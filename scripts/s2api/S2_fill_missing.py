import pandas as pd
import numpy as np
import requests
import time
import json
from tqdm import tqdm


def test_missing_values(filepath, required_columns):
    """
    Test script to count rows with empty or None values in specified columns.

    Args:
        filepath (str): Path to the CSV file.
        required_columns (list): A list of column names to check for missing values.

    Returns:
        tuple: A tuple containing the DataFrame and the boolean mask of empty rows, or (None, None) on error.
    """
    try:
        # Load the specified CSV file
        print(f"Loading {filepath}...")
        df = pd.read_csv(filepath)
        
        print(f"Total rows in dataset: {len(df)}")
        print(f"Columns in dataset: {list(df.columns)}")
        
        # Check if the required columns exist
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"Warning: Missing columns: {missing_columns}")
            return None, None
        
        # Create a combined mask for all required columns
        final_empty_mask = pd.Series([False] * len(df), index=df.index)

        for col in required_columns:
            base_mask = (
                df[col].isna() |
                (df[col].astype(str).str.strip() == '') |
                (df[col].astype(str).str.strip() == 'nan')
            )
            # Special case: 'corpus_id' value of 0 is also considered empty
            if col == 'corpus_id':
                base_mask |= (df[col] == 0)
            
            final_empty_mask |= base_mask

        rows_with_empty_values = final_empty_mask.sum()
        
        print(f"\nResults:")
        print(f"Rows with empty or None values in any of {required_columns}: {rows_with_empty_values}")
        print(f"Percentage of rows with missing values: {(rows_with_empty_values / len(df)) * 100:.2f}%")
        
        # Show breakdown by column
        print(f"\nBreakdown by column:")
        for col in required_columns:
            col_mask = (
                df[col].isna() |
                (df[col].astype(str).str.strip() == '') |
                (df[col].astype(str).str.strip() == 'nan')
            )
            if col == 'corpus_id':
                 col_mask |= (df[col] == 0)
            
            col_empty = col_mask.sum()
            print(f"  {col}: {col_empty} empty values ({col_empty/len(df)*100:.2f}%)")
        
        return df, final_empty_mask
        
    except FileNotFoundError:
        print(f"Error: {filepath} not found.")
        return None, None
    except Exception as e:
        print(f"Error: {e}")
        return None, None


