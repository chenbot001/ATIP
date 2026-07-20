import pandas as pd
import os
import requests
import time

def extract_paper_ids_from_dataframe(df):
    """
    Extract paper IDs (ACL IDs and DOIs) from a dataframe and format them for API requests.
    
    Args:
        df (DataFrame): Dataframe with acl_id and doi columns
        
    Returns:
        list: List of paper ID values as strings with appropriate prefixes
    """
    paper_ids = []
    
    for idx, row in df.iterrows():
        # Check if ACL ID exists and is not empty
        if pd.notna(row['acl_id']) and str(row['acl_id']).strip() != '':
            paper_ids.append('ACL:' + str(row['acl_id']))
        # Check if DOI exists and is not empty
        elif pd.notna(row['doi']) and str(row['doi']).strip() != '':
            paper_ids.append('DOI:' + str(row['doi']))
        else:
            # If neither ACL ID nor DOI exists, append None to maintain index correspondence
            paper_ids.append(None)
    
    return paper_ids

def extract_paper_ids(csv_filepath):
    """
    Read a CSV file and extract paper ID column values (ACL IDs and DOIs).
    
    Args:
        csv_filepath (str): Path to the CSV file
        
    Returns:
        tuple: (list of paper ID values as strings with appropriate prefixes, DataFrame)
    """
    try:
        # Check if file exists
        if not os.path.exists(csv_filepath):
            print(f"Error: File '{csv_filepath}' does not exist.")
            return [], None
        
        # Read the entire CSV file
        df = pd.read_csv(csv_filepath)
        
        # Check if required columns exist
        required_cols = ['acl_id', 'doi']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"Error: Required columns {missing_cols} not found in the CSV file.")
            print(f"Available columns: {list(df.columns)}")
            return [], None
        
        # Filter DataFrame to only include rows with valid paper IDs (ACL ID or DOI)
        original_rows = len(df)
        df_filtered = df[
            (df['acl_id'].notna() & (df['acl_id'].astype(str) != '') & (df['acl_id'].astype(str).str.strip() != '')) |
            (df['doi'].notna() & (df['doi'].astype(str) != '') & (df['doi'].astype(str).str.strip() != ''))
        ]
        
        # Extract paper ID values from filtered DataFrame
        paper_ids = extract_paper_ids_from_dataframe(df_filtered)
        
        print(f"Successfully loaded {original_rows} rows from CSV file.")
        print(f"Rows with valid paper IDs: {len(df_filtered)}")
        print(f"Rows filtered out (no paper ID): {original_rows - len(df_filtered)}")
        print(f"Total paper ID values to process: {len(paper_ids)}")
        
        # Count ACL IDs vs DOIs
        acl_count = df_filtered['acl_id'].notna().sum()
        doi_count = df_filtered['doi'].notna().sum()
        print(f"Papers with ACL IDs: {acl_count}")
        print(f"Papers with DOIs: {doi_count}")
        
        return paper_ids, df_filtered
        
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return [], None

def batch_request(api_key, id_list, max_retries=3):
    """
    Make a batch request to Semantic Scholar API for multiple paper IDs with retry logic
    
    Args:
        api_key (str): Semantic Scholar API key
        id_list (list): List of paper IDs to fetch
        max_retries (int): Maximum number of retry attempts
    
    Returns:
        dict: JSON response from the API
    """
    for attempt in range(max_retries + 1):
        try:
            r = requests.post(
                'https://api.semanticscholar.org/graph/v1/paper/batch',
                params={'fields': 'paperId,corpusId,externalIds'},
                headers={'x-api-key': api_key},
                json={"ids": id_list},
                timeout=30  # Add timeout to prevent hanging requests
            )
            r.raise_for_status()  # Raise exception for HTTP error status codes
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
                return [None] * len(id_list)  # Return None for each ID to skip this batch

