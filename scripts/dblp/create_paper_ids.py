#!/usr/bin/env python3
"""
Paper IDs Collection Script

This script creates a comprehensive paper_ids.csv file by extracting IDs directly
from the ee (external URL) column in DBLP paper data.        print("="*80)
        print("PAPER IDS COLLECTION SUMMARY")
        print("="*80)
        print(f"Total papers processed: {len(paper_ids_df):,}")
        print(f"Papers with ACL IDs: {papers_with_acl_ids:,}")
        print(f"Papers with DOIs: {papers_with_dois:,}")
        print(f"Papers with any ID: {papers_with_any_id:,}")
        print(f"Papers without extracted IDs: {papers_without_ids:,}")
        print(f"ID extraction success rate: {id_extraction_percentage:.1f}%")
        print(f"Average author count: {author_stats['mean']:.2f}")
        print("")
        print("ID Type Distribution:")
        print(f"  ACL Anthology (legacy): {len(acl_anthology_ids):,}")
        print(f"  DOI URLs: {len(doi_ids):,}")
        print(f"  Modern ACL format: {len(modern_acl_ids):,}")
        print(f"Output file: {OUTPUT_FILE}")
        print(f"Output columns: {list(paper_ids_df.columns)}")
        print("="*80) ACL Anthology
URLs and DOI URLs to extract the appropriate identifiers.

The output includes dblp_key, title, author_count, acl_id, and doi columns
(where acl_id contains ACL Anthology paper IDs and doi contains DOI identifiers).

Author: AI Assistant  
Date: August 13, 2025
"""

import pandas as pd
import ast
import logging
import os
import urllib.parse
import re
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_id_from_url(url):
    """
    Extract the appropriate ID from ee URL based on the domain.
    
    Args:
        url (str): The URL from the ee column
        
    Returns:
        tuple: (acl_id, doi) where one is the extracted ID and the other is None
    """
    try:
        if pd.isna(url) or not isinstance(url, str):
            return None, None
            
        # Parse the URL
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path
        
        # Handle ACL Anthology URLs
        if 'aclanthology.org' in domain:
            # Extract the paper ID from the path (e.g., /P10-1077/ -> P10-1077)
            # Remove leading/trailing slashes and extract the paper ID
            paper_id = path.strip('/')
            if paper_id:
                return paper_id, None
            return None, None
            
        # Handle DOI URLs
        elif 'doi.org' in domain:
            # Extract DOI from path (e.g., /10.3115/1118149.1118159 -> 10.3115/1118149.1118159)
            if path.startswith('/'):
                doi = path[1:]  # Remove leading slash
                if doi:
                    return None, doi
            return None, None
            
        else:
            # Unknown domain
            return None, None
            
    except Exception as e:
        logger.warning(f"Error extracting ID from URL {url}: {e}")
        return None, None

def count_authors(authors_data):
    """
    Count the number of authors from various author data formats.
    
    Args:
        authors_data: Author data in various formats (list, string, etc.)
        
    Returns:
        int: Number of authors
    """
    try:
        if pd.isna(authors_data):
            return 0
            
        if isinstance(authors_data, str):
            # Try to parse as list if it's a string representation
            try:
                authors_list = ast.literal_eval(authors_data)
                if isinstance(authors_list, list):
                    return len(authors_list)
                else:
                    return 1
            except:
                # If parsing fails, count by splitting on common delimiters
                # Remove brackets and quotes, then split by comma
                cleaned = str(authors_data).strip('[]"\'').replace("'", "").replace('"', '')
                authors = [a.strip() for a in cleaned.split(',') if a.strip()]
                return len(authors)
                
        elif isinstance(authors_data, list):
            return len(authors_data)
        else:
            return 1
            
    except Exception as e:
        logger.warning(f"Error counting authors for {authors_data}: {e}")
        return 0
    
