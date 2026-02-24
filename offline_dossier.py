import os
import re
import time
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from urllib.parse import urljoin, urlparse

# --- Configuration ---
# Default to CSV as openpyxl is missing
INPUT_FILE = "ibs_2026_all_exhibitors.csv" 
OUTPUT_DIR = "offline_dossier"
MAX_WORKERS = 10  # Number of concurrent requests
TIMEOUT = 30      # Request timeout in seconds

# Headers to mimic a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def clean_filename(s):
    """Creates a safe filename from a string."""
    s = str(s).lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')

def get_session():
    """Creates a requests Session with retry logic."""
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session

def fetch_url(session, url):
    """Fetches a URL, returning text and final URL."""
    try:
        response = session.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        return response.text, response.url
    except Exception:
        return "", ""

# --- Regex Extraction Helpers (No BS4) ---

def extract_emails(html):
    """Extracts emails using regex."""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(email_pattern, html)))

def extract_links_parsed(html):
    """Extracts all hrefs from <a> tags."""
    return re.findall(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"', html, re.IGNORECASE)

def extract_social_links(html):
    """Extracts social media links."""
    social_domains = ['facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com', 'youtube.com']
    links = []
    found_hrefs = extract_links_parsed(html)
    for href in found_hrefs:
        if any(domain in href for domain in social_domains):
            links.append(href)
    return list(set(links))

def extract_meta_content(html):
    """Extracts meta description and keywords using regex."""
    description = ""
    keywords = ""
    
    # Meta Description
    desc_match = re.search(r'<meta\s+(?:name|property)=["\'](?:og:)?description["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
    if desc_match:
        description = desc_match.group(1).strip()

    # Meta Keywords
    key_match = re.search(r'<meta\s+name=["\']keywords["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
    if key_match:
        keywords = key_match.group(1).strip()
        
    return description, keywords

def remove_tags(html):
    """Removes HTML tags to get text content."""
    # Remove script and style content first
    clean = re.sub(r'<(script|style).*?</\1>', '', html, flags=re.DOTALL|re.IGNORECASE)
    # Remove comments
    clean = re.sub(r'<!--.*?-->', '', clean, flags=re.DOTALL)
    # Remove tags
    clean = re.sub(r'<[^>]+>', ' ', clean)
    # Unescape common entities (basic)
    clean = clean.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    # Normalize whitespace
    return re.sub(r'\s+', ' ', clean).strip()

def process_company(row, session):
    """
    Process a single company:
    1. Visit profile URL (IBS) -> Extract real website
    2. Visit real website -> Extract content, emails, social
    3. Save HTML and Markdown report
    """
    company_name = row.get("Company", "Unknown")
    profile_url = row.get("Website", "")
    segment = row.get("Segment", "General")
    
    slug = clean_filename(company_name)
    company_dir = os.path.join(OUTPUT_DIR, "detailed_reports", slug)
    os.makedirs(company_dir, exist_ok=True) 
    
    result = {
        "Company": company_name,
        "Segment": segment,
        "ProfileURL": profile_url,
        "CompanyWebsite": "",
        "Status": "Failed",
        "Emails": "",
        "SocialLinks": "",
        "MetaDescription": "",
        "ReportPath": ""
    }

    # 1. Fetch Profile Page (IBS) or Use CSV data
    # The profile URL is likely broken (404), so we prioritize existing CSV data
    # and try to find a link in the description if possible.

    bs_profile_url = profile_url
    
    # Try to extract website from Description if available and looks like a URL
    description_text = str(row.get("Description", ""))
    
    # Simple check for links in description (naive)
    if "http" in description_text:
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', description_text)
        if urls:
            # Filter out IBS links
            for u in urls:
                if "buildersshow.com" not in u:
                    result["CompanyWebsite"] = u
                    break
    
    # If we found a website, try to scrape it
    text_content = ""
    emails = []
    socials = []
    desc = ""
    keywords = ""
    
    if result["CompanyWebsite"]:
        site_html, final_url = fetch_url(session, result["CompanyWebsite"])
        if site_html:
            result["Status"] = "Success"
            text_content = remove_tags(site_html)
            emails = extract_emails(site_html)
            socials = extract_social_links(site_html)
            desc, keyw = extract_meta_content(site_html)
            keywords = keyw
            
            result["Emails"] = ", ".join(emails)
            result["SocialLinks"] = ", ".join(socials)
            result["MetaDescription"] = desc
        else:
            result["Status"] = "Website Unreachable"
    else:
        result["Status"] = "No Website Found"

    # 5. Save Artifacts (Markdown Report is ALWAYS generated)
    
    # Use description from CSV if no web crawl
    if not desc:
        desc = description_text[:300] + "..." if len(description_text) > 300 else description_text

    markdown_report = f"""# {company_name}

**Segment:** {segment}
**Booth:** {row.get('Booth', 'N/A')}
**Location:** {row.get('City', '')}, {row.get('State/Country', '')}
**IBS Profile:** {bs_profile_url}
**Detected Website:** {result['CompanyWebsite'] or 'None'}

## IBS Description
{description_text}

## Web Crawl Data
**Status:** {result['Status']}
- **Emails:** {', '.join(emails) if emails else 'None'}
- **Socials:** {', '.join(socials) if socials else 'None'}
- **Meta Description:** {desc}

## Scraped Content (Preview)
{text_content[:2000] if text_content else "No content scraped."}
"""
    report_path = os.path.join(company_dir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(markdown_report)
    
    result["ReportPath"] = report_path
    
    return result

def main():
    # Force CSV usage since openpyxl is missing
    input_file = INPUT_FILE
    
    if not os.path.exists(input_file):
         print(f"Error: Input file '{input_file}' not found.")
         return

    # Create directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    try:
        # pd.read_csv works without openpyxl
        df = pd.read_csv(input_file)
        # Filter for relevant columns if needed, or just use as is
    except Exception as e:
        print(f"Error reading input CSV: {e}")
        return

    print(f"Loaded {len(df)} exhibitors from {input_file}")
    
    session = get_session()
    results = []
    
    # Use ThreadPoolExecutor for concurrency
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_company = {executor.submit(process_company, row, session): row for _, row in df.iterrows()}
        
        for future in tqdm(as_completed(future_to_company), total=len(df), desc="Scraping Companies"):
            try:
                data = future.result()
                results.append(data)
            except Exception:
                pass
    
    # Save Master Index to CSV (No Excel dependency)
    output_df = pd.DataFrame(results)
    output_csv = os.path.join(OUTPUT_DIR, "dossier_index.csv")
    output_df.to_csv(output_csv, index=False)
    
    print(f"\nScraping complete! Results saved to '{output_csv}'")
    print(f"Detailed Markdown reports are in '{OUTPUT_DIR}/detailed_reports/'")

if __name__ == "__main__":
    main()