def populate_dataframe(df, api_response, paper_ids):
    """
    Populate the dataframe with data from the API response.
    
    Args:
        df (DataFrame): Original dataframe with acl_id and doi columns
        api_response (list): List of dictionaries from the API response
        paper_ids (list): List of paper IDs that were sent in the request
        
    Returns:
        DataFrame: Updated dataframe with new columns populated
    """
    # Add new columns if they don't exist
    if 'corpus_id' not in df.columns:
        df['corpus_id'] = pd.Series(dtype='Int64')  # Use nullable integer dtype
    if 's2_id' not in df.columns:
        df['s2_id'] = None

    # Ensure corpus_id column is Int64 dtype
    if df['corpus_id'].dtype != 'Int64':
        df['corpus_id'] = df['corpus_id'].astype('Int64')
    
    # Create a mapping from paper ID to row index for quick lookup
    id_to_index = {}
    for idx, row in df.iterrows():
        # Create lookup keys for both ACL ID and DOI
        if pd.notna(row['acl_id']) and str(row['acl_id']).strip() != '':
            clean_acl_id = str(row['acl_id']).replace('ACL:', '')
            id_to_index[clean_acl_id] = idx
        if pd.notna(row['doi']) and str(row['doi']).strip() != '':
            clean_doi = str(row['doi']).replace('DOI:', '')
            # Store DOI in lowercase for case-insensitive matching
            id_to_index[clean_doi.lower()] = idx
    
    # Iterate through API response and populate dataframe
    for i, paper_data in enumerate(api_response):
        if paper_data is None:
            continue
            
        # Handle case where paper_data might be a string instead of dict
        if not isinstance(paper_data, dict):
            print(f"Warning: Skipping non-dict paper data: {type(paper_data)} - {paper_data}")
            continue
            
        # Extract external IDs
        external_ids = paper_data.get('externalIds', {})
        api_acl_id = external_ids.get('ACL')
        api_doi = external_ids.get('DOI')
        
        # Debug: Print what we got from API and check if it was in our request
        paper_id = paper_data.get('paperId', 'Unknown')
        requested_id = paper_ids[i] if i < len(paper_ids) else "Index out of range"
        
        # Find the corresponding row in the dataframe
        row_idx = None
        matched_id = None
        search_was_acl = False
        
        if api_acl_id and api_acl_id in id_to_index:
            row_idx = id_to_index[api_acl_id]
            matched_id = f"ACL:{api_acl_id}"
            search_was_acl = True
        elif api_doi and api_doi.lower() in id_to_index:
            row_idx = id_to_index[api_doi.lower()]
            matched_id = f"DOI:{api_doi}"
            search_was_acl = False
        
        if row_idx is not None:
            # Get corpusId and convert to integer if it exists
            corpus_id = paper_data.get('corpusId')
            if corpus_id is not None:
                corpus_id = int(corpus_id)
            
            # Always populate s2_id and corpus_id
            df.at[row_idx, 'corpus_id'] = corpus_id
            df.at[row_idx, 's2_id'] = paper_data.get('paperId')
            
            # Fill missing identifiers based on search type:
            # If search was by ACL ID, fill missing DOI (if available from API)
            if search_was_acl and api_doi and (pd.isna(df.at[row_idx, 'doi']) or str(df.at[row_idx, 'doi']).strip() == ''):
                df.at[row_idx, 'doi'] = api_doi
            
            # If search was by DOI, fill missing ACL ID (if available from API)
            if not search_was_acl and api_acl_id and (pd.isna(df.at[row_idx, 'acl_id']) or str(df.at[row_idx, 'acl_id']).strip() == ''):
                df.at[row_idx, 'acl_id'] = api_acl_id
            
        else:
            if api_acl_id or api_doi:
                unmatched_id = api_acl_id if api_acl_id else api_doi
                print(f"No match found for ID: {unmatched_id}")
            else:
                print(f"No ACL ID or DOI found in paper data: {paper_data.get('paperId', 'Unknown')}")
    
    # Ensure corpus_id column maintains Int64 dtype after updates
    df['corpus_id'] = df['corpus_id'].astype('Int64')
    
    return df

