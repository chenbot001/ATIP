import pandas as pd
import os
import requests
import time
from difflib import SequenceMatcher
import re
from datetime import datetime

def clean_title(title):
    """
    Clean a title for comparison by removing special characters and normalizing case.
    
    Args:
        title (str): The title to clean
        
    Returns:
        str: Cleaned title
    """
    if pd.isna(title) or title is None:
        return ""
    
    # Convert to string and lowercase
    title = str(title).lower()
    
    # Remove special characters, keep only alphanumeric and spaces
    title = re.sub(r'[^a-zA-Z0-9\s]', ' ', title)
    
    # Replace multiple spaces with single space and strip
    title = re.sub(r'\s+', ' ', title).strip()
    
    return title

def calculate_title_similarity(title1, title2):
    """
    Calculate similarity between two titles using sequence matching.
    
    Args:
        title1 (str): First title
        title2 (str): Second title
        
    Returns:
        float: Similarity ratio between 0 and 1
    """
    # Clean both titles
    clean_title1 = clean_title(title1)
    clean_title2 = clean_title(title2)
    
    # If either title is empty, return 0 similarity
    if not clean_title1 or not clean_title2:
        return 0.0
    
    # Calculate similarity using SequenceMatcher
    similarity = SequenceMatcher(None, clean_title1, clean_title2).ratio()
    
    return similarity

def extract_s2_data_from_csv(csv_filepath):
    """
    Read CSV file and extract s2_id and title columns.
    
    Args:
        csv_filepath (str): Path to the CSV file
        
    Returns:
        tuple: (DataFrame with s2_id and title, list of valid s2_ids)
    """
    try:
        if not os.path.exists(csv_filepath):
            print(f"Error: File '{csv_filepath}' does not exist.")
            return None, []
        
        # Read the CSV file
        df = pd.read_csv(csv_filepath)
        
        # Check if required columns exist
        required_cols = ['s2_id', 'title']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"Error: Required columns {missing_cols} not found in the CSV file.")
            print(f"Available columns: {list(df.columns)}")
            return None, []
        
        # Filter rows with valid s2_id (not null/empty)
        original_rows = len(df)
        df_filtered = df[df['s2_id'].notna() & (df['s2_id'].astype(str) != '') & (df['s2_id'].astype(str).str.strip() != '')]
        
        print(f"Successfully loaded {original_rows} rows from CSV file.")
        print(f"Rows with valid s2_id: {len(df_filtered)}")
        print(f"Rows filtered out (no s2_id): {original_rows - len(df_filtered)}")
        
        # Extract s2_ids for API requests
        s2_ids = df_filtered['s2_id'].tolist()
        
        return df_filtered, s2_ids
        
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return None, []

