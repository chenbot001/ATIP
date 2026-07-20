import pandas as pd
from collections import defaultdict
import os

def calculate_rsm_with_smoothing():
    """
    Calculates a smoothed Rising Star Magnet (RSM) score to correct for
    bias from authors with very small collaboration networks.

    The script performs the following steps:
    1.  Loads all required data.
    2.  Calculates raw "magnet points" based on early-career collaborations.
    3.  Calculates the raw RSM score for each author.
    4.  Calculates a global average (prior) for the raw RSM score.
    5.  Applies a confidence-weighted smoothing formula to produce a robust final score.
    6.  Saves the final, smoothed results to a CSV file.
    """
    # --- 1. Load Data ---
    try:
        authorships_df = pd.read_csv('data/database/authorships.csv')
        papers_df = pd.read_csv('data/database/megatable_papers.csv')
        rising_stars_df = pd.read_csv('data/derived_metrics/rising_stars.csv')
    except FileNotFoundError as e:
        print(f"Error: {e}. Please ensure all required CSV files are in the directory.")
        return

    print("Data loaded successfully.")

    # --- 2. Create Mappings & Identify Stars ---
    author_names_map = authorships_df[['author_id', 'author_name']].drop_duplicates().set_index('author_id')
    rising_star_ids = set(rising_stars_df[rising_stars_df['is_rising_star'] == True]['author_id'])
    
    if not rising_star_ids:
        print("No authors classified as 'Rising Star' found in rising_stars.csv.")
        return
    
    print(f"Identified {len(rising_star_ids)} rising stars.")

    # --- 3. Attribute "Magnet Points" ---
    authorships_with_year = pd.merge(authorships_df, papers_df[['paper_id', 'year']], on='paper_id')
    career_starts = authorships_with_year.groupby('author_id')['year'].min().to_dict()
    magnet_points = defaultdict(int)

    for rs_id in rising_star_ids:
        if rs_id not in career_starts: continue
        rs_start_year = career_starts[rs_id]
        magnet_window_end_year = rs_start_year + 2
        rs_early_paper_ids = set(
            authorships_with_year[
                (authorships_with_year['author_id'] == rs_id) &
                (authorships_with_year['year'] <= magnet_window_end_year)
            ]['paper_id']
        )
        if not rs_early_paper_ids: continue
        early_collaborators = authorships_with_year[authorships_with_year['paper_id'].isin(rs_early_paper_ids)]
        for co_author_id in early_collaborators['author_id'].unique():
            if co_author_id != rs_id:
                magnet_points[co_author_id] += 1
    
    print(f"Attributed magnet points to {len(magnet_points)} collaborators.")

    # --- 4. Calculate Raw Scores ---
    coauthor_pairs = pd.merge(authorships_df, authorships_df, on='paper_id', suffixes=('_A', '_B'))
    coauthor_pairs = coauthor_pairs[coauthor_pairs['author_id_A'] != coauthor_pairs['author_id_B']]
    total_coauthors = coauthor_pairs.groupby('author_id_A')['author_id_B'].nunique()
    total_coauthors.name = 'total_unique_coauthors'
    
    magnet_df = pd.DataFrame.from_dict(magnet_points, orient='index', columns=['magnet_points'])
    magnet_df.index.name = 'author_id'

    rsm_results = magnet_df.join(total_coauthors, how='left')
    rsm_results['total_unique_coauthors'] = rsm_results['total_unique_coauthors'].fillna(0)
    
    rsm_results['rsm_raw'] = rsm_results.apply(
        lambda row: row['magnet_points'] / row['total_unique_coauthors'] if row['total_unique_coauthors'] > 0 else 0,
        axis=1
    )
    print("Calculated raw RSM scores.")

    # --- 5. Apply Confidence-Weighted Smoothing ---
    # Define the smoothing factor 'k'. This is a tunable parameter.
    k = 10 
    
    # Calculate the prior: the average raw score across all authors.
    rsm_prior = rsm_results['rsm_raw'].mean()
    
    # Apply the smoothing formula.
    rsm_results['rsm_smoothed'] = rsm_results.apply(
        lambda row: (
            (row['total_unique_coauthors'] * row['rsm_raw']) + (k * rsm_prior)
        ) / (row['total_unique_coauthors'] + k),
        axis=1
    )
    print(f"Applied smoothing with k={k} and prior={rsm_prior:.4f}")

    # --- 6. Finalize and Save ---
    rsm_results = rsm_results.reset_index().merge(author_names_map, on='author_id', how='left')
    
    # Sort by the new, robust smoothed score.
    rsm_results = rsm_results.sort_values(by='rsm_smoothed', ascending=False)

    final_columns = [
        'author_id', 'author_name', 'rsm_smoothed', 'magnet_points', 
        'total_unique_coauthors', 'rsm_raw'
    ]
    rsm_results = rsm_results[final_columns]
    
    output_dir = 'data/derived_metrics'
    output_path = os.path.join(output_dir, 'rsm.csv')
    os.makedirs(output_dir, exist_ok=True)
    rsm_results.to_csv(output_path, index=False)
    
    print(f"\n✅ Results successfully saved to: {output_path}")
    return rsm_results

if __name__ == '__main__':
    final_scores = calculate_rsm_with_smoothing()
    if final_scores is not None:
        print("\n--- Smoothed Rising Star Magnet (RSM) Top 20 Scores ---")
        # Rename columns for cleaner display
        display_df = final_scores.rename(columns={
            'rsm_smoothed': 'Smoothed Score',
            'magnet_points': 'Magnet Points',
            'total_unique_coauthors': 'Total Co-authors',
            'rsm_raw': 'Raw Score'
        })
        print(display_df.head(20).to_string(index=False, float_format="%.4f"))