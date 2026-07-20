import pandas as pd
import numpy as np
import os
from typing import Dict, List

# --- Configuration Constants ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(script_dir, '..', '..')
DATA_DIR = os.path.join(project_root, "data", "database")
CURRENT_YEAR = 2025
RISING_STAR_PERCENTILE = 0.95 # Top 5% are flagged as Rising Stars

# Parameters for the "Rising Star" TACI calculation
TACI_LAMBDA_RISING_STAR = 0.7
TACI_MU_RISING_STAR = 0.7

# Parameters for Citation Acceleration (CA)
CA_LOOKBACK_YEARS = 5
CA_SMOOTHING_K = 5

# Parameters for the Early-Career Profile Filter
PUB_COUNT_THRESHOLD = 10
LAR_THRESHOLD = 0.25
FAR_THRESHOLD = 0.50

def calculate_paper_impacts(citation_details_df: pd.DataFrame, papers_df: pd.DataFrame) -> Dict[int, float]:
    """
    Calculates the time-weighted impact for every paper.
    Uses high lambda and mu suitable for identifying Rising Stars.
    """
    print("Calculating paper impacts...")
    paper_year_lookup = dict(zip(papers_df['paper_id'], papers_df['year']))
    
    citations = citation_details_df[citation_details_df['year_cited'] > 0].copy()
    citations['paper_year'] = citations['target_paper_id'].map(paper_year_lookup)
    citations.dropna(subset=['paper_year'], inplace=True)

    citations['recency_diff'] = CURRENT_YEAR - citations['year_cited']
    citations['velocity_diff'] = citations['year_cited'] - citations['paper_year']

    recency_factor = np.exp(-TACI_LAMBDA_RISING_STAR * citations['recency_diff'])
    velocity_factor = np.exp(-TACI_MU_RISING_STAR * citations['velocity_diff'])
    citations['citation_impact'] = recency_factor * velocity_factor
    
    paper_impacts = citations.groupby('target_paper_id')['citation_impact'].sum().to_dict()
    
    return paper_impacts

def calculate_taci_avg(authorships_df: pd.DataFrame, paper_impacts: Dict[int, float]) -> pd.DataFrame:
    """Calculates the average TACI score for each author."""
    print("Calculating author shares and TACI scores...")
    authorships = authorships_df.copy()
    authorships['weight'] = 0.5
    authorships.loc[authorships['is_last_author'] & ~authorships['is_first_author'], 'weight'] = 0.8
    authorships.loc[authorships['is_first_author'], 'weight'] = 1.0
    
    paper_total_weights = authorships.groupby('paper_id')['weight'].sum().to_dict()
    authorships['total_paper_weight'] = authorships['paper_id'].map(paper_total_weights)
    authorships['author_share'] = authorships['weight'] / authorships['total_paper_weight']

    authorships['paper_impact'] = authorships['paper_id'].map(paper_impacts).fillna(0)
    authorships['taci_contribution'] = authorships['author_share'] * authorships['paper_impact']

    author_taci = authorships.groupby('author_id').agg(
        taci_contribution=('taci_contribution', 'sum'),
        paper_count=('paper_id', 'nunique')
    ).reset_index()  # Reset index to make author_id a column again
    
    author_taci['taci_avg'] = author_taci['taci_contribution'] / author_taci['paper_count']
    return author_taci[['author_id', 'taci_avg']]

