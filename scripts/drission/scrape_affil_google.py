import csv
import time
import random
from DrissionPage import ChromiumPage, ChromiumOptions
from tqdm import tqdm

# ==============================================================================
# --- CONFIGURATION ---
# ==============================================================================
CSV_FILE_PATH = "data/author_profiles.csv"
BASE_RESTART_WAIT_SECONDS = 300  # The initial wait time (5 minutes)
SAVE_INTERVAL = 500
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# ==============================================================================
# --- SCRIPT SETUP ---
# ==============================================================================

def save_progress(file_path, header, data, message="✅ Progress saved."):
    """Writes the current progress to the CSV file."""
    with open(file_path, mode='w', encoding='utf-8', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerow(header)
        writer.writerows(data)
    print(message)

# Initialize state for CAPTCHA handling
consecutive_captcha_count = 0

# ==============================================================================
# --- MAIN SCRIPT LOGIC with AUTO-RESTART LOOP ---
# ==============================================================================
while True:
    # Read data and identify rows that still need processing
    try:
        with open(CSV_FILE_PATH, mode='r', encoding='utf-8', newline='') as infile:
            reader = csv.reader(infile)
            all_data = list(reader)
        header = all_data[0]
        data_rows = all_data[1:]
    except FileNotFoundError:
        print(f"Error: Input file not found at '{CSV_FILE_PATH}'")
        break

    rows_to_process = [(index, row) for index, row in enumerate(data_rows) if not row[5].strip()]

    # If no work is left, the script's job is done.
    if not rows_to_process:
        print("✅ All tasks are complete. Exiting script.")
        break

    # Configure browser for the current session (always Chrome)
    co = ChromiumOptions()
    co.set_browser_path(CHROME_PATH)
    print(f"\n--- Starting new session with Chrome. {len(rows_to_process)} authors remaining. ---")
    
    page = None
    captcha_was_detected = False
    hard_block_detected = False
    first_query_successful = False  # Track if first query of session was successful

    try:
        page = ChromiumPage(addr_or_opts=co)
        progress_bar = tqdm(
            enumerate(rows_to_process),
            total=len(rows_to_process),
            desc="Scraping Affiliations"
        )
        for i, (index, row_data) in progress_bar:
            try:
                first_name, last_name = row_data[1], row_data[2]
                query_name = f"{first_name} {last_name}"
                progress_bar.set_postfix_str(f"Processing: {query_name}")
                page.get(f"https://scholar.google.com/scholar?hl=en&q={query_name}")

                # Check for hard block message first
                if page.ele("text:We're sorry...", timeout=2):
                    print("\n❌ Hard IP block detected by Google. Terminating script.")
                    hard_block_detected = True
                    break

                # Then, check for the regular CAPTCHA
                if page.ele('#gs_captcha_ccl', timeout=2):
                    progress_bar.set_postfix_str("Status: CAPTCHA 🚨")
                    captcha_was_detected = True
                    # Check if this is the first query of the session
                    if i == 0:
                        print(f"\n🚨 Consecutive CAPTCHA detected on first query! Count: {consecutive_captcha_count + 1}")
                    break

                # (Perfect match verification logic remains the same)
                profile_link_container = page.ele('tag:h4@class=gs_rt2', timeout=2)
                match_found = False
                if profile_link_container:
                    link_element = profile_link_container.ele("tag:a")
                    if link_element and query_name.lower() == link_element.text.lower():
                        match_found = True
                        profile_url = link_element.attr("href")
                        if profile_url:  # Fix the linter error by checking for None
                            page.get(profile_url)
                            affiliation_element = page.ele('css:.gsc_prf_il', timeout=2)
                            if affiliation_element:
                                data_rows[index][5] = affiliation_element.text.replace(',', ';')
                            else:
                                data_rows[index][5] = "No Record"
                        else:
                            data_rows[index][5] = "No Record"
                        progress_bar.set_postfix_str("Status: Found (Perfect Match) ✔️")
                
                if not match_found:
                    data_rows[index][5] = "No Record"
                    progress_bar.set_postfix_str("Status: Not Found ❌")
                
                # Mark first query as successful if we reach this point
                if i == 0:
                    first_query_successful = True

            except Exception:
                data_rows[index][5] = "Error"
                progress_bar.set_postfix_str("Status: Error ❗")
            
            time.sleep(random.uniform(2, 5))
            if (i + 1) % SAVE_INTERVAL == 0 and (i + 1) < len(rows_to_process):
                save_progress(CSV_FILE_PATH, header, data_rows, f"\n🔄 Processed {i + 1} authors...")

    except KeyboardInterrupt:
        print("\n🛑 User interrupted. Exiting permanently.")
        break

    finally:
        if page:
            page.quit()
        save_progress(CSV_FILE_PATH, header, data_rows)
    
    # If a hard block was found, break the main 'while' loop to exit.
    if hard_block_detected:
        break

    # If a regular CAPTCHA was found, handle the incremental wait time.
    if captcha_was_detected:
        # Only increment consecutive count if CAPTCHA was on the first query
        if not first_query_successful:
            consecutive_captcha_count += 1
            print(f"🚨 Consecutive CAPTCHA detected! Count: {consecutive_captcha_count}")
            
            # Check if we've hit the limit (3 consecutive CAPTCHAs)
            # if consecutive_captcha_count >= 3:
            #     print("❌ Maximum consecutive CAPTCHAs (3) reached. Exiting script.")
            #     break
        else:
            print("✅ CAPTCHA detected but first query was successful. Resetting consecutive counter.")
            consecutive_captcha_count = 0
            
        # Add 2 minutes (120 seconds) to the wait time for each consecutive failure.
        current_wait_time = BASE_RESTART_WAIT_SECONDS + (consecutive_captcha_count * 120)
        
        print(f"Waiting for {current_wait_time / 60:.1f} minutes before restarting...")
        time.sleep(current_wait_time)
    else:
        # If a session completes successfully (finishes its list of authors),
        # this 'else' block will be reached. The main loop will then restart
        # and the check at the top will find no rows to process, exiting gracefully.
        print("Session completed successfully. Resetting CAPTCHA counter.")
        consecutive_captcha_count = 0