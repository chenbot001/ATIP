#!/usr/bin/env python
"""
Optimized Citation Acceleration Calculator using vectorized operations.
Run this script after activating the AI conda environment:
    conda activate AI
"""
import pandas as pd
import numpy as np
import os
import sys
import json
import argparse
from sklearn.linear_model import LinearRegression

def calculate_citation_acceleration_vectorized(authorships_df, citation_details_df, authors_meta_df, 
                                             n_years=5, k_prior=5):
    """
    Vectorized calculation of citation acceleration scores.
    
    Parameters:
    - n_years: Number of recent years to use for regression
    - k_prior: Smoothing factor for Bayesian adjustment
    """
    print('Building citation profiles with vectorized operations...')
    
    # Create paper-to-citations mapping using vectorized operations
    print('Aggregating citations by paper and year...')
    paper_year_citations = citation_details_df.groupby(['target_paper_id', 'year_cited']).size().reset_index(name='citation_count')
    
    # Merge with authorships to get author-paper-year citations
    print('Mapping citations to authors...')
    author_paper_citations = authorships_df[['author_id', 'paper_id']].merge(
        paper_year_citations, 
        left_on='paper_id', 
        right_on='target_paper_id', 
        how='left'
    ).fillna(0)
    
    # Aggregate citations by author and year
    print('Aggregating citations by author and year...')
    author_year_citations = author_paper_citations.groupby(['author_id', 'year_cited'])['citation_count'].sum().reset_index()
    
    # Filter out zero citation years (from fillna)
    author_year_citations = author_year_citations[author_year_citations['citation_count'] > 0]
    
    print('Calculating acceleration scores using vectorized linear regression...')
    
    # Get unique authors who have citations
    authors_with_citations = author_year_citations['author_id'].unique()
    
    # Calculate accelerations for all authors at once
    acceleration_results = []
    
    # Group by author for vectorized processing
    grouped = author_year_citations.groupby('author_id')
    
    # Calculate total citations per author
    print('Calculating total citations per author...')
    author_total_citations = author_year_citations.groupby('author_id')['citation_count'].sum().to_dict()
    
    # First pass: collect all individual slopes for calculating field average
    all_slopes = []
    author_data = {}
    
    for author_id, group in grouped:
        years = group['year_cited'].values
        citations = group['citation_count'].values
        
        if len(years) < 2:
            continue
            
        # Sort by year
        sort_idx = np.argsort(years)
        years_sorted = years[sort_idx]
        citations_sorted = citations[sort_idx]
        
        # Use only recent years
        if len(years_sorted) > n_years:
            years_recent = years_sorted[-n_years:]
            citations_recent = citations_sorted[-n_years:]
        else:
            years_recent = years_sorted
            citations_recent = citations_sorted
            
        if len(years_recent) >= 2:
            # Calculate slope using vectorized operations
            X = years_recent.reshape(-1, 1)
            y = citations_recent
            
            # Use numpy for faster linear regression calculation
            X_mean = np.mean(X)
            y_mean = np.mean(y)
            numerator = np.sum((X.flatten() - X_mean) * (y - y_mean))
            denominator = np.sum((X.flatten() - X_mean) ** 2)
            
            if denominator != 0:
                slope = numerator / denominator
                all_slopes.append(slope)
                author_data[author_id] = {
                    'slope': slope,
                    'n_points': len(years_recent),
                    'year_citations': dict(zip(group['year_cited'], group['citation_count'])),
                    'total_citations': author_total_citations.get(author_id, 0)
                }
    
    # Calculate field-wide prior
    m_prior = np.mean(all_slopes) if all_slopes else 0.0
    print(f'Field-wide average acceleration (m_prior): {m_prior:.4f}')
    
    # Second pass: calculate smoothed accelerations
    print('Calculating smoothed acceleration scores...')
    
    # Get all authors from authorships (including those without citations)
    all_authors = authorships_df['author_id'].unique()
    
    # Create author name mapping
    author_names = authorships_df.groupby('author_id')['author_name'].first().to_dict()
    
    results = []
    
    for author_id in all_authors:
        # Get author metadata
        meta = authors_meta_df[authors_meta_df['author_id'] == author_id]
        if not meta.empty:
            first_name = meta.iloc[0]['first_name'] if pd.notna(meta.iloc[0]['first_name']) else ''
            last_name = meta.iloc[0]['last_name'] if pd.notna(meta.iloc[0]['last_name']) else ''
            career_length = meta.iloc[0]['career_length'] if pd.notna(meta.iloc[0]['career_length']) else ''
            author_name = f"{first_name} {last_name}".strip()
        else:
            author_name = author_names.get(author_id, '')
            career_length = ''
        
        # Calculate acceleration
        if author_id in author_data:
            data = author_data[author_id]
            m = data['slope']
            n_points = data['n_points']
            year_citations = data['year_citations']
            total_citations = data['total_citations']
            
            # Bayesian smoothing
            accel_score = (n_points * m + k_prior * m_prior) / (n_points + k_prior)
        else:
            accel_score = 0.0
            year_citations = {}
            total_citations = author_total_citations.get(author_id, 0)
        
        results.append({
            'author_id': author_id,
            'author_name': author_name,
            'career_length': career_length,
            'accel_score': accel_score,
            'total_citations': total_citations,
            'citations_by_year': json.dumps(year_citations, sort_keys=True)
        })
    
    return pd.DataFrame(results)

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Calculate citation acceleration scores (optimized version)')
    parser.add_argument('--n_years', type=int, default=5, 
                       help='Number of recent years for regression (default: 5)')
    parser.add_argument('--k_prior', type=int, default=5,
                       help='Smoothing factor for Bayesian adjustment (default: 5)')
    
    args = parser.parse_args()
    n_years = args.n_years
    k_prior = args.k_prior
    
    print(f'Starting citation acceleration calculation (optimized) with n_years={n_years}, k_prior={k_prior}...')
    
    # Define file paths
    input_dir = 'data/database'
    output_dir = 'data/derived_metrics'
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    print('Loading data...')
    # Load data with only required columns for memory efficiency
    authorships_df = pd.read_csv(
        os.path.join(input_dir, 'authorships.csv'), 
        usecols=['author_id', 'paper_id', 'author_name']
    )
    citation_details_df = pd.read_csv(
        os.path.join(input_dir, 'citation_details.csv'), 
        usecols=['target_paper_id', 'year_cited']
    )
    authors_meta_df = pd.read_csv(
        os.path.join(input_dir, 'megatable_authors.csv'), 
        usecols=['author_id', 'first_name', 'last_name', 'career_length']
    )
    
    print(f"Loaded {len(authorships_df)} authorships")
    print(f"Loaded {len(citation_details_df)} citation details")
    print(f"Loaded {len(authors_meta_df)} author metadata records")
    
    # Filter out invalid citation years
    citation_details_df = citation_details_df[citation_details_df['year_cited'] > 0]
    print(f"Using {len(citation_details_df)} valid citations")
    
    # Calculate acceleration scores using vectorized operations
    results_df = calculate_citation_acceleration_vectorized(
        authorships_df, citation_details_df, authors_meta_df, 
        n_years=n_years, k_prior=k_prior
    )
    
    # Sort by acceleration score (descending)
    results_df = results_df.sort_values('accel_score', ascending=False)

    # Round acceleration scores to 2 decimal places for readability
    results_df['accel_score'] = results_df['accel_score'].round(2)
    
    # Save results
    output_file = os.path.join(output_dir, f'citation_acceleration.csv')
    results_df.to_csv(output_file, index=False)
    
    print(f'Citation acceleration calculation complete!')
    print(f'Results saved to: {output_file}')
    print(f'Parameters used: n_years={n_years}, k_prior={k_prior}')
    print(f'Total authors processed: {len(results_df)}')
    
    # Print some statistics
    non_zero_accel = results_df[results_df['accel_score'] != 0]
    if len(non_zero_accel) > 0:
        print(f"\nAcceleration Score Statistics (non-zero only):")
        print(f"Authors with non-zero acceleration: {len(non_zero_accel)}")
        print(f"Mean acceleration: {non_zero_accel['accel_score'].mean():.4f}")
        print(f"Median acceleration: {non_zero_accel['accel_score'].median():.4f}")
        print(f"Max acceleration: {non_zero_accel['accel_score'].max():.4f}")
        print(f"Min acceleration: {non_zero_accel['accel_score'].min():.4f}")
    
    # Print citation statistics
    non_zero_citations = results_df[results_df['total_citations'] > 0]
    if len(non_zero_citations) > 0:
        print(f"\nCitation Statistics:")
        print(f"Authors with citations: {len(non_zero_citations)}")
        print(f"Mean total citations: {non_zero_citations['total_citations'].mean():.2f}")
        print(f"Median total citations: {non_zero_citations['total_citations'].median():.0f}")
        print(f"Max total citations: {non_zero_citations['total_citations'].max():.0f}")
        print(f"Min total citations (>0): {non_zero_citations['total_citations'].min():.0f}")
    

if __name__ == '__main__':
    main()