def calculate_citation_acceleration(authorships_df: pd.DataFrame, citation_details_df: pd.DataFrame, author_ids: List[int]) -> pd.DataFrame:
    """Calculates the Citation Acceleration (CA) for a cohort of authors."""
    print("Calculating citation acceleration...")
    citations = citation_details_df.merge(authorships_df[['paper_id', 'author_id']], left_on='target_paper_id', right_on='paper_id')
    citations = citations[citations['author_id'].isin(author_ids)]

    velocity_df = citations.groupby(['author_id', 'year_cited']).size().reset_index(name='citations')

    def get_slope(data: pd.DataFrame) -> float:
        data = data.tail(CA_LOOKBACK_YEARS)
        if len(data) < 2:
            return 0.0
        relative_years = data['year_cited'] - data['year_cited'].min()
        slope, _ = np.polyfit(relative_years, data['citations'], 1)
        return slope

    # Fix the deprecation warning by using apply on the grouped data properly
    raw_acceleration = velocity_df.groupby('author_id', group_keys=False).apply(lambda x: get_slope(x), include_groups=False).to_dict()

    ca_df = pd.DataFrame({'author_id': author_ids})
    ca_df['ca_raw'] = ca_df['author_id'].map(raw_acceleration).fillna(0)
    
    paper_counts = authorships_df[authorships_df['author_id'].isin(author_ids)].groupby('author_id').size()
    ca_df['paper_count'] = ca_df['author_id'].map(paper_counts).fillna(0)

    ca_prior = ca_df['ca_raw'].mean()
    
    ca_df['ca_smoothed'] = ((ca_df['paper_count'] * ca_df['ca_raw']) + (CA_SMOOTHING_K * ca_prior)) / (ca_df['paper_count'] + CA_SMOOTHING_K)
    
    return ca_df[['author_id', 'ca_smoothed']]

def calculate_author_ratios(authorships_df: pd.DataFrame) -> pd.DataFrame:
    """Calculates publication count, FAR, and LAR for all authors."""
    print("Calculating author contribution ratios (FAR/LAR)...")
    
    # Debug: Check input data
    print(f"Authorships dataframe shape: {authorships_df.shape}")
    print(f"Authorships columns: {authorships_df.columns.tolist()}")
    
    try:
        author_stats = authorships_df.groupby('author_id').agg(
            publication_count=('paper_id', 'nunique'),
            first_author_count=('is_first_author', 'sum'),
            last_author_count=('is_last_author', 'sum')
        ).reset_index()  # Reset index to make author_id a column again
        
        print(f"Author stats shape after groupby: {author_stats.shape}")
        print(f"Author stats columns: {author_stats.columns.tolist()}")
        
        author_stats['far'] = author_stats['first_author_count'] / author_stats['publication_count']
        author_stats['lar'] = author_stats['last_author_count'] / author_stats['publication_count']
        
        result = author_stats[['author_id', 'publication_count', 'far', 'lar']]
        print(f"Final result shape: {result.shape}")
        print(f"Final result sample:\n{result.head()}")
        
        return result
        
    except Exception as e:
        print(f"Error in calculate_author_ratios: {e}")
        raise

