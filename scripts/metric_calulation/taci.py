import pandas as pd
import numpy as np
import os
from datetime import datetime
import math
import argparse

def calculate_paper_impact_vectorized(citations_df, papers_df, current_year=2025, lambda_decay=0.1, mu_decay=0.1):
    """
    Vectorized calculation of PaperImpact using pandas operations.
    
    Formula: PaperImpact(p) = sum(exp(-lambda * (T_current - T_c)) * exp(-mu * (T_c - T_p)))
    """
    # Create a paper_year lookup dictionary for fast access
    paper_year_lookup = dict(zip(papers_df['paper_id'], papers_df['year']))
    
    # Filter out invalid citation years (0 or negative)
    valid_citations = citations_df[citations_df['year_cited'] > 0].copy()
    print(f"Filtered out {len(citations_df) - len(valid_citations)} citations with invalid years")
    
    # Add paper publication year to citations dataframe
    valid_citations['paper_year'] = valid_citations['target_paper_id'].map(paper_year_lookup)
    
    # Remove citations to papers not in our dataset
    valid_citations = valid_citations.dropna(subset=['paper_year'])
    
    # Vectorized calculation of time differences
    valid_citations['recency_diff'] = current_year - valid_citations['year_cited']
    valid_citations['velocity_diff'] = valid_citations['year_cited'] - valid_citations['paper_year']
    
    # Clamp values to prevent overflow
    max_exponent = 700
    valid_citations['recency_diff'] = np.clip(valid_citations['recency_diff'], -max_exponent, max_exponent)
    valid_citations['velocity_diff'] = np.clip(valid_citations['velocity_diff'], -max_exponent, max_exponent)
    
    # Vectorized exponential calculations
    valid_citations['recency_factor'] = np.exp(-lambda_decay * valid_citations['recency_diff'])
    valid_citations['velocity_factor'] = np.exp(-mu_decay * valid_citations['velocity_diff'])
    valid_citations['citation_impact'] = valid_citations['recency_factor'] * valid_citations['velocity_factor']
    
    # Group by target paper and sum impacts
    paper_impacts = valid_citations.groupby('target_paper_id')['citation_impact'].sum().to_dict()
    
    # Initialize all papers with 0 impact (including those without citations)
    all_paper_impacts = dict.fromkeys(papers_df['paper_id'], 0.0)
    all_paper_impacts.update(paper_impacts)
    
    papers_with_citations = len(paper_impacts)
    print(f"Papers with citations: {papers_with_citations}")
    print(f"Papers without citations: {len(papers_df) - papers_with_citations}")
    
    return all_paper_impacts

def calculate_author_shares_vectorized(authorships_df):
    """
    Vectorized calculation of author shares for all papers.
    """
    # Calculate weights based on position (matching original logic exactly)
    authorships_df = authorships_df.copy()
    
    # Default weight for middle authors
    authorships_df['weight'] = 0.5
    
    # Set weights using the same if/elif logic as original
    # First author takes precedence over last author (for single-author papers)
    authorships_df.loc[authorships_df['is_last_author'] & ~authorships_df['is_first_author'], 'weight'] = 0.8
    authorships_df.loc[authorships_df['is_first_author'], 'weight'] = 1.0
    
    # Calculate total weight per paper
    paper_total_weights = authorships_df.groupby('paper_id')['weight'].sum()
    
    # Map total weights back to authorships
    authorships_df['total_paper_weight'] = authorships_df['paper_id'].map(paper_total_weights)
    
    # Calculate author share
    authorships_df['author_share'] = authorships_df['weight'] / authorships_df['total_paper_weight']
    
    return authorships_df[['author_id', 'paper_id', 'author_share']]

