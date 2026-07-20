#!/usr/bin/env python3
"""
Author Contribution Metrics Calculator (Optimized)

This script calculates the following author contribution metrics:
- FAR (First Author Ratio): Proportion of papers where author is first author
- FAI (First Author Impact): Proportion of citations from first-authored papers
- LAR (Last Author Ratio): Proportion of papers where author is last author  
- LAI (Last Author Impact): Proportion of citations from last-authored papers

Optimized version using vectorized operations for better performance.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_data():
    """Load the required CSV files from data/database"""
    logger.info("Loading data files...")
    
    # Load authorships data
    authorships_path = Path("data/database/authorships.csv")
    if not authorships_path.exists():
        raise FileNotFoundError(f"Authorships file not found: {authorships_path}")
    
    authorships = pd.read_csv(authorships_path)
    logger.info(f"Loaded authorships data: {len(authorships)} records")
    
    # Load papers data
    papers_path = Path("data/database/megatable_papers.csv")
    if not papers_path.exists():
        raise FileNotFoundError(f"Papers file not found: {papers_path}")
    
    papers = pd.read_csv(papers_path)
    logger.info(f"Loaded papers data: {len(papers)} records")
    
    return authorships, papers

def calculate_author_contribution_metrics_vectorized(authorships, papers):
    """
    Calculate author contribution metrics using vectorized operations
    
    Args:
        authorships: DataFrame with author_id, paper_id, is_first_author, is_last_author
        papers: DataFrame with paper_id, citation_count
    
    Returns:
        DataFrame with author_id, author_name, FAR, FAI, LAR, LAI
    """
    logger.info("Calculating author contribution metrics (vectorized)...")
    
    # Merge authorships with papers to get citation counts
    merged = authorships.merge(papers[['paper_id', 'citation_count']], 
                              on='paper_id', how='left')
    
    # Fill NaN citation counts with 0
    merged['citation_count'] = merged['citation_count'].fillna(0)
    
    # Create boolean columns for easier aggregation
    merged['is_first_author_bool'] = merged['is_first_author'].astype(bool)
    merged['is_last_author_bool'] = merged['is_last_author'].astype(bool)
    
    # Calculate weighted citations for first and last author papers
    merged['first_author_citations'] = np.where(merged['is_first_author_bool'], 
                                               merged['citation_count'], 0)
    merged['last_author_citations'] = np.where(merged['is_last_author_bool'], 
                                              merged['citation_count'], 0)
    
    logger.info("Aggregating metrics by author (vectorized)...")
    
    # Group by author and calculate all metrics at once using vectorized operations
    author_metrics = merged.groupby(['author_id', 'author_name']).agg({
        'paper_id': 'count',                          # total_papers
        'citation_count': 'sum',                      # total_citations
        'is_first_author_bool': 'sum',               # first_authorships
        'first_author_citations': 'sum',             # FAI (First Author Impact)
        'is_last_author_bool': 'sum',                # last_authorships
        'last_author_citations': 'sum'               # LAI (Last Author Impact)
    }).reset_index()
    
    # Rename columns for clarity
    author_metrics.columns = [
        'author_id', 'author_name', 'total_papers', 'total_citations',
        'first_authorships', 'FAI', 'last_authorships', 'LAI'
    ]
    
    logger.info("Calculating ratios (vectorized)...")
    
    # Calculate ratios using vectorized operations
    author_metrics['FAR'] = np.where(author_metrics['total_papers'] > 0,
                                    author_metrics['first_authorships'] / author_metrics['total_papers'],
                                    0.0)
    
    author_metrics['LAR'] = np.where(author_metrics['total_papers'] > 0,
                                    author_metrics['last_authorships'] / author_metrics['total_papers'],
                                    0.0)
    
    # Round all floating point values to 2 decimal places
    float_columns = ['FAR', 'LAR']
    for col in float_columns:
        author_metrics[col] = author_metrics[col].round(2)
    
    # Reorder columns to match original output format
    final_columns = [
        'author_id', 'author_name', 'total_papers', 'total_citations',
        'first_authorships', 'FAR', 'FAI', 'last_authorships', 'LAR', 'LAI'
    ]
    
    return author_metrics[final_columns]

def save_results(results_df):
    """Save the results to data/derived_metrics/author_contribution.csv"""
    output_dir = Path("data/derived_metrics")
    output_dir.mkdir(exist_ok=True)
    
    output_path = output_dir / "author_contribution.csv"
    results_df.to_csv(output_path, index=False)
    logger.info(f"Results saved to: {output_path}")
    
    # Print summary statistics
    logger.info(f"Calculated metrics for {len(results_df)} authors")
    
    # Calculate and display statistics
    if len(results_df) > 0:
        logger.info(f"FAR range: {results_df['FAR'].min():.2f} - {results_df['FAR'].max():.2f}")
        logger.info(f"FAI range: {results_df['FAI'].min():.2f} - {results_df['FAI'].max():.2f}")
        logger.info(f"LAR range: {results_df['LAR'].min():.2f} - {results_df['LAR'].max():.2f}")
        logger.info(f"LAI range: {results_df['LAI'].min():.2f} - {results_df['LAI'].max():.2f}")
        

def main():
    """Main function to run the author contribution metrics calculation"""
    try:
        # Load data
        authorships, papers = load_data()
        
        # Calculate metrics using vectorized operations
        results = calculate_author_contribution_metrics_vectorized(authorships, papers)
        
        # Save results
        save_results(results)
        
        logger.info("Author contribution metrics calculation completed successfully!")
        
    except Exception as e:
        logger.error(f"Error calculating author contribution metrics: {e}")
        raise

if __name__ == "__main__":
    main()
