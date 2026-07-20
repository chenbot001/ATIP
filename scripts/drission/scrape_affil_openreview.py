import csv
import time
import random
import pandas as pd
import os
import urllib.parse
import json
from DrissionPage import ChromiumPage, ChromiumOptions
from tqdm import tqdm

# ==============================================================================
# --- CONFIGURATION ---
# ==============================================================================
INPUT_CSV_PATH = "data/author_profiles.csv"
OUTPUT_DF_PATH = "data/author_history.csv"
CHECKPOINT_FILE = "data/scraping_checkpoint.json"
RESTART_WAIT_TIME_SECONDS = 120
SAVE_INTERVAL = 100
MAX_PROFILE_ID_SEARCH = 50

co = ChromiumOptions().headless()
co.set_browser_path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

# --- HELPER FUNCTION TO SAVE DATAFRAME ---
def save_dataframe(file_path, results_list, message="✅ DataFrame progress saved."):
    if not results_list:
        return
    df = pd.DataFrame(results_list)
    column_order = ["author_id", "author_name", "openreview_id", "affiliation", "position", "timeframe"]
    df = df.reindex(columns=column_order)
    df.drop_duplicates(inplace=True)
    df.to_csv(file_path, index=False, encoding='utf-8')
    print(message)

# --- HELPER FUNCTION TO SAVE CHECKPOINT ---
def save_checkpoint(author_id, author_name):
    checkpoint_data = {
        "last_processed_author_id": author_id,
        "last_processed_author_name": author_name,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(checkpoint_data, f, indent=2)

# --- HELPER FUNCTION TO LOAD CHECKPOINT ---
def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            return json.load(f)
    return None

# ==============================================================================
# --- SCRIPT LOGIC with AUTO-RESTART LOOP ---
# ==============================================================================
while True:
    try:
        with open(INPUT_CSV_PATH, mode='r', encoding='utf-8', newline='') as infile:
            reader = csv.reader(infile)
            next(reader, None)
            input_authors = list(reader)
    except FileNotFoundError:
        print(f"Error: Input file not found at '{INPUT_CSV_PATH}'")
        break

    scraped_results = []
    processed_author_ids = set()
    
    # Load existing results and track processed author_ids
    if os.path.exists(OUTPUT_DF_PATH):
        print(f"Resuming from existing results file: {OUTPUT_DF_PATH}")
        df_existing = pd.read_csv(OUTPUT_DF_PATH)
        scraped_results = df_existing.to_dict('records')
        # Track processed author_ids instead of just names
        processed_author_ids = set(df_existing['author_id'].unique())
        print(f"Found {len(processed_author_ids)} already processed authors")

    # Load checkpoint to find where we left off
    checkpoint = load_checkpoint()
    start_index = 0
    
    if checkpoint:
        last_processed_id = checkpoint.get("last_processed_author_id")
        last_processed_name = checkpoint.get("last_processed_author_name")
        print(f"Checkpoint found: Last processed was {last_processed_name} (ID: {last_processed_id})")
        
        # Find the index of the next author to process
        for i, author in enumerate(input_authors):
            if author[0] == last_processed_id:
                start_index = i + 1  # Start from the next author
                break
        print(f"Resuming from index {start_index}")

    # Filter authors to process - start from the checkpoint position
    authors_to_process = input_authors[start_index:]

    if not authors_to_process:
        print("✅ All authors have been processed. Exiting script.")
        break

    print(f"\n--- Starting new session. {len(authors_to_process)} authors remaining. ---")
    page = None

    try:
        page = ChromiumPage(addr_or_opts=co)
        progress_bar = tqdm(
            enumerate(authors_to_process),
            total=len(authors_to_process),
            desc="Scraping History"
        )

        for i, author_row in progress_bar:
            author_id = author_row[0]
            author_name = f"{author_row[1]} {author_row[2]}"
            
            # Skip if this author_id was already processed (from existing results)
            if author_id in processed_author_ids:
                progress_bar.set_postfix_str(f"Skipping {author_name} (already processed)")
                continue
                
            try:
                progress_bar.set_postfix_str(f"Processing: {author_name}")
                base_profile_id = f"~{author_row[1]}_{author_row[2]}"
                
                # --- SEARCH AND SCRAPE ON THE FLY ---
                total_entries = 0
                valid_profiles = 0
                
                for profile_num in range(1, MAX_PROFILE_ID_SEARCH + 1):
                    current_id = f"{base_profile_id}{profile_num}"
                    current_url = f"https://openreview.net/profile?id={urllib.parse.quote(current_id)}"
                    page.get(current_url)
                    
                    # Check for an explicit error message
                    if page.ele('css:pre.error-message', timeout=2):
                        # If the error message exists, this profile ID is invalid. Stop searching.
                        time.sleep(1)
                        break
                    
                    # If no error message, this is a valid profile - scrape it immediately
                    valid_profiles += 1
                    history_entries = page.eles('css:section.history .table-row', timeout=3)
                    found_count = 0
                    
                    for entry in list(history_entries):  # Convert to list to fix iteration issue
                        position = entry.ele('.position').text
                        institution = entry.ele('.institution').text
                        timeframe = entry.ele('.timeframe').text
                        
                        scraped_results.append({
                            "author_id": author_id,  # author_id is the first column
                            "author_name": author_name,
                            "openreview_id": current_id,
                            "affiliation": institution,
                            "position": position,
                            "timeframe": timeframe
                        })
                        found_count += 1
                    
                    total_entries += found_count
                    progress_bar.set_postfix_str(f"Profile {profile_num} for {author_name}")
                    time.sleep(1)
                
                # Mark this author_id as processed and save checkpoint immediately
                processed_author_ids.add(author_id)
                save_checkpoint(author_id, author_name)
                
                if valid_profiles > 0:
                    progress_bar.set_postfix_str(f"Status: Found {total_entries} entries from {valid_profiles} profiles")
                else:
                    progress_bar.set_postfix_str(f"Status: No Profile Found ❌")

            except Exception as e:
                progress_bar.set_postfix_str(f"Status: Error ❗ - {str(e)}")
            
            # Auto-save logic
            if (i + 1) % SAVE_INTERVAL == 0 and (i + 1) < len(authors_to_process):
                save_dataframe(
                    OUTPUT_DF_PATH, scraped_results,
                    message=f"\n🔄 Processed {i + 1} authors. Auto-saving progress..."
                )

    except KeyboardInterrupt:
        print("\n🛑 User interrupted. Saving progress and exiting...")
        break

    finally:
        if page:
            page.quit()
        save_dataframe(OUTPUT_DF_PATH, scraped_results)
    break