def calculate_all_taci_scores_vectorized(authorships_df, paper_impacts, authors_df):
    """
    Vectorized calculation of TACI scores for all authors.
    """
    # Calculate author shares for all papers
    author_shares_df = calculate_author_shares_vectorized(authorships_df)
    
    # Convert paper_impacts to Series for vectorized operations
    paper_impacts_series = pd.Series(paper_impacts)
    
    # Map paper impacts to authorships
    author_shares_df['paper_impact'] = author_shares_df['paper_id'].map(paper_impacts_series).fillna(0)
    
    # Calculate contribution of each authorship to TACI
    author_shares_df['taci_contribution'] = author_shares_df['author_share'] * author_shares_df['paper_impact']
    
    # Group by author and calculate totals
    author_taci = author_shares_df.groupby('author_id').agg({
        'taci_contribution': 'sum',
        'paper_id': 'count'
    }).rename(columns={'paper_id': 'paper_count', 'taci_contribution': 'total_taci'})
    
    # Apply log normalization
    author_taci['log_normalized_taci'] = np.log1p(author_taci['total_taci'])
    
    # Calculate average TACI
    author_taci['average_taci'] = author_taci['log_normalized_taci'] / author_taci['paper_count']
    
    return author_taci

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Calculate TACI scores with configurable decay parameters (optimized version)')
    parser.add_argument('--lambda_decay', type=float, default=0.1, 
                       help='Lambda decay parameter for recency factor (default: 0.1)')
    parser.add_argument('--mu_decay', type=float, default=0.1,
                       help='Mu decay parameter for velocity factor (default: 0.1)')
    
    args = parser.parse_args()
    lambda_decay = args.lambda_decay
    mu_decay = args.mu_decay
    
    print(f"Starting TACI calculation (optimized) with lambda_decay={lambda_decay}, mu_decay={mu_decay}...")
    
    # Define file paths
    data_dir = "data/database"
    output_dir = "data/derived_metrics"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load data
    print("Loading data files...")
    authorships_df = pd.read_csv(os.path.join(data_dir, "authorships.csv"))
    citation_details_df = pd.read_csv(os.path.join(data_dir, "citation_details.csv"))
    papers_df = pd.read_csv(os.path.join(data_dir, "megatable_papers.csv"))
    authors_df = pd.read_csv(os.path.join(data_dir, "megatable_authors.csv"))
    
    print(f"Loaded {len(authorships_df)} authorships")
    print(f"Loaded {len(citation_details_df)} citation details")
    print(f"Loaded {len(papers_df)} papers")
    print(f"Loaded {len(authors_df)} authors")
    
    # Calculate paper impacts with vectorized operations
    print("Calculating paper impacts (vectorized)...")
    paper_impacts = calculate_paper_impact_vectorized(citation_details_df, papers_df, 
                                                    lambda_decay=lambda_decay, mu_decay=mu_decay)
    print(f"Calculated impacts for {len(paper_impacts)} papers")
    
    # Filter authors with more than 5 papers
    print("Filtering authors with more than 5 papers...")
    authors_with_many_papers = authors_df[authors_df['publication_count'] > 5]
    filtered_author_ids = set(authors_with_many_papers['author_id'].unique())
    
    # Filter authorships to only include these authors
    filtered_authorships = authorships_df[authorships_df['author_id'].isin(filtered_author_ids)]
    
    print(f"Found {len(filtered_author_ids)} authors with more than 5 papers")
    print(f"(Filtered from {len(authors_df)} total authors)")
    
    # Calculate TACI scores for all filtered authors using vectorized operations
    print("Calculating TACI scores (vectorized)...")
    author_taci_results = calculate_all_taci_scores_vectorized(filtered_authorships, paper_impacts, authors_df)
    
    # Merge with author names
    author_names = authors_df[['author_id', 'first_name', 'last_name']].copy()
    author_names['author_full_name'] = author_names['first_name'].fillna('') + ' ' + author_names['last_name'].fillna('')
    author_names['author_full_name'] = author_names['author_full_name'].str.strip()
    
    # Merge results with names
    results_df = author_taci_results.reset_index().merge(author_names[['author_id', 'author_full_name']], 
                                                        on='author_id', how='left')
    
    # Handle missing names by falling back to authorships table
    missing_names = results_df['author_full_name'].isna()
    if missing_names.any():
        fallback_names = authorships_df.groupby('author_id')['author_name'].first()
        results_df.loc[missing_names, 'author_full_name'] = results_df.loc[missing_names, 'author_id'].map(fallback_names)
    
    # Rename columns to match original format
    results_df = results_df.rename(columns={
        'log_normalized_taci': 'TACI',
        'average_taci': 'average_TACI'
    })
    
    # Sort by TACI score (descending)
    results_df = results_df.sort_values('TACI', ascending=False)
    
    # Normalize scores to 0-100 scale
    if len(results_df) > 0:
        max_taci = results_df['TACI'].max()
        max_avg_taci = results_df['average_TACI'].max()
        
        if max_taci > 0:
            results_df['TACI'] = (results_df['TACI'] / max_taci) * 100
        if max_avg_taci > 0:
            results_df['average_TACI'] = (results_df['average_TACI'] / max_avg_taci) * 100
    
    # Round TACI scores to 2 decimal places for better readability
    results_df['TACI'] = results_df['TACI'].round(2)
    results_df['average_TACI'] = results_df['average_TACI'].round(2)
    
    # Save to CSV with lambda and mu parameters in filename
    output_file = os.path.join(output_dir, f"citation_impact_lambda{lambda_decay}_mu{mu_decay}.csv")
    results_df[['author_id', 'author_full_name', 'TACI', 'average_TACI', 'paper_count']].to_csv(output_file, index=False)
    
    print(f"TACI calculation complete!")
    print(f"Results saved to: {output_file}")
    print(f"Parameters used: lambda_decay={lambda_decay}, mu_decay={mu_decay}")
    print(f"Total authors processed: {len(results_df)}")
    
    # Print some statistics
    if len(results_df) > 0:
        print("\nTACI Score Statistics:")
        print(f"Mean TACI: {results_df['TACI'].mean():.4f}")
        print(f"Median TACI: {results_df['TACI'].median():.4f}")
        print(f"Max TACI: {results_df['TACI'].max():.4f}")
        print(f"Min TACI: {results_df['TACI'].min():.4f}")

if __name__ == "__main__":
    main()
