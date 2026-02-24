import os
import pandas as pd

INPUT_CSV = "offline_dossier/ibs_2026_final_enriched.csv"

def update_markdown_report(report_path, products, services, website):
    if not os.path.exists(report_path):
        return

    with open(report_path, 'r') as f:
        content = f.read()

    # Prepare new content
    enrichment_section = ""
    if website and "No Website Found" in content:
        # Replace "No Website Found" in the header metadata if we found one
        content = content.replace("**Detected Website:** None", f"**Detected Website:** {website}")
        content = content.replace("**Status:** No Website Found", f"**Status:** AI Inferred Website")
    
    # Add new section for Products & Services
    new_section = "\n## AI Enrichment (Gemini/OpenAI)\n"
    if website:
        new_section += f"- **Inferred Website:** [{website}](https://{website})\n"
    if products:
        new_section += f"- **Products:** {products}\n"
    if services:
        new_section += f"- **Services:** {services}\n"
        
    if "## AI Enrichment" not in content:
        # Append before "## Scraped Content" or at the end
        if "## Scraped Content" in content:
            content = content.replace("## Scraped Content", f"{new_section}\n## Scraped Content")
        else:
            content += new_section

    with open(report_path, 'w') as f:
        f.write(content)

def main():
    if not os.path.exists(INPUT_CSV):
        print("Enriched CSV not found.")
        return

    print("Updating Markdown reports...")
    df = pd.read_csv(INPUT_CSV)
    
    count = 0
    for index, row in df.iterrows():
        products = str(row.get('Extracted_Products', '')).strip()
        services = str(row.get('Extracted_Services', '')).strip()
        website = str(row.get('Inferred_Website', '')).strip()
        report_path = str(row.get('ReportPath', '')).strip()
        
        # Only update if we have something new
        if (products and products != 'nan') or (services and services != 'nan') or (website and website != 'nan'):
            # Handle NaN strings
            if products == 'nan': products = ""
            if services == 'nan': services = ""
            if website == 'nan': website = ""
            
            update_markdown_report(report_path, products, services, website)
            count += 1
            
    print(f"Updated {count} reports with enriched data.")

if __name__ == "__main__":
    main()
