import pandas as pd
import os
import sys
from datetime import datetime

def extract_id_from_url(url):
    """
    Extracts the last segment from a URL path.
    Example: 'https://doi.org/10.18653/v1/2020.acl-main.42' -> '2020.acl-main.42'
    """
    if not isinstance(url, str):
        return None
    return url.strip().strip('/').split('/')[-1]

def report_acl_coverage():
    """
    Main function to compare ACL paper IDs against the DBLP dataset, report coverage,
    and log any ACL papers that are not found in DBLP.
    """
    # --- Configuration ---
    DBLP_FILE = os.path.join('revised_data', 'dblp_nlp_papers.csv')
    ACL_FILE = os.path.join('revised_data', 'acl_papers_cleaned.csv')
    UNCOVERED_PAPERS_LOG = 'acl_papers_not_in_dblp.txt'

    # --- 1. Load Data ---
    print("--- Starting ACL Coverage Report Script ---")
    try:
        print(f"📚 Loading DBLP data from '{DBLP_FILE}'...")
        dblp_df = pd.read_csv(DBLP_FILE)
        print(f"📚 Loading ACL data from '{ACL_FILE}'...")
        acl_df = pd.read_csv(ACL_FILE)
    except FileNotFoundError as e:
        print(f"❌ Error: File not found. Please check your file paths. Details: {e}")
        sys.exit(1)

    # --- 2. Prepare Data for Matching ---
    print("⚙️  Preparing data for case-insensitive comparison...")
    dblp_df['extracted_id'] = dblp_df['ee'].apply(extract_id_from_url).str.lower()
    acl_df['normalized_paper_id'] = acl_df['paper_id'].astype(str).str.lower()

    # --- 3. Perform the Match (ACL -> DBLP) ---
    print("🔍 Finding which ACL papers are covered by the DBLP dataset...")
    
    # Create a set of DBLP IDs for very fast lookups
    dblp_id_set = set(dblp_df['extracted_id'].dropna())

    # Create a boolean mask to identify which ACL rows have an ID present in the DBLP set
    matched_mask = acl_df['normalized_paper_id'].isin(dblp_id_set)
    
    # Separate the ACL DataFrame into covered and uncovered papers
    covered_acl_df = acl_df[matched_mask]
    uncovered_acl_df = acl_df[~matched_mask]

    # --- 4. Generate and Print Summary ---
    total_acl_papers = len(acl_df)
    covered_count = len(covered_acl_df)
    uncovered_count = len(uncovered_acl_df)
    coverage_percentage = (covered_count / total_acl_papers) * 100 if total_acl_papers > 0 else 0

    print("\n" + "="*45)
    print("       ACL Dataset Coverage Summary")
    print("="*45)
    print(f"Total papers in ACL file: {total_acl_papers}")
    print(f"ACL papers covered by DBLP dataset: {covered_count} ✅")
    print(f"ACL papers NOT covered by DBLP: {uncovered_count} ❌")
    print(f"Coverage Percentage: {coverage_percentage:.2f}%")
    print("="*45)

    # --- 5. Save Uncovered Papers to Log File ---
    if not uncovered_acl_df.empty:
        print(f"\n📝 Logging {uncovered_count} uncovered ACL papers...")
        with open(UNCOVERED_PAPERS_LOG, 'w', encoding='utf-8') as f:
            f.write(f"ACL Papers Not Found in DBLP Dataset\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Uncovered: {uncovered_count}\n")
            f.write("="*80 + "\n\n")

            for index, row in uncovered_acl_df.iterrows():
                # Safely get doi, title, and paper_id, providing 'N/A' if missing
                paper_id = row.get('paper_id', 'N/A')
                title = row.get('title', 'N/A')
                doi = row.get('doi', 'N/A')

                f.write(f"ID:    {paper_id}\n")
                f.write(f"Title: {title}\n")
                f.write(f"DOI:   {doi}\n")
                f.write("-" * 40 + "\n")
        
        print(f"💾 Log file for uncovered papers saved to '{UNCOVERED_PAPERS_LOG}'")
    else:
        print("\n✅ All ACL papers were covered by the DBLP dataset. No log file created.")

if __name__ == "__main__":
    report_acl_coverage()