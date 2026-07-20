"""
Network Growth Catalyst (NGC) Metric Calculator (Revised & Corrected)

This script calculates the Network Growth Catalyst score for authors based on their
ability to foster new, independent collaborations among their co-authors.

Revision: Replaced the slow, iterative calculation with a highly optimized
approach that pre-computes lookup maps and uses fast set operations. Corrected
a TypeError during final data formatting.

Author: Generated for ATIP project
Date: August 2025
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from itertools import combinations
import warnings
from tqdm import tqdm

warnings.filterwarnings('ignore')

def load_data(data_dir):
    """Load required datasets for NGC calculation."""
    print("Loading data...")
    authorships_df = pd.read_csv(os.path.join(data_dir, 'authorships.csv'))
    papers_df = pd.read_csv(os.path.join(data_dir, 'megatable_papers.csv'))
    authors_df = pd.read_csv(os.path.join(data_dir, 'megatable_authors.csv'))
    print(f"Loaded {len(authorships_df)} authorships, {len(papers_df)} papers, {len(authors_df)} authors.")
    return authorships_df, papers_df, authors_df

def calculate_ngc_optimized(authorships_df: pd.DataFrame, papers_df: pd.DataFrame, authors_df: pd.DataFrame, smoothing_k: int = 20) -> pd.DataFrame:
    """
    Optimized calculation of NGC scores with confidence-weighted smoothing.
    """
    print("Starting optimized NGC calculation...")

    # --- Step 1: Pre-computation of Lookup Maps for Efficiency ---
    print("Step 1/4: Pre-computing lookup maps...")
    authorships_with_year = authorships_df.merge(papers_df[['paper_id', 'year']], on='paper_id', how='inner')
    author_papers_map = authorships_with_year.groupby('author_id')['paper_id'].apply(set).to_dict()
    paper_year_map = papers_df.set_index('paper_id')['year'].to_dict()
    paper_authors_map = authorships_with_year.groupby('paper_id')['author_id'].apply(set).to_dict()

    # --- Step 2: Identify each author's co-author network and first contact years ---
    print("Step 2/4: Identifying co-author networks and first contact years...")
    author_networks = {}
    for author_id, papers in tqdm(author_papers_map.items(), desc="Building Networks"):
        coauthors = {}
        for paper_id in papers:
            for coauthor_id in paper_authors_map.get(paper_id, set()):
                if author_id != coauthor_id:
                    year = paper_year_map.get(paper_id)
                    if coauthor_id not in coauthors or year < coauthors[coauthor_id]:
                        coauthors[coauthor_id] = year
        author_networks[author_id] = coauthors

    # --- Step 3: Calculate Raw NGC score for each author ---
    print("Step 3/4: Calculating Raw NGC scores...")
    results = []
    for author_id, coauthors in tqdm(author_networks.items(), desc="Calculating NGC"):
        if len(coauthors) < 2:
            results.append({'author_id': author_id, 'network_size': len(coauthors), 'catalyzed_count': 0, 'total_pairs': 0, 'ngc_raw': 0.0})
            continue

        catalyzed_count = 0
        coauthor_pairs = list(combinations(coauthors.keys(), 2))
        total_possible_pairs = len(coauthor_pairs)

        for coauthor_x, coauthor_y in coauthor_pairs:
            introduction_year = max(coauthors[coauthor_x], coauthors[coauthor_y])
            common_papers = author_papers_map.get(coauthor_x, set()) & author_papers_map.get(coauthor_y, set())
            independent_papers = common_papers - author_papers_map.get(author_id, set())
            for paper_id in independent_papers:
                if paper_year_map.get(paper_id, 0) > introduction_year:
                    catalyzed_count += 1
                    break
        
        ngc_raw = catalyzed_count / total_possible_pairs if total_possible_pairs > 0 else 0.0
        results.append({'author_id': author_id, 'network_size': len(coauthors), 'catalyzed_count': catalyzed_count, 'total_pairs': total_possible_pairs, 'ngc_raw': ngc_raw})
        
    ngc_results_df = pd.DataFrame(results)

    # --- Step 4: Apply Confidence-Weighted Smoothing ---
    print("Step 4/4: Applying confidence-weighted smoothing...")
    ngc_prior = ngc_results_df['ngc_raw'].mean()
    ngc_results_df['ngc_smoothed'] = (
        (ngc_results_df['total_pairs'] * ngc_results_df['ngc_raw']) + (smoothing_k * ngc_prior)
    ) / (ngc_results_df['total_pairs'] + smoothing_k)

    # --- Finalize and Format Output ---
    final_df = authors_df.merge(ngc_results_df, on='author_id', how='left')
    
    # --- CORRECTED FILLNA LOGIC ---
    # Fill only the specific numeric columns that might be NaN after the left merge
    numeric_cols_to_fill = ['network_size', 'catalyzed_count', 'ngc_smoothed']
    for col in numeric_cols_to_fill:
        final_df[col] = final_df[col].fillna(0)

    final_df['network_size'] = final_df['network_size'].astype(int)
    final_df['catalyzed_count'] = final_df['catalyzed_count'].astype(int)
    
    # This line will now work correctly
    final_df['author_name'] = (final_df['first_name'].fillna('') + ' ' + final_df['last_name'].fillna('')).str.strip()
    
    return final_df[['author_id', 'author_name', 'career_length', 'network_size', 'catalyzed_count', 'ngc_smoothed']].rename(columns={'ngc_smoothed': 'ngc_score'})

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(script_dir, '..', '..')
    data_dir = os.path.join(project_root, 'data', 'database')
    output_dir = os.path.join(project_root, 'data', 'derived_metrics')
    output_file = os.path.join(output_dir, 'ngc.csv')
    
    print(f"Data directory: {data_dir}")
    print(f"Output file will be saved to: {output_file}")
    os.makedirs(output_dir, exist_ok=True)
    
    authorships_df, papers_df, authors_df = load_data(data_dir)
    
    start_time = datetime.now()
    results_df = calculate_ngc_optimized(authorships_df, papers_df, authors_df)
    end_time = datetime.now()
    
    print(f"\nCalculation completed in {end_time - start_time}")
    
    print("\n=== NGC Score Summary ===")
    print(f"Total authors processed: {len(results_df)}")
    print(f"Authors with NGC > 0: {len(results_df[results_df['ngc_score'] > 0])}")
    print(f"Mean NGC score: {results_df['ngc_score'].mean():.4f}")
    print(f"Median NGC score: {results_df['ngc_score'].median():.4f}")
    print(f"Max NGC score: {results_df['ngc_score'].max():.4f}")
    
    print("\n=== Top 20 Authors by NGC Score (Smoothed) ===")
    top_20 = results_df.nlargest(20, 'ngc_score')
    print(top_20.to_string(index=False))
    
    results_df.to_csv(output_file, index=False)
    print(f"\nResults saved to: {output_file}")

if __name__ == "__main__":
    main()