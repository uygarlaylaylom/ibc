import os
import requests
import json
import pandas as pd
import math
import urllib.parse
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def extract_primary_domain(url):
    if not isinstance(url, str) or not url.strip():
        return None
    try:
        if not url.startswith('http'):
            url = 'https://' + url
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        return netloc if netloc else None
    except:
        return None

def clean_data(val):
    if pd.isna(val):
        return None
    if isinstance(val, float) and math.isnan(val):
         return None
    return str(val).strip() if val else None

def seed_companies():
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    url = f"{SUPABASE_URL}/rest/v1/companies"
    
    try:
        df = pd.read_csv("offline_dossier/ibs_2026_final_enriched.csv")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    records = []
    
    for index, row in df.iterrows():
        website = clean_data(row.get('Inferred_Website')) or clean_data(row.get('Website'))
        primary_domain = extract_primary_domain(website)
        
        record = {
            "booth_number": clean_data(row.get('Booth')),
            "company_name": clean_data(row.get('Company')) or f"Unknown Company {index}",
            "segment": clean_data(row.get('Segment')),
            "description": clean_data(row.get('Description')),
            "website": website,
            "primary_domain": primary_domain,
            "visited": False,
            "priority": 1
        }
        records.append(record)

    batch_size = 100
    success_count = 0
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            response = requests.post(url, headers=headers, json=batch)
            if response.status_code in (200, 201, 204):
                success_count += len(batch)
                print(f"Inserted {success_count}/{len(records)}...")
            else:
                print(f"Error inserting batch: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Exception: {e}")

    print(f"Seeding complete! Successfully inserted {success_count} companies using Request API.")

if __name__ == "__main__":
    seed_companies()
