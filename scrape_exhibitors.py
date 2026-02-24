import requests
import pandas as pd
import time
import re
from html import unescape

BASE_URL = "https://www.buildersshow.com/search-api/exhibitors"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

SEGMENTS = ["BB", "MP", "CT", "GP", "IF", "OL"]

def clean_html(raw_html):
    if not raw_html:
        return ""
    text = re.sub('<.*?>', '', raw_html)
    return unescape(text).strip()

def classify_role(product_segment):
    if not product_segment:
        return "Product"
    if "Business Management" in product_segment:
        return "Service"
    return "Product"

def fetch_all(page_size=100):
    all_rows = []
    startrow = 1

    while True:
        params = {
            "startrow": startrow,
            "pagesize": page_size,
            "showID": 22,
        }
        
        # The user's code had a loop inside the loop for params?
        # Original code:
        # for seg in SEGMENTS:
        #    params.setdefault("segments", [])
        #    params["segments"].append(seg)
        # 
        # Wait, the original code logic for params construction might be slightly off if it appends multiple times in the while loop?
        # Actually, `params` is re-initialized inside the `while True` loop.
        # But wait, looking at the user's provided code:
        # while True:
        #    params = { ... }
        #    for seg in SEGMENTS:
        #        params.setdefault("segments", [])
        #        params["segments"].append(seg)
        # This looks correct, it sets the segments for every request.
        
        # However, `requests` params with lists might need specific handling (e.g. segments[]=BB&segments[]=MP) or just separate keys.
        # Let's stick EXACTLY to the user's code first.
        # But wait, `requests` handles list in params by repeating the key usually if passed as a list.
        # The user's code does: `params["segments"].append(seg)`.
        
        for seg in SEGMENTS:
            params.setdefault("segments", [])
            params["segments"].append(seg)
            
        print(f"Requesting startrow={startrow}...")
        try:
            response = requests.get(BASE_URL, headers=HEADERS, params=params)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Error fetching data: {e}")
            break

        # The API structure in the user code expects "Results"
        items = data.get("Results", [])
        if not items:
            print("No more items found.")
            break

        for item in items:
            booths = item.get("booths", [])
            booth_number = booths[0]["booth"] if booths else None

            product_segment = item.get("productSegment", "")

            # The user code had: "Website": f"https://www.buildersshow.com/exhibitor/{item.get('redirectName')}"
            
            all_rows.append({
                "Company": item.get("companyName"),
                "Segment": product_segment,
                "City": item.get("city"),
                "State/Country": item.get("stateCountry"),
                "Booth": booth_number,
                "Website": f"https://www.buildersshow.com/exhibitor/{item.get('redirectName')}",
                "Description": clean_html(item.get("description")),
                "Role": classify_role(product_segment)
            })

        print(f"Fetched {len(items)} items. Total so far: {len(all_rows)}")
        startrow += page_size
        time.sleep(1)

    return pd.DataFrame(all_rows)

if __name__ == "__main__":
    print("Starting scrape...")
    df = fetch_all()
    output_file = "ibs_2026_all_exhibitors.csv"
    df.to_csv(output_file, index=False)
    print(f"Done. File saved as {output_file}")