def fix_dupes(df, api_key):
    """
    Identifies and handles duplicate s2_ids.
    1. Removes rows where both s2_id and title are identical.
    2. For remaining dupes (same s2_id, different title), searches by title for each row.
    3. Updates rows based on API results: match current data (no change), different IDs (update), or no result (set to defaults).
    """
    print("\nStarting duplicate check and correction process...")
    dupe_mask = df.duplicated(subset=['s2_id'], keep=False) & df['s2_id'].notna()
    # Ensure the mask is boolean
    dupe_mask = dupe_mask.astype(bool)
    s2_ids_to_check = df[dupe_mask]['s2_id'].unique()
    
    if len(s2_ids_to_check) == 0:
        print("✅ No duplicate s2_ids found. Skipping correction.")
        return df
        
    print(f"Found {len(s2_ids_to_check)} s2_ids with duplicate entries. Verifying...")
    
    # --- Take a snapshot of the initial state of all duplicate rows ---
    initial_dupe_rows = df[dupe_mask].copy()
    
    df_corrected = df.copy()
    api_corrected_count = 0
    api_not_found_count = 0
    title_dupes_removed_count = 0

    # Loop to attempt corrections
    for s2_id in tqdm(s2_ids_to_check, desc="Fixing Duplicates"):
        # --- 1. Handle rows with IDENTICAL TITLES first ---
        dupe_group = df_corrected[df_corrected['s2_id'] == s2_id]
        title_dupe_mask = dupe_group.duplicated(subset=['title'], keep='first')
        indices_to_drop = dupe_group[title_dupe_mask].index

        if not indices_to_drop.empty:
            df_corrected.drop(indices_to_drop, inplace=True)
            title_dupes_removed_count += len(indices_to_drop)
        
        # --- 2. For remaining dupes (same ID, different titles), search by title for each row ---
        # Re-evaluate the group after potential removals
        dupe_group_after_cleanup = df_corrected[df_corrected['s2_id'] == s2_id]
        
        # Process each row in the duplicate group
        for idx, row in dupe_group_after_cleanup.iterrows():
            title = row.get('title')
            if pd.isna(title) or not title.strip():
                continue

            api_result = search_by_title(api_key, title)
            time.sleep(1) 

            if api_result and api_result.get('paperId'):
                # API returned a result - check if it matches current data
                api_s2_id = api_result.get('paperId')
                api_corpus_id = api_result.get('corpusId')
                api_doi = api_result.get('externalIds', {}).get('DOI')
                
                current_s2_id = str(row['s2_id'])
                current_corpus_id = str(row['corpus_id']) if not pd.isna(row['corpus_id']) else ''
                current_doi = str(row.get('DOI', '')) if not pd.isna(row.get('DOI', '')) else ''
                
                # Check if the returned IDs match the current row data
                s2_id_matches = current_s2_id == str(api_s2_id)
                corpus_id_matches = current_corpus_id == str(api_corpus_id) if api_corpus_id else current_corpus_id == ''
                doi_matches = current_doi == str(api_doi) if api_doi else current_doi == ''
                
                if s2_id_matches and corpus_id_matches and doi_matches:
                    # IDs match current data - do nothing
                    pass
                else:
                    # IDs don't match - update with correct values
                    df_corrected.at[idx, 's2_id'] = api_s2_id
                    df_corrected.at[idx, 'corpus_id'] = api_corpus_id
                    
                    if 'DOI' in df_corrected.columns:
                        df_corrected.at[idx, 'DOI'] = api_doi
                    
                    api_corrected_count += 1
            else:
                # API returned no result - set to default values
                df_corrected.at[idx, 'corpus_id'] = 0
                df_corrected.at[idx, 's2_id'] = ''
                
                if 'DOI' in df_corrected.columns:
                    df_corrected.at[idx, 'DOI'] = ''
                
                api_not_found_count += 1

    print(f"\nDuplicate check complete!")
    if title_dupes_removed_count > 0:
        print(f"✅ Removed {title_dupes_removed_count} redundant entries with identical titles.")
    if api_corrected_count > 0:
        print(f"✅ Corrected {api_corrected_count} rows with incorrect ID assignments via API.")
    if api_not_found_count > 0:
        print(f"⚠️ Set {api_not_found_count} rows to default values (paper not found on Semantic Scholar).")
    if title_dupes_removed_count == 0 and api_corrected_count == 0 and api_not_found_count == 0:
        print("No rows required correction or removal.")


    # --- 3. Debugging: Compare final state to initial state for remaining dupes ---
    un_updated_dupes = []
    # Get the final state of the rows that were initially identified as duplicates
    final_dupe_rows = df_corrected.loc[df_corrected.index.intersection(initial_dupe_rows.index)]

    for idx, initial_row in initial_dupe_rows.iterrows():
        # Check if the row still exists in the corrected dataframe
        if idx in final_dupe_rows.index:
            final_row = final_dupe_rows.loc[idx]
            
            s2_id_same = str(initial_row['s2_id']) == str(final_row['s2_id'])
            corpus_id_same = str(initial_row['corpus_id']) == str(final_row['corpus_id'])
            doi_same = str(initial_row.get('DOI')) == str(final_row.get('DOI'))

            if s2_id_same and corpus_id_same and doi_same:
                un_updated_dupes.append({
                    'index': idx,
                    's2_id': initial_row['s2_id'],
                    'title': initial_row['title']
                })

    if un_updated_dupes:
        print("\n" + "="*50)
        print("⚠️ DEBUGGING: Summary of Un-updated Duplicate Rows")
        print("="*50)
        print(f"The following {len(un_updated_dupes)} rows were part of a duplicate group but were not changed:")
        for item in un_updated_dupes:
            print(f"\n  - Row Index: {item['index']}")
            print(f"    - s2_id: {item['s2_id']}")
            print(f"    - Title: {str(item['title'])}")
    print("="*50)
    
    return df_corrected