def create_paper_ids_csv():
    """
    Create a comprehensive paper_ids.csv file with dblp_key, title, author_count, and ee_id.
    
    Procedure:
    1) Load DBLP papers data
    2) Extract dblp_key, title, and calculate author_count
    3) Extract ACL/DOI IDs directly from ee URLs
    4) Save the combined data to paper_ids.csv
    """
    
    # --- Configuration ---
    DBLP_FILE = os.path.join('revised_data', 'dblp_papers_nlp.csv')
    OUTPUT_FILE = os.path.join('revised_data', 'paper_ids.csv')
    
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    try:
        # --- 1. Load DBLP Data ---
        logger.info(f"Loading DBLP data from {DBLP_FILE}")
        dblp_df = pd.read_csv(DBLP_FILE)
        logger.info(f"Loaded {len(dblp_df):,} DBLP papers")
        
        # --- 2. Create Initial DataFrame with DBLP Data ---
        logger.info("Processing DBLP data...")
        
        # Create paper_ids dataframe with required columns
        paper_ids_df = pd.DataFrame({
            'dblp_key': dblp_df['key'],
            'title': dblp_df['title'],
            'author_count': dblp_df['authors'].apply(count_authors),
            'acl_id': None,  # Will be filled for ACL Anthology papers
            'doi': None      # Will be filled for DOI papers
        })
        
        logger.info(f"Created initial dataframe with {len(paper_ids_df):,} papers")
        
        # --- 3. Extract IDs from ee URLs ---
        logger.info("Extracting IDs from ee URLs...")
        
        # Extract IDs directly from the ee column
        extraction_results = dblp_df['ee'].apply(extract_id_from_url)
        
        # Separate ACL IDs and DOIs
        paper_ids_df['acl_id'] = extraction_results.apply(lambda x: x[0] if x else None)
        paper_ids_df['doi'] = extraction_results.apply(lambda x: x[1] if x else None)

        # Count how many papers have extracted IDs
        papers_with_acl_ids = paper_ids_df['acl_id'].notna().sum()
        papers_with_dois = paper_ids_df['doi'].notna().sum()
        papers_with_any_id = (paper_ids_df['acl_id'].notna() | paper_ids_df['doi'].notna()).sum()
        papers_without_ids = len(paper_ids_df) - papers_with_any_id
        id_extraction_percentage = (papers_with_any_id / len(paper_ids_df)) * 100
        
        logger.info(f"Papers with ACL IDs: {papers_with_acl_ids:,}")
        logger.info(f"Papers with DOIs: {papers_with_dois:,}")
        logger.info(f"Papers with any ID: {papers_with_any_id:,} ({id_extraction_percentage:.1f}%)")
        logger.info(f"Papers without extracted IDs: {papers_without_ids:,} ({100-id_extraction_percentage:.1f}%)")
        
        # --- 4. Analyze extracted ID types ---
        logger.info("Analyzing extracted ID types...")
        
        acl_anthology_ids = paper_ids_df[paper_ids_df['acl_id'].str.contains(r'^[A-Z]\d', na=False, regex=True)]
        doi_ids = paper_ids_df[paper_ids_df['doi'].str.contains(r'^10\.', na=False, regex=True)]
        modern_acl_ids = paper_ids_df[paper_ids_df['acl_id'].str.contains(r'^\d{4}\.', na=False, regex=True)]
        
        logger.info(f"ACL Anthology IDs (legacy format): {len(acl_anthology_ids):,}")
        logger.info(f"DOI IDs: {len(doi_ids):,}")
        logger.info(f"Modern ACL IDs: {len(modern_acl_ids):,}")
        
        # --- 5. Calculate Author Count Statistics ---
        author_stats = paper_ids_df['author_count'].describe()
        logger.info("Author count statistics:")
        logger.info(f"Mean: {author_stats['mean']:.2f}")
        logger.info(f"Median: {author_stats['50%']:.0f}")
        logger.info(f"Min: {author_stats['min']:.0f}, Max: {author_stats['max']:.0f}")
        
        # --- 6. Save the Results ---
        logger.info(f"Saving paper IDs to {OUTPUT_FILE}")
        paper_ids_df.to_csv(OUTPUT_FILE, index=False)
        
        # --- 7. Print Summary ---
        print("\n" + "="*80)
        print("PAPER IDS COLLECTION SUMMARY")
        print("="*80)
        print(f"Total papers processed: {len(paper_ids_df):,}")
        print(f"Papers with ACL IDs: {papers_with_acl_ids:,}")
        print(f"Papers with DOIs: {papers_with_dois:,}")
        print(f"Papers with any ID: {papers_with_any_id:,}")
        print(f"Papers without extracted IDs: {papers_without_ids:,}")
        print(f"ID extraction success rate: {id_extraction_percentage:.1f}%")
        print(f"Average author count: {author_stats['mean']:.2f}")
        print("")
        print("ID Type Distribution:")
        print(f"  ACL Anthology (legacy): {len(acl_anthology_ids):,}")
        print(f"  DOI URLs: {len(doi_ids):,}")
        print(f"  Modern ACL format: {len(modern_acl_ids):,}")
        print(f"Output file: {OUTPUT_FILE}")
        print(f"Output columns: {list(paper_ids_df.columns)}")
        print("="*80)
        
        # --- 8. Display Sample Results ---
        print("\nSample data (first 10 rows):")
        print(paper_ids_df.head(10).to_string(index=False))
        
        if papers_with_any_id > 0:
            print(f"\nSample papers with extracted IDs (first 5):")
            ids_mapped = paper_ids_df[(paper_ids_df['acl_id'].notna()) | (paper_ids_df['doi'].notna())].head(5)
            print(ids_mapped.to_string(index=False))
        
        # --- 9. Sample URLs and extracted IDs ---
        print(f"\nSample URL -> ID mappings:")
        sample_urls = dblp_df[['ee']].head(10)
        extraction_results_sample = dblp_df['ee'].head(10).apply(extract_id_from_url)
        for i, (url, (acl_id, doi)) in enumerate(zip(sample_urls['ee'], extraction_results_sample)):
            if acl_id:
                print(f"  {url} -> ACL ID: {acl_id}")
            elif doi:
                print(f"  {url} -> DOI: {doi}")
            else:
                print(f"  {url} -> No ID extracted")
            if i >= 4:  # Show only first 5
                break
        
        # --- 10. Author Count Distribution ---
        print(f"\nAuthor count distribution:")
        author_count_dist = paper_ids_df['author_count'].value_counts().sort_index()
        for count, freq in author_count_dist.head(10).items():
            print(f"  {count} author(s): {freq:,} papers")
        
        if len(author_count_dist) > 10:
            print(f"  ... and {len(author_count_dist) - 10} more categories")
        
        logger.info("Paper IDs collection completed successfully")
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Error creating paper IDs: {str(e)}")
        raise

def main():
    """Main function to execute the paper IDs collection."""
    logger.info("Starting paper IDs collection script")
    create_paper_ids_csv()

if __name__ == "__main__":
    main()
