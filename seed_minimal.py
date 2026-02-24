import urllib.request
import urllib.parse
import json
import csv
import sys
import os

SUPABASE_URL = "https://voiexsboyzgglnmtinhf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZvaWV4c2JveXpnZ2xubXRpbmhmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE4OTIxODQsImV4cCI6MjA4NzQ2ODE4NH0.Q5-EXFDNVKAW_sCBp0KQRrv7xzziQqFuZ2MXqwbusdM"

def extract_primary_domain(url):
    if not isinstance(url, str) or not url.strip(): return None
    try:
        if not url.startswith('http'): url = 'https://' + url
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith('www.'): netloc = netloc[4:]
        return netloc if netloc else None
    except:
        return None

def clean_data(val):
    if val is None or val == "" or val.lower() == 'nan': return None
    return str(val).strip()

def seed_companies():
    records = []
    try:
        with open("offline_dossier/ibs_2026_final_enriched.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                website = clean_data(row.get('Inferred_Website')) or clean_data(row.get('Website'))
                
                record = {
                    "booth_number": clean_data(row.get('Booth')),
                    "company_name": clean_data(row.get('Company')) or f"Unknown Company {i}",
                    "segment": clean_data(row.get('Segment')),
                    "description": clean_data(row.get('Description')),
                    "website": website,
                    "primary_domain": extract_primary_domain(website),
                    "visited": False,
                    "priority": 1
                }
                records.append(record)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)

    url = f"{SUPABASE_URL}/rest/v1/companies"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    batch_size = 100
    success_count = 0
    print(f"Total companies to insert: {len(records)}")
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        data = json.dumps(batch).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        
        try:
            with urllib.request.urlopen(req) as response:
                if response.status in (200, 201, 204):
                    success_count += len(batch)
                    print(f"Inserted {success_count}/{len(records)}...", flush=True)
                else:
                    print(f"Error: HTTP {response.status}")
        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code}: {e.read().decode()}")
        except urllib.error.URLError as e:
            print(f"URL Error: {e.reason}")

    print(f"\n✅ Seeding complete! Successfully inserted {success_count} companies using native modules.")

if __name__ == "__main__":
    seed_companies()