def search_by_title(api_key, title):
    """
    Search for a paper by title using Semantic Scholar API
    
    Args:
        api_key (str): Semantic Scholar API key
        title (str): Paper title to search for
    
    Returns:
        dict: Paper information if found, None otherwise
    """
    try:
        r = requests.get(
            'https://api.semanticscholar.org/graph/v1/paper/search',
            headers={'x-api-key': api_key},
            params={
                'query': title,
                'limit': 1,
                'fields': 'paperId,corpusId,externalIds'
            },
            timeout=10
        )
        
        if r.status_code == 200:
            response = r.json()
            if response.get('data') and len(response['data']) > 0:
                paper = response['data'][0]
                return {
                    'paperId': paper.get('paperId'),
                    'corpusId': paper.get('corpusId'),
                    'externalIds': paper.get('externalIds', {})
                }
        return None
    except Exception as e:
        print(f"Error searching for title '{title[:50]}...': {e}")
        return None

def fill_missing_values(df, empty_mask, api_key):
    """
    Fill missing values by searching Semantic Scholar API
    
    Args:
        df (pd.DataFrame): DataFrame with paper information
        empty_mask (pd.Series): Boolean mask of rows with missing values
        api_key (str): Semantic Scholar API key
    
    Returns:
        pd.DataFrame: Updated DataFrame with filled values
    """
    print(f"\nStarting to fill missing values for {empty_mask.sum()} rows...")
    
    # Create a copy to avoid modifying the original
    df_updated = df.copy()
    filled_count = 0
    error_count = 0
    
    # Get rows with missing values
    missing_rows = df_updated[empty_mask].copy()
    
    try:
        for idx, row in tqdm(missing_rows.iterrows(), total=len(missing_rows), desc="Filling missing values"):
            try:
                title = row['title']
                if pd.isna(title) or str(title).strip() == '':
                    # This print is commented out to reduce noise, but can be enabled for debugging.
                    # print(f"Row {idx}: Skipping - no title available")
                    continue
                    
                # Search for the paper
                result = search_by_title(api_key, title)
                
                if result:
                    # Update missing values
                    updated = False
                    
                    # Fill corpus_id if missing or 0
                    if pd.isna(df_updated.at[idx, 'corpus_id']) or str(df_updated.at[idx, 'corpus_id']).strip() in ['', 'nan', '0']:
                        if result.get('corpusId'):
                            df_updated.at[idx, 'corpus_id'] = result['corpusId']
                            updated = True
                    
                    # Fill s2_id if missing
                    if pd.isna(df_updated.at[idx, 's2_id']) or str(df_updated.at[idx, 's2_id']).strip() in ['', 'nan']:
                        if result.get('paperId'):
                            df_updated.at[idx, 's2_id'] = result['paperId']
                            updated = True
                    
                    # Fill DOI if missing
                    if 'DOI' in df_updated.columns and (pd.isna(df_updated.at[idx, 'DOI']) or str(df_updated.at[idx, 'DOI']).strip() in ['', 'nan']):
                        external_ids = result.get('externalIds', {})
                        if external_ids.get('DOI'):
                            df_updated.at[idx, 'DOI'] = external_ids['DOI']
                            updated = True
                    
                    if updated:
                        filled_count += 1

                time.sleep(1)
                
            except Exception as e:
                error_count += 1
                print(f"Row {idx}: Error processing - {e}")
                continue
                
    except KeyboardInterrupt:
        print(f"\n\nKeyboard interrupt detected! Saving current progress...")
        print(f"Processed {filled_count} rows successfully before interruption")
        print(f"Encountered {error_count} errors before interruption")
        
        # Save the current progress
        try:
            save_updated_dataframe(df_updated, 'paper_info_updated.csv')
            print("Current progress saved to 'paper_info_updated.csv'")
        except Exception as save_error:
            print(f"Error saving interrupted progress: {save_error}")
        
        return df_updated
    
    print(f"\nFilling complete!")
    print(f"Successfully filled: {filled_count} rows")
    print(f"Errors encountered: {error_count} rows")
    
    return df_updated

def save_updated_dataframe(df, filename='paper_info_updated.csv'):
    """
    Save the updated DataFrame to a new CSV file
    
    Args:
        df (pd.DataFrame): DataFrame to save
        filename (str): Output filename
    """
    try:
        output_path = f'./data/{filename}'
        df.to_csv(output_path, index=False)
        print(f"\nUpdated data saved to: {output_path}")
    except Exception as e:
        print(f"Error saving file: {e}")