def calculate_rising_stars(authors_df: pd.DataFrame, papers_df: pd.DataFrame, authorships_df: pd.DataFrame, citation_details_df: pd.DataFrame) -> pd.DataFrame:
    """
    Main function to orchestrate the Rising Star calculation.
    """
    print("Defining early-career cohort using multi-factor profile...")

    # Step 1: Calculate contribution ratios for all authors
    author_ratios_df = calculate_author_ratios(authorships_df)
    
    # Debug: Check the structure of author_ratios_df
    print(f"Author ratios columns: {author_ratios_df.columns.tolist()}")
    print(f"Author ratios shape: {author_ratios_df.shape}")
    print(f"Author ratios sample:\n{author_ratios_df.head()}")

    # Step 2: Merge ratios with the main authors dataframe
    print(f"Authors dataframe shape before merge: {authors_df.shape}")
    authors_with_stats_df = authors_df.merge(author_ratios_df, on='author_id', how='left', suffixes=('', '_calc'))
    print(f"Authors dataframe shape after merge: {authors_with_stats_df.shape}")
    print(f"Columns after merge: {authors_with_stats_df.columns.tolist()}")
    
    # Use the calculated publication count and handle any naming conflicts
    if 'publication_count_calc' in authors_with_stats_df.columns:
        authors_with_stats_df['publication_count'] = authors_with_stats_df['publication_count_calc']
        authors_with_stats_df.drop('publication_count_calc', axis=1, inplace=True)
    
    # Fill NaN values with 0 for authors with no publications
    authors_with_stats_df['publication_count'] = authors_with_stats_df['publication_count'].fillna(0)
    authors_with_stats_df['far'] = authors_with_stats_df['far'].fillna(0)
    authors_with_stats_df['lar'] = authors_with_stats_df['lar'].fillna(0)

    # Step 3: Apply the multi-factor filter to define the cohort
    is_low_pub_count = authors_with_stats_df['publication_count'] < PUB_COUNT_THRESHOLD
    is_low_lar = authors_with_stats_df['lar'] < LAR_THRESHOLD
    is_high_far = authors_with_stats_df['far'] > FAR_THRESHOLD

    early_career_authors = authors_with_stats_df[is_low_pub_count & is_low_lar & is_high_far]

    print(f"Identified {len(early_career_authors)} potential rising stars after filtering.")

    cohort_author_ids = early_career_authors['author_id'].tolist()
    
    authorships_cohort = authorships_df[authorships_df['author_id'].isin(cohort_author_ids)]

    # --- Calculate Metrics for the Cohort ---
    paper_impacts = calculate_paper_impacts(citation_details_df, papers_df)
    taci_scores = calculate_taci_avg(authorships_cohort, paper_impacts)
    ca_scores = calculate_citation_acceleration(authorships_cohort, citation_details_df, cohort_author_ids)

    # --- Combine and Normalize ---
    print("Combining, normalizing, and calculating final scores...")
    
    results_df = early_career_authors.copy()
    results_df = results_df.merge(taci_scores, on='author_id', how='left')
    results_df = results_df.merge(ca_scores, on='author_id', how='left')
    
    results_df['taci_avg'] = results_df['taci_avg'].fillna(0)
    results_df['ca_smoothed'] = results_df['ca_smoothed'].fillna(0)
    
    taci_min, taci_max = results_df['taci_avg'].min(), results_df['taci_avg'].max()
    ca_min, ca_max = results_df['ca_smoothed'].min(), results_df['ca_smoothed'].max()
    
    results_df['taci_norm'] = (results_df['taci_avg'] - taci_min) / (taci_max - taci_min) if taci_max > taci_min else 0
    results_df['ca_norm'] = (results_df['ca_smoothed'] - ca_min) / (ca_max - ca_min) if ca_max > ca_min else 0
    
    results_df['star_score'] = (0.6 * results_df['ca_norm']) + (0.4 * results_df['taci_norm'])
    
    # --- Classify Rising Stars ---
    score_threshold = results_df['star_score'].quantile(RISING_STAR_PERCENTILE)
    results_df['is_rising_star'] = results_df['star_score'] >= score_threshold
    
    # --- Format Final Output ---
    results_df['author_name'] = results_df['first_name'].fillna('') + ' ' + results_df['last_name'].fillna('')
    results_df['author_name'] = results_df['author_name'].str.strip()
    
    final_cols = ['author_id', 'author_name', 'career_length', 'star_score', 'is_rising_star']
    
    return results_df[final_cols].sort_values(by='star_score', ascending=False)

def main():
    """Main execution block"""
    try:
        print("Loading all data files...")
        authorships_df = pd.read_csv(os.path.join(DATA_DIR, "authorships.csv"))
        citation_details_df = pd.read_csv(os.path.join(DATA_DIR, "citation_details.csv"))
        papers_df = pd.read_csv(os.path.join(DATA_DIR, "megatable_papers.csv"))
        authors_df = pd.read_csv(os.path.join(DATA_DIR, "megatable_authors.csv"))
        print("Data loading complete.")

        rising_stars_df = calculate_rising_stars(authors_df, papers_df, authorships_df, citation_details_df)
        
        print("\n--- Rising Star Calculation Complete ---")
        print(f"Found {rising_stars_df['is_rising_star'].sum()} Rising Stars (Top {(1-RISING_STAR_PERCENTILE)*100:.1f}%).")
        
        print("\nTop 20 Ranked Early-Career Authors (after filtering):")
        print(rising_stars_df.head(20).to_string())
        
        print("\nExample Rising Stars:")
        print(rising_stars_df[rising_stars_df['is_rising_star'] == True].head(10).to_string())
        
        output_dir = os.path.join(project_root, 'data', 'derived_metrics')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'rising_stars.csv')
        rising_stars_df.to_csv(output_file, index=False)
        print(f"\nResults saved to: {output_file}")

    except FileNotFoundError as e:
        print(f"Error: Data file not found. Make sure your data is in '{DATA_DIR}'")
        print(f"Attempted to read from: {os.path.abspath(DATA_DIR)}")
        print(e)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()