import os
import pandas as pd
import requests
import json
import time
from tqdm import tqdm

# --- Configuration ---
API_KEY = os.environ.get("OPENAI_API_KEY", "your-api-key-here")
INPUT_DOSSIER = "offline_dossier/dossier_index.csv"
INPUT_ORIGINAL = "ibs_2026_all_exhibitors_clean - Sheet1.csv" 
OUTPUT_FILE = "offline_dossier/ibs_2026_final_enriched.csv"
MODEL_NAME = "gpt-4o"

def enrich_company(company, description, segment):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    prompt = f"""
    Analyze the following company information from a construction trade show (IBS 2026).
    
    Company: {company}
    Segment: {segment}
    Description: {description}
    
    Task:
    1. Extract a comma-separated list of specific PRODUCTS they offer.
    2. Extract a comma-separated list of SERVICES they offer.
    3. If the website is missing, suggest a likely domain (e.g. companyname.com).
    
    Output format: JSON
    {{
      "products": "item1, item2, ...",
      "services": "service1, service2, ...",
      "inferred_website": "example.com"
    }}
    """
    
    data = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant extracting structured data from company descriptions."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
             print(f"Error ({response.status_code}): {response.text}")
             if response.status_code == 429: # Rate limit
                 time.sleep(20)
             return ""
        
        result = response.json()
        text = result["choices"][0]["message"]["content"]
        return text
    except Exception as e:
        print(f"Exception: {e}")
        return ""

def parse_json(json_str):
    try:
        if not json_str: return "","",""
        data = json.loads(json_str)
        return data.get("products", ""), data.get("services", ""), data.get("inferred_website", "")
    except:
        return json_str, "", "" 

def main():
    if not os.path.exists(INPUT_DOSSIER) or not os.path.exists(INPUT_ORIGINAL):
        print("Input files not found.")
        return

    # 1. Check for existing output to RESUME
    if os.path.exists(OUTPUT_FILE):
        print(f"Found existing output file '{OUTPUT_FILE}'. Resuming...")
        df_merged = pd.read_csv(OUTPUT_FILE)
    else:
        print("Loading initial data...")
        try:
            df_dossier = pd.read_csv(INPUT_DOSSIER)
            df_orig = pd.read_csv(INPUT_ORIGINAL)
            # Merge
            df_merged = pd.merge(df_orig, df_dossier[['Company', 'Status', 'Emails', 'SocialLinks', 'MetaDescription', 'ReportPath']], on='Company', how='left')
            # Init cols
            df_merged["Extracted_Products"] = ""
            df_merged["Extracted_Services"] = ""
            df_merged["Inferred_Website"] = ""
        except Exception as e:
            print(f"Error loading CSVs: {e}")
            return

    print(f"Total records to process: {len(df_merged)}")
    print("Starting OpenAI Enrichment (GPT-4o)...")
    
    requests_count = 0
    total_processed = 0
    
    for index, row in tqdm(df_merged.iterrows(), total=len(df_merged)):
        # Check if already done
        if pd.notna(row.get('Extracted_Products')) and str(row.get('Extracted_Products')).strip() != "":
            continue
            
        desc = str(row.get('Description', ''))
        if len(desc) < 10 or pd.isna(desc): 
            continue
            
        analysis_json = enrich_company(row['Company'], desc, row.get('Segment', ''))
        products, services, web = parse_json(analysis_json)
        
        df_merged.at[index, 'Extracted_Products'] = products
        df_merged.at[index, 'Extracted_Services'] = services
        df_merged.at[index, 'Inferred_Website'] = web
        
        requests_count += 1
        total_processed += 1
        
        # Save explicitly frequently
        if total_processed % 10 == 0:
            df_merged.to_csv(OUTPUT_FILE, index=False)

    df_merged.to_csv(OUTPUT_FILE, index=False)
    print(f"\nProcessing complete! Final Merged File: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