if __name__ == "__main__":
    # --- Script Configuration ---
    API_KEY = "39B73CXWua7xhzGlxFrNJ5wY6uIjXCna9sLxWL2w" # Replace with your actual key if needed
    FILE_PATH = './data/paper_info.csv'
    # Columns to check for missing values to trigger the fill process
    INITIAL_CHECK_COLUMNS = ['corpus_id', 's2_id']
    # Columns to check for the final statistics report
    FINAL_CHECK_COLUMNS = ['corpus_id', 's2_id', 'DOI']
    # --------------------------

    # --- Load Data ---
    try:
        df = pd.read_csv(FILE_PATH)
        print(f"✅ Successfully loaded {FILE_PATH}. Total rows: {len(df)}")
    except FileNotFoundError:
        print(f"❌ Error: {FILE_PATH} not found. Exiting.")
        exit()
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        exit()

    # --- Step 1: Fix Duplicates (Optional) ---
    response_dupes = input("\nDo you want to check for and fix duplicate IDs? (y/n): ")
    if response_dupes.lower() in ['y', 'yes']:
        df = fix_dupes(df, API_KEY)
    else:
        print("Skipping duplicate check.")
    
    # df is now updated in memory if duplicates were fixed.

    # --- Step 2: Fill Missing Values (Optional) ---
    print("\n" + "="*50)
    print("ANALYZING FOR MISSING VALUES (Post-Dupe-Fix):")
    print("="*50)
    
    # Manually calculate the mask on the current dataframe
    empty_mask = pd.Series([False] * len(df), index=df.index)
    for col in INITIAL_CHECK_COLUMNS:
        base_col_mask = (df[col].isna() | (df[col].astype(str).str.strip() == '') | (df[col].astype(str).str.strip() == 'nan'))
        if col == 'corpus_id':
            base_col_mask |= (df[col] == 0)
        empty_mask |= base_col_mask
    
    rows_with_empty_values = empty_mask.sum()
    print(f"Found {rows_with_empty_values} rows with missing values in {INITIAL_CHECK_COLUMNS}.")
    
    df_final = df.copy() # Start with the current version of the dataframe

    if rows_with_empty_values > 0:
        response_fill = input("Do you want to attempt to fill them using the Semantic Scholar API? (y/n): ")
        if response_fill.lower() in ['y', 'yes']:
            df_final = fill_missing_values(df, empty_mask, API_KEY)
        else:
            print("Skipping missing value filling.")
    else:
        print("✅ No missing values to fill.")

    # --- Step 3: Final Statistics and Save ---
    print("\n" + "="*50)
    print("FINAL STATISTICS:")
    print("="*50)
    
    # Recalculate missing values across all target columns for the final report
    final_empty_mask_updated = pd.Series([False] * len(df_final), index=df_final.index)
    for col in FINAL_CHECK_COLUMNS:
         if col in df_final.columns:
            base_mask = (df_final[col].isna() | (df_final[col].astype(str).str.strip() == '') | (df_final[col].astype(str).str.strip() == 'nan'))
            if col == 'corpus_id':
                base_mask |= (df_final[col] == 0)
            final_empty_mask_updated |= base_mask

    rows_with_empty_values_updated = final_empty_mask_updated.sum()
    print(f"Total rows with empty or None values after all operations: {rows_with_empty_values_updated}")
    if len(df_final) > 0:
        print(f"Percentage of rows with missing values: {(rows_with_empty_values_updated / len(df_final)) * 100:.2f}%")
    
    # Show final breakdown by column
    print(f"\nBreakdown by column:")
    for col in FINAL_CHECK_COLUMNS:
        if col in df_final.columns:
            col_mask = (df_final[col].isna() | (df_final[col].astype(str).str.strip() == '') | (df_final[col].astype(str).str.strip() == 'nan'))
            if col == 'corpus_id':
                col_mask |= (df_final[col] == 0)

            col_empty = col_mask.sum()
            if len(df_final) > 0:
                print(f"  - {col}: {col_empty} empty values ({col_empty/len(df_final)*100:.2f}%)")

    # Save the final, cleaned data
    save_updated_dataframe(df_final)