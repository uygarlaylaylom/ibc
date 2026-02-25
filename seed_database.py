import os
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
import math
import urllib.parse

# Load environment variables
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Warning: SUPABASE_URL or SUPABASE_KEY not found in .env file. ")
    print("Trying to proceed, but if it fails, please create a .env file with your credentials.")

# Initialize Supabase Client (Will delay creation if keys are missing so script can still be loaded)
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    supabase = None
    pass

def extract_primary_domain(url):
    """Extracts the base domain from a URL (e.g. https://www.vosker.com -> vosker.com)."""
    if not isinstance(url, str) or not url.strip():
        return None
    try:
        # Give it a scheme if missing so urlparse works correctly
        if not url.startswith('http'):
            url = 'https://' + url
            
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        
        # Remove 'www.'
        if netloc.startswith('www.'):
            netloc = netloc[4:]
            
        return netloc if netloc else None
    except:
        return None

def clean_data(val):
    """Cleans NaN or float values from pandas to be JSON serializable for Supabase."""
    if pd.isna(val):
        return None
    if isinstance(val, float) and math.isnan(val):
         return None
    return str(val).strip() if val else None

def seed_companies(file_path="ibs_2026_all_exhibitors_clean.xlsx"):
    if not supabase:
        print("Cannot run seeding without Supabase credentials. Set them in a .env file.")
        return
        
    print(f"Loading data from {file_path}...")
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return

    records = []
    
    # Required columns in Supabase: booth_number, company_name, segment, description, website, primary_domain
    for index, row in df.iterrows():
        # Use fallbacks to handle small header variations in the clean excel
        website = clean_data(row.get('Website')) or clean_data(row.get('Inferred_Website'))
        primary_domain = extract_primary_domain(website)
        
        company = clean_data(row.get('Company')) or clean_data(row.get('Company Name')) or clean_data(row.get('Exhibitor Name')) or clean_data(row.get('Name')) or f"Unknown Company {index}"
        booth = clean_data(row.get('Booth')) or clean_data(row.get('Booth Number'))
        segment = clean_data(row.get('Segment')) or clean_data(row.get('Category')) or clean_data(row.get('Product Category'))
        desc = clean_data(row.get('Description')) or clean_data(row.get('About')) or clean_data(row.get('Profile'))
        
        record = {
            "booth_number": booth,
            "company_name": company,
            "segment": segment,
            "description": desc,
            "website": website,
            "primary_domain": primary_domain,
            "visited": False,
            "priority": 1
        }
        records.append(record)

    print(f"Parsed {len(records)} companies. Proceeding to insert to Supabase in batches of 100...")
    
    # Insert in batches
    batch_size = 100
    success_count = 0
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            # Upsert by company_name + booth_number could be tricky without a unique constraint,
            # so we just insert. We assume an empty table.
            response = supabase.table("companies").insert(batch).execute()
            success_count += len(response.data)
            print(f"Inserted {success_count}/{len(records)}...")
        except Exception as e:
            print(f"Error inserting batch starting at {i}: {e}")
            
    print(f"Seeding complete! Successfully inserted {success_count} companies.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Test domain parsing:", extract_primary_domain("https://www.google.com/test"))
    else:
        seed_companies()
