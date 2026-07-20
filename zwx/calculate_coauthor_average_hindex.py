#!/usr/bin/env python3
"""
Calculate Researcher Coauthor Average H-Index Script
Calculate each researcher's coauthor average h-index based on coauthors_by_author.csv and author_citation_metrics.csv
"""

import pandas as pd
import numpy as np
import sys
from typing import Dict, List, Optional


def load_data():
    """Load required data files"""
    print("Loading data files...")
    
    try:
        # Load coauthor data
        coauthors_df = pd.read_csv('/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/coauthors_by_author.csv')
        print(f"Coauthor data: {len(coauthors_df)} records")
        
        # Load citation metrics data
        metrics_df = pd.read_csv('/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/author_citation_metrics.csv')
        print(f"Citation metrics data: {len(metrics_df)} records")
        
        return coauthors_df, metrics_df
        
    except FileNotFoundError as e:
        print(f"Data file not found: {e}")
        return None, None
    except Exception as e:
        print(f"Error reading data files: {e}")
        return None, None


def create_hindex_lookup(metrics_df: pd.DataFrame) -> Dict[int, float]:
    """Create author_id to h-index mapping dictionary"""
    print("Creating h-index lookup dictionary...")
    
    hindex_lookup = {}
    
    # Filter out empty or invalid h-index records
    valid_metrics = metrics_df.dropna(subset=['atip_h_index'])
    valid_metrics = valid_metrics[valid_metrics['atip_h_index'] >= 0]
    
    for _, row in valid_metrics.iterrows():
        author_id = row['author_id']
        h_index = row['atip_h_index']
        hindex_lookup[author_id] = h_index
    
    print(f"Valid h-index records: {len(hindex_lookup)}")
    return hindex_lookup


def calculate_coauthor_average_hindex(coauthors_df: pd.DataFrame, hindex_lookup: Dict[int, float]) -> pd.DataFrame:
    """Calculate each researcher's coauthor average h-index"""
    print("Starting coauthor average h-index calculation...")
    
    results = []
    
    # Group by researcher_id
    grouped = coauthors_df.groupby('researcher_id')
    total_researchers = len(grouped)
    processed = 0
    
    for researcher_id, group in grouped:
        processed += 1
        if processed % 100 == 0:
            print(f"Processing progress: {processed}/{total_researchers} ({processed/total_researchers:.1%})")
        
        # Get researcher name (take the name from the first record)
        author_name = group.iloc[0]['author_name']
        
        # Collect all coauthors' h-index
        coauthor_hindices = []
        total_coauthors = len(group)
        found_coauthors = 0
        
        for _, row in group.iterrows():
            coauthor_id = row['coauthor_id']
            
            # Look up coauthor's h-index
            if coauthor_id in hindex_lookup:
                h_index = hindex_lookup[coauthor_id]
                coauthor_hindices.append(h_index)
                found_coauthors += 1
        
        # Calculate average h-index
        if coauthor_hindices:
            avg_hindex = np.mean(coauthor_hindices)
            avg_hindex = round(avg_hindex, 2)  # Keep two decimal places
        else:
            avg_hindex = None  # No coauthor h-index found
        
        results.append({
            'author_id': researcher_id,
            'author_name': author_name,
            'coauthor_average_h_index': avg_hindex
        })
    
    print(f"Processing complete: {total_researchers} researchers")
    
    return pd.DataFrame(results)


def save_results(results_df: pd.DataFrame):
    """Save results and display statistics"""
    print("\n=== Result Statistics ===")
    
    total_authors = len(results_df)
    authors_with_hindex = len(results_df[results_df['coauthor_average_h_index'].notna()])
    authors_without_hindex = total_authors - authors_with_hindex
    
    print(f"Total researchers: {total_authors}")
    print(f"Researchers with calculated average h-index: {authors_with_hindex} ({authors_with_hindex/total_authors:.1%})")
    print(f"Researchers without calculated average h-index: {authors_without_hindex} ({authors_without_hindex/total_authors:.1%})")
    
    # Display statistics
    if authors_with_hindex > 0:
        valid_hindices = results_df[results_df['coauthor_average_h_index'].notna()]['coauthor_average_h_index']
        print(f"\nAverage h-index statistics:")
        print(f"  Minimum: {valid_hindices.min():.2f}")
        print(f"  Maximum: {valid_hindices.max():.2f}")
        print(f"  Mean: {valid_hindices.mean():.2f}")
        print(f"  Median: {valid_hindices.median():.2f}")
    
    # Display examples
    print(f"\n=== Top 10 Result Examples ===")
    for i, row in results_df.head(10).iterrows():
        status = "✓" if pd.notna(row['coauthor_average_h_index']) else "✗"
        print(f"{status} ID: {row['author_id']}, Name: {row['author_name'][:20]}{'...' if len(row['author_name']) > 20 else ''}")
        print(f"   Average h-index: {row['coauthor_average_h_index'] if pd.notna(row['coauthor_average_h_index']) else 'N/A'}")
        print()
    
    # Save results
    output_file = '/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/author_coauthor_hindex.csv'
    results_df.to_csv(output_file, index=False)
    print(f"Results saved to: {output_file}")


def main():
    """Main function"""
    print("=== Researcher Coauthor Average H-Index Calculation Script ===\n")
    
    # 1. Load data
    coauthors_df, metrics_df = load_data()
    if coauthors_df is None or metrics_df is None:
        print("Data loading failed, exiting program")
        return
    
    # 2. Create h-index lookup dictionary
    hindex_lookup = create_hindex_lookup(metrics_df)
    if not hindex_lookup:
        print("No valid h-index data, exiting program")
        return
    
    # 3. Calculate coauthor average h-index
    results_df = calculate_coauthor_average_hindex(coauthors_df, hindex_lookup)
    
    # 4. Save results
    save_results(results_df)
    
    print("\n=== Calculation Complete ===")


if __name__ == "__main__":
    main()