def process_in_batches(df, paper_ids, api_key, batch_size=500, delay=2):
    """
    Process the dataframe in batches, making API requests for each batch.
    
    Args:
        df (DataFrame): Dataframe to populate
        paper_ids (list): List of all paper IDs (ACL IDs and DOIs)
        api_key (str): Semantic Scholar API key
        batch_size (int): Number of papers to process per batch
        delay (int): Delay in seconds between requests
        
    Returns:
        DataFrame: Updated dataframe
    """
    # Filter out None values from paper_ids for API requests
    valid_paper_ids = [pid for pid in paper_ids if pid is not None]
    total_papers = len(valid_paper_ids)
    total_batches = (total_papers + batch_size - 1) // batch_size  # Ceiling division
    save_interval = 5  # Save every 5 batches
    
    print(f"\nProcessing {total_papers} papers in {total_batches} batches of {batch_size}")
    print(f"Will save progress every {save_interval} batches")

    # total_batches = 1
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_papers)
        
        batch_ids = valid_paper_ids[start_idx:end_idx]
        
        print(f"\n--- Batch {batch_num + 1}/{total_batches} ---")
        print(f"Processing papers {start_idx + 1} to {end_idx} ({len(batch_ids)} papers)")
        
        # Make API request for this batch
        response = batch_request(api_key, batch_ids)
        if response is not None:
            print(f"API Response received with {len(response)} papers")
        else:
            print("API Response was None - skipping this batch")
            continue
        
        # Populate dataframe with this batch's data
        df = populate_dataframe(df, response, batch_ids)
        
        # Save incrementally every 5 batches (or on the last batch)
        if (batch_num + 1) % save_interval == 0 or batch_num == total_batches - 1:
            temp_output_filepath = "revised_data/paper_ids_temp.csv"
            df.to_csv(temp_output_filepath, index=False)
            print(f"✓ Progress saved to {temp_output_filepath} (Batch {batch_num + 1}/{total_batches})")
        
        # Add delay between requests (except for the last batch)
        if batch_num < total_batches - 1:
            print(f"Waiting {delay} second before next batch...")
            time.sleep(delay)
    
    return df

def main():
    """Main function to run the script."""
    # Updated filepath to point to paper_ids data with ACL IDs and DOIs
    csv_filepath = "revised_data/dblp_paper_ids.csv"
    S2_API_KEY = "39B73CXWua7xhzGlxFrNJ5wY6uIjXCna9sLxWL2w"

    print(f"Reading from: {csv_filepath}")
    paper_ids, paper_info = extract_paper_ids(csv_filepath)
    
    if not paper_ids or paper_info is None:
        print("Failed to extract paper IDs or load dataframe. Exiting.")
        return
    
    if len(paper_info) == 0:
        print("No papers with valid paper IDs found. Exiting.")
        return
    
    # Process the filtered dataframe (only papers with valid paper IDs) in batches
    updated_df = process_in_batches(paper_info, paper_ids, S2_API_KEY, batch_size=500, delay=1)
    
    # Create output dataframe with requested columns
    output_df = pd.DataFrame({
        'dblp_id': updated_df['dblp_key'],
        'title': updated_df['title'],
        'author_count': updated_df['author_count'],
        's2_id': updated_df['s2_id'],
        'corpus_id': updated_df['corpus_id'],
        'acl_id': updated_df['acl_id'],
        'DOI': updated_df['doi']  # Use the original 'doi' column from input, not 'DOI'
    })
    
    # Show summary of populated data with fill rates
    print("\n" + "="*80)
    print("FINAL SUMMARY:")
    print("="*80)
    total_rows = len(output_df)
    print(f"Total rows: {total_rows}")
    
    # Calculate fill rates for each column
    s2_id_filled = output_df['s2_id'].notna().sum()
    corpus_id_filled = output_df['corpus_id'].notna().sum()
    acl_id_filled = output_df['acl_id'].notna().sum()
    doi_filled = output_df['DOI'].notna().sum()
    
    # Calculate failed searches (rows where no new data was added from API)
    # Failed searches are rows where both s2_id and corpus_id are missing
    failed_searches = output_df['s2_id'].isna().sum()
    
    print(f"Rows with s2_id: {s2_id_filled} (Fill rate: {s2_id_filled/total_rows*100:.1f}%)")
    print(f"Rows with corpus_id: {corpus_id_filled} (Fill rate: {corpus_id_filled/total_rows*100:.1f}%)")
    print(f"Rows with ACL ID: {acl_id_filled} (Fill rate: {acl_id_filled/total_rows*100:.1f}%)")
    print(f"Rows with DOI: {doi_filled} (Fill rate: {doi_filled/total_rows*100:.1f}%)")
    print(f"Failed searches (no API data): {failed_searches} ({failed_searches/total_rows*100:.1f}%)")
    
    # Save the output dataframe to paper_ids.csv
    output_filepath = "revised_data/dblp_paper_ids_new.csv"
    output_df.to_csv(output_filepath, index=False)
    print(f"\nDataframe saved to: {output_filepath}")
    print(f"Output columns: {list(output_df.columns)}")

if __name__ == "__main__":
    main()