def batch_request_titles(api_key, s2_id_list, max_retries=3):
    """
    Make a batch request to Semantic Scholar API to get paper titles.
    
    Args:
        api_key (str): Semantic Scholar API key
        s2_id_list (list): List of s2_ids to fetch
        max_retries (int): Maximum number of retry attempts
    
    Returns:
        list: List of paper data dictionaries from the API
    """
    for attempt in range(max_retries + 1):
        try:
            r = requests.post(
                'https://api.semanticscholar.org/graph/v1/paper/batch',
                params={'fields': 'paperId,title'},
                headers={'x-api-key': api_key},
                json={"ids": s2_id_list},
                timeout=30
            )
            r.raise_for_status()
            return r.json()
            
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout, 
                requests.exceptions.RequestException) as e:
            
            if attempt < max_retries:
                wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4 seconds
                print(f"Request failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"Request failed after {max_retries + 1} attempts: {e}")
                print("Returning empty response to continue processing...")
                return [None] * len(s2_id_list)

def verify_titles_batch(df_batch, s2_ids_batch, api_key, similarity_threshold=0.5, log_file_handle=None):
    """
    Verify titles for a batch of papers and log mismatches.
    
    Args:
        df_batch (DataFrame): Batch of papers to verify
        s2_ids_batch (list): List of s2_ids for this batch
        api_key (str): Semantic Scholar API key
        similarity_threshold (float): Threshold below which to log mismatches
        log_file_handle: File handle for logging mismatches
        
    Returns:
        dict: Statistics about the verification
    """
    # Make API request for this batch
    api_response = batch_request_titles(api_key, s2_ids_batch)
    
    if api_response is None or len(api_response) == 0:
        print("No valid API response for this batch")
        return {'processed': 0, 'matched': 0, 'mismatched': 0, 'api_errors': len(s2_ids_batch)}
    
    stats = {'processed': 0, 'matched': 0, 'mismatched': 0, 'api_errors': 0}
    
    # Create mapping from s2_id to dataframe row
    s2_id_to_row = {}
    for idx, row in df_batch.iterrows():
        s2_id_to_row[row['s2_id']] = row
    
    # Process API response
    for i, paper_data in enumerate(api_response):
        if paper_data is None or not isinstance(paper_data, dict):
            stats['api_errors'] += 1
            if i < len(s2_ids_batch):
                s2_id = s2_ids_batch[i]
                if log_file_handle:
                    log_file_handle.write(f"API_ERROR,{s2_id},,No data returned from API\n")
            continue
        
        # Get paper data from API
        api_s2_id = paper_data.get('paperId', '')
        api_title = paper_data.get('title', '')
        
        # Find corresponding row in dataframe
        if api_s2_id in s2_id_to_row:
            row = s2_id_to_row[api_s2_id]
            csv_title = row.get('title', '')
            
            # Calculate similarity
            similarity = calculate_title_similarity(csv_title, api_title)
            stats['processed'] += 1
            
            if similarity >= similarity_threshold:
                stats['matched'] += 1
            else:
                stats['mismatched'] += 1
                
                # Log the mismatch
                if log_file_handle:
                    log_file_handle.write(f"MISMATCH,{api_s2_id},{similarity:.3f},\"{csv_title}\",\"{api_title}\"\n")
                    log_file_handle.flush()  # Ensure data is written immediately
                
                print(f"MISMATCH (similarity: {similarity:.1%})")
                print(f"  S2 ID: {api_s2_id}")
                print(f"  CSV Title: {csv_title}")
                print(f"  API Title: {api_title}")
                print()
    
    return stats

def process_title_verification(df, s2_ids, api_key, batch_size=500, delay=2, similarity_threshold=0.5):
    """
    Process title verification in batches and log mismatches.
    
    Args:
        df (DataFrame): DataFrame with paper data
        s2_ids (list): List of s2_ids to verify
        api_key (str): Semantic Scholar API key
        batch_size (int): Number of papers to process per batch
        delay (int): Delay in seconds between requests
        similarity_threshold (float): Threshold below which to log mismatches
        
    Returns:
        dict: Overall statistics
    """
    total_papers = len(s2_ids)
    total_batches = (total_papers + batch_size - 1) // batch_size
    
    # Create log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filepath = f"logs/title_mismatches_{timestamp}.txt"
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Overall statistics
    overall_stats = {'processed': 0, 'matched': 0, 'mismatched': 0, 'api_errors': 0}
    
    print(f"\nProcessing {total_papers} papers in {total_batches} batches of {batch_size}")
    print(f"Similarity threshold: {similarity_threshold:.1%}")
    print(f"Mismatches will be logged to: {log_filepath}")
    
    with open(log_filepath, 'w', encoding='utf-8') as log_file:
        # Write header
        log_file.write("Type,S2_ID,Similarity,CSV_Title,API_Title\n")
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_papers)
            
            # Get batch data
            batch_s2_ids = s2_ids[start_idx:end_idx]
            df_batch = df[df['s2_id'].isin(batch_s2_ids)]
            
            print(f"\n--- Batch {batch_num + 1}/{total_batches} ---")
            print(f"Processing papers {start_idx + 1} to {end_idx} ({len(batch_s2_ids)} papers)")
            
            # Verify titles for this batch
            batch_stats = verify_titles_batch(df_batch, batch_s2_ids, api_key, similarity_threshold, log_file)
            
            # Update overall statistics
            for key in overall_stats:
                overall_stats[key] += batch_stats[key]
            
            print(f"Batch results: {batch_stats['matched']} matched, {batch_stats['mismatched']} mismatched, {batch_stats['api_errors']} API errors")
            
            # Add delay between requests (except for the last batch)
            if batch_num < total_batches - 1:
                print(f"Waiting {delay} seconds before next batch...")
                time.sleep(delay)
    
    print(f"\nTitle verification complete. Mismatches logged to: {log_filepath}")
    return overall_stats

def main():
    """Main function to run the title verification script."""
    csv_filepath = "revised_data/dblp_paper_ids.csv"
    S2_API_KEY = "39B73CXWua7xhzGlxFrNJ5wY6uIjXCna9sLxWL2w"
    SIMILARITY_THRESHOLD = 0.5  # 50% similarity threshold
    
    print("=" * 80)
    print("SEMANTIC SCHOLAR TITLE VERIFICATION")
    print("=" * 80)
    print(f"Reading from: {csv_filepath}")
    print(f"Similarity threshold: {SIMILARITY_THRESHOLD:.1%}")
    
    # Extract s2_ids and titles from CSV
    df, s2_ids = extract_s2_data_from_csv(csv_filepath)
    
    if df is None or len(s2_ids) == 0:
        print("Failed to extract s2_ids or load dataframe. Exiting.")
        return
    
    # Process title verification
    stats = process_title_verification(
        df, 
        s2_ids, 
        S2_API_KEY, 
        batch_size=500, 
        delay=1,  # 1 second delay between batches
        similarity_threshold=SIMILARITY_THRESHOLD
    )
    
    # Print final summary
    print("\n" + "="*80)
    print("FINAL VERIFICATION SUMMARY:")
    print("="*80)
    
    total_processed = stats['processed']
    total_matched = stats['matched']
    total_mismatched = stats['mismatched']
    total_api_errors = stats['api_errors']
    
    print(f"Total papers processed: {total_processed}")
    print(f"Titles matched (≥{SIMILARITY_THRESHOLD:.1%} similarity): {total_matched} ({total_matched/total_processed*100:.1f}%)")
    print(f"Titles mismatched (<{SIMILARITY_THRESHOLD:.1%} similarity): {total_mismatched} ({total_mismatched/total_processed*100:.1f}%)")
    print(f"API errors: {total_api_errors}")
    
    if total_mismatched > 0:
        print(f"\nCheck the log file in the 'logs/' directory for detailed mismatch information.")

if __name__ == "__main__":
    main()
