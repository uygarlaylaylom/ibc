import pandas as pd
import os

INPUT_CSV = "offline_dossier/ibs_2026_final_enriched.csv"
OUTPUT_EXCEL_CSV = "offline_dossier/ibs_2026_final_enriched_EXCEL.csv"

def main():
    if not os.path.exists(INPUT_CSV):
        print(f"Error: {INPUT_CSV} not found.")
        return

    print(f"Reading {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)
    
    print(f"Writing Excel-friendly CSV to {OUTPUT_EXCEL_CSV}...")
    # Use ; as separator and utf-8-sig (BOM) which forces Excel to recognize encoding
    df.to_csv(OUTPUT_EXCEL_CSV, index=False, sep=';', encoding='utf-8-sig')
    print("Success! Created Excel-compatible CSV.")

if __name__ == "__main__":
    main()
