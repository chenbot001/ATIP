import pandas as pd
import os
import numpy as np

def compile_team_metrics(team_file, output_file):
    """
    Compile comprehensive metrics for team authors found in the dataset.
    
    Args:
        team_file (str): Path to the text file containing team names and author IDs
        output_file (str): Path for the output CSV file
    """

    # Read the team file to get author IDs
    print(f"Reading team data from {team_file}...")
    team_authors = []

    try:
        with open(team_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if ' | ' in line:
                    name, result = line.split(' | ', 1)
                    if result != 'not found' and result.isdigit():
                        team_authors.append({
                            'author_name': name,
                            'author_id': int(result)
                        })

        print(f"Found {len(team_authors)} team authors in dataset")
        
    except Exception as e:
        print(f"Error reading team file: {e}")
        return

    if not team_authors:
        print("No team authors found in dataset")
        return
    
    # Convert to DataFrame for easier handling
    team_df = pd.DataFrame(team_authors)
    
    # Add original order index to preserve input order
    team_df['original_order'] = range(len(team_df))

    # Define metrics files and their paths
    metrics_dir = "data/derived_metrics"
    
    # Load all metric files
    print("Loading metric files...")
    
    # Citation Impact (lambda=0.1, mu=0.1)
    try:
        citation_impact_df = pd.read_csv(os.path.join(metrics_dir, "citation_impact_lambda0.1_mu0.1.csv"))
        citation_impact_df['citation_impact_ranking'] = citation_impact_df['TACI'].rank(ascending=False, method='min')
        citation_impact_df['average_taci_ranking'] = citation_impact_df['average_TACI'].rank(ascending=False, method='min')
        print(f"  - Citation impact: {len(citation_impact_df)} authors")
    except Exception as e:
        print(f"  - Warning: Could not load citation impact data: {e}")
        citation_impact_df = pd.DataFrame(columns=['author_id', 'TACI', 'citation_impact_ranking', 'average_TACI', 'average_taci_ranking'])
    
    # Citation Acceleration
    try:
        citation_accel_df = pd.read_csv(os.path.join(metrics_dir, "citation_acceleration.csv"))
        citation_accel_df['citation_accel_ranking'] = citation_accel_df['accel_score'].rank(ascending=False, method='min')
        print(f"  - Citation acceleration: {len(citation_accel_df)} authors")
    except Exception as e:
        print(f"  - Warning: Could not load citation acceleration data: {e}")
        citation_accel_df = pd.DataFrame(columns=['author_id', 'career_length', 'accel_score', 'citation_accel_ranking'])
    
    # Author Contribution
    try:
        contribution_df = pd.read_csv(os.path.join(metrics_dir, "author_contribution.csv"))
        print(f"  - Author contribution: {len(contribution_df)} authors")
    except Exception as e:
        print(f"  - Warning: Could not load author contribution data: {e}")
        contribution_df = pd.DataFrame(columns=['author_id', 'total_papers', 'total_citations', 'FAI', 'LAI'])
    
    # Author Breakthroughs
    try:
        breakthroughs_df = pd.read_csv(os.path.join(metrics_dir, "author_breakthroughs.csv"))
        print(f"  - Author breakthroughs: {len(breakthroughs_df)} authors")
    except Exception as e:
        print(f"  - Warning: Could not load author breakthroughs data: {e}")
        breakthroughs_df = pd.DataFrame(columns=['author_id', 'weighted_BPR', 'weighted_LIPR'])
    
    # Rising Star Magnetism
    try:
        rsm_df = pd.read_csv(os.path.join(metrics_dir, "rsm.csv"))
        print(f"  - Rising Star Magnetism: {len(rsm_df)} authors")
    except Exception as e:
        print(f"  - Warning: Could not load RSM data: {e}")
        rsm_df = pd.DataFrame(columns=['author_id', 'rsm_smoothed', 'unique_coauthors'])
    
    # Network Growth Catalyst
    try:
        ngc_df = pd.read_csv(os.path.join(metrics_dir, "ngc.csv"))
        print(f"  - Network Growth Catalyst: {len(ngc_df)} authors")
    except Exception as e:
        print(f"  - Warning: Could not load NGC data: {e}")
        ngc_df = pd.DataFrame(columns=['author_id', 'ngc_score', 'catalyzed_count'])
    
    # Rising Stars
    try:
        rising_stars_df = pd.read_csv(os.path.join(metrics_dir, "rising_stars.csv"))
        # Round star_score to 4 decimal places
        if 'star_score' in rising_stars_df.columns:
            rising_stars_df['star_score'] = rising_stars_df['star_score'].round(4)
        print(f"  - Rising Stars: {len(rising_stars_df)} authors")
    except Exception as e:
        print(f"  - Warning: Could not load rising stars data: {e}")
        rising_stars_df = pd.DataFrame(columns=['author_id', 'is_rising_star', 'star_score'])
    
    print("Compiling metrics for team authors...")

    # Start with team authors
    results = team_df.copy()

    # Check which team authors exist in each dataset
    team_author_ids = set(team_df['author_id'])

    # Log coverage for each metric
    citation_impact_coverage = len(set(citation_impact_df['author_id']) & team_author_ids)
    citation_accel_coverage = len(set(citation_accel_df['author_id']) & team_author_ids)
    contribution_coverage = len(set(contribution_df['author_id']) & team_author_ids)
    breakthroughs_coverage = len(set(breakthroughs_df['author_id']) & team_author_ids)
    ngc_coverage = len(set(ngc_df['author_id']) & team_author_ids)
    rsm_coverage = len(set(rsm_df['author_id']) & team_author_ids)
    rising_stars_coverage = len(set(rising_stars_df['author_id']) & team_author_ids)

    print(f"Team coverage by metric:")
    print(f"  - Citation Impact: {citation_impact_coverage}/{len(team_author_ids)} authors")
    print(f"  - Citation Acceleration: {citation_accel_coverage}/{len(team_author_ids)} authors")
    print(f"  - Author Contribution: {contribution_coverage}/{len(team_author_ids)} authors")
    print(f"  - Breakthroughs: {breakthroughs_coverage}/{len(team_author_ids)} authors")
    print(f"  - NGC: {ngc_coverage}/{len(team_author_ids)} authors")
    print(f"  - RSM: {rsm_coverage}/{len(team_author_ids)} authors")
    print(f"  - Rising Stars: {rising_stars_coverage}/{len(team_author_ids)} authors")

    # Merge citation impact data (TACI and ranking only, not publication count)
    results = results.merge(
        citation_impact_df[['author_id', 'TACI', 'citation_impact_ranking']],
        on='author_id', how='left'
    )
    
    # Merge citation acceleration data
    results = results.merge(
        citation_accel_df[['author_id', 'career_length', 'accel_score', 'citation_accel_ranking']],
        on='author_id', how='left'
    )
    
    # Merge contribution data (this includes total_papers which is the authoritative publication count)
    results = results.merge(
        contribution_df[['author_id', 'total_papers', 'total_citations', 'FAI', 'LAI']],
        on='author_id', how='left'
    )
    
    # Merge breakthrough data
    results = results.merge(
        breakthroughs_df[['author_id', 'weighted_BPR', 'weighted_LIPR']],
        on='author_id', how='left'
    )
    
    # Merge NGC data
    results = results.merge(
        ngc_df[['author_id', 'ngc_score']],
        on='author_id', how='left'
    )
    
    # Merge RSM data
    results = results.merge(
        rsm_df[['author_id', 'rsm_smoothed']],
        on='author_id', how='left'
    )
    
    # Merge Rising Stars data
    results = results.merge(
        rising_stars_df[['author_id', 'is_rising_star', 'star_score']],
        on='author_id', how='left'
    )
    
    # Calculate global rankings for each metric with sophisticated tiebreakers
    print("Calculating rankings with tiebreakers...")
    
    # Citation Impact ranking: rank ties by paper count (highest first)
    if 'publication_count' in citation_impact_df.columns:
        # Create temporary ranking columns for proper tiebreaking
        citation_impact_df = citation_impact_df.copy()
        citation_impact_df['temp_rank_taci'] = citation_impact_df.groupby('TACI')['publication_count'].rank(ascending=False, method='min')
        citation_impact_df = citation_impact_df.sort_values(['TACI', 'temp_rank_taci'], ascending=[False, True])
        citation_impact_df['citation_impact_ranking'] = range(1, len(citation_impact_df) + 1)
        
        citation_impact_df['temp_rank_avg'] = citation_impact_df.groupby('average_TACI')['publication_count'].rank(ascending=False, method='min')
        citation_impact_df = citation_impact_df.sort_values(['average_TACI', 'temp_rank_avg'], ascending=[False, True])
        citation_impact_df['average_taci_ranking'] = range(1, len(citation_impact_df) + 1)
        
        citation_impact_df = citation_impact_df.drop(['temp_rank_taci', 'temp_rank_avg'], axis=1)
    else:
        citation_impact_df['citation_impact_ranking'] = citation_impact_df['TACI'].rank(ascending=False, method='min')
        citation_impact_df['average_taci_ranking'] = citation_impact_df['average_TACI'].rank(ascending=False, method='min')
    
    # Citation Acceleration ranking: rank ties by total citations
    if 'total_citations' in citation_accel_df.columns:
        citation_accel_df = citation_accel_df.copy()
        citation_accel_df['temp_rank'] = citation_accel_df.groupby('accel_score')['total_citations'].rank(ascending=False, method='min')
        citation_accel_df = citation_accel_df.sort_values(['accel_score', 'temp_rank'], ascending=[False, True])
        citation_accel_df['citation_accel_ranking'] = range(1, len(citation_accel_df) + 1)
        citation_accel_df = citation_accel_df.drop(['temp_rank'], axis=1)
    else:
        citation_accel_df['citation_accel_ranking'] = citation_accel_df['accel_score'].rank(ascending=False, method='min')
    
    # FAI and LAI rankings: rank ties by total citations
    if 'total_citations' in contribution_df.columns:
        contribution_df = contribution_df.copy()
        
        # FAI ranking
        contribution_df['temp_rank_fai'] = contribution_df.groupby('FAI')['total_citations'].rank(ascending=False, method='min')
        contribution_df = contribution_df.sort_values(['FAI', 'temp_rank_fai'], ascending=[False, True])
        contribution_df['fai_ranking'] = range(1, len(contribution_df) + 1)
        
        # LAI ranking
        contribution_df['temp_rank_lai'] = contribution_df.groupby('LAI')['total_citations'].rank(ascending=False, method='min')
        contribution_df = contribution_df.sort_values(['LAI', 'temp_rank_lai'], ascending=[False, True])
        contribution_df['lai_ranking'] = range(1, len(contribution_df) + 1)
        
        contribution_df = contribution_df.drop(['temp_rank_fai', 'temp_rank_lai'], axis=1)
    else:
        contribution_df['fai_ranking'] = contribution_df['FAI'].rank(ascending=False, method='min')
        contribution_df['lai_ranking'] = contribution_df['LAI'].rank(ascending=False, method='min')
    
    # Breakthrough rankings: rank ties by paper count (highest first)
    if 'paper_count' in breakthroughs_df.columns:
        breakthroughs_df = breakthroughs_df.copy()
        
        # BPR ranking
        breakthroughs_df['temp_rank_bpr'] = breakthroughs_df.groupby('weighted_BPR')['paper_count'].rank(ascending=False, method='min')
        breakthroughs_df = breakthroughs_df.sort_values(['weighted_BPR', 'temp_rank_bpr'], ascending=[False, True])
        breakthroughs_df['weighted_bpr_ranking'] = range(1, len(breakthroughs_df) + 1)
        
        # LIPR ranking
        breakthroughs_df['temp_rank_lipr'] = breakthroughs_df.groupby('weighted_LIPR')['paper_count'].rank(ascending=False, method='min')
        breakthroughs_df = breakthroughs_df.sort_values(['weighted_LIPR', 'temp_rank_lipr'], ascending=[False, True])
        breakthroughs_df['weighted_lipr_ranking'] = range(1, len(breakthroughs_df) + 1)
        
        breakthroughs_df = breakthroughs_df.drop(['temp_rank_bpr', 'temp_rank_lipr'], axis=1)
    else:
        breakthroughs_df['weighted_bpr_ranking'] = breakthroughs_df['weighted_BPR'].rank(ascending=False, method='min')
        breakthroughs_df['weighted_lipr_ranking'] = breakthroughs_df['weighted_LIPR'].rank(ascending=False, method='min')
    
    # NGC ranking: rank ties by catalyzed count
    if 'catalyzed_count' in ngc_df.columns:
        ngc_df = ngc_df.copy()
        ngc_df['temp_rank'] = ngc_df.groupby('ngc_score')['catalyzed_count'].rank(ascending=False, method='min')
        ngc_df = ngc_df.sort_values(['ngc_score', 'temp_rank'], ascending=[False, True])
        ngc_df['ngc_ranking'] = range(1, len(ngc_df) + 1)
        ngc_df = ngc_df.drop(['temp_rank'], axis=1)
    else:
        ngc_df['ngc_ranking'] = ngc_df['ngc_score'].rank(ascending=False, method='min')
    
    # RSM ranking: rank ties by unique coauthors count
    if 'unique_coauthors' in rsm_df.columns:
        rsm_df = rsm_df.copy()
        rsm_df['temp_rank'] = rsm_df.groupby('rsm_smoothed')['unique_coauthors'].rank(ascending=False, method='min')
        rsm_df = rsm_df.sort_values(['rsm_smoothed', 'temp_rank'], ascending=[False, True])
        rsm_df['rsm_ranking'] = range(1, len(rsm_df) + 1)
        rsm_df = rsm_df.drop(['temp_rank'], axis=1)
    else:
        rsm_df['rsm_ranking'] = rsm_df['rsm_smoothed'].rank(ascending=False, method='min')
    
    # Re-merge with rankings instead of raw values

    # Start fresh with team authors
    results = team_df.copy()
    
    # Merge citation impact data with ranking
    results = results.merge(
        citation_impact_df[['author_id', 'citation_impact_ranking', 'average_taci_ranking']],
        on='author_id', how='left'
    )
    
    # Merge citation acceleration data with ranking
    results = results.merge(
        citation_accel_df[['author_id', 'career_length', 'citation_accel_ranking']],
        on='author_id', how='left'
    )
    
    # Merge contribution data with rankings (keep publication and citation counts as raw values)
    results = results.merge(
        contribution_df[['author_id', 'total_papers', 'total_citations', 'fai_ranking', 'lai_ranking']],
        on='author_id', how='left'
    )
    
    # Merge breakthrough data with rankings
    results = results.merge(
        breakthroughs_df[['author_id', 'weighted_bpr_ranking', 'weighted_lipr_ranking']],
        on='author_id', how='left'
    )
    
    # Merge NGC data with ranking
    results = results.merge(
        ngc_df[['author_id', 'ngc_ranking']],
        on='author_id', how='left'
    )
    
    # Merge RSM data with ranking
    results = results.merge(
        rsm_df[['author_id', 'rsm_ranking']],
        on='author_id', how='left'
    )
    
    # Merge Rising Stars data
    results = results.merge(
        rising_stars_df[['author_id', 'is_rising_star', 'star_score']],
        on='author_id', how='left'
    )
    
    # Rename columns to match requested format
    results = results.rename(columns={
        'total_papers': 'publication_count',
        'total_citations': 'citation_count'
    })
    
    # Fill missing values with appropriate defaults
    results['is_rising_star'] = results['is_rising_star'].fillna(False)
    results['star_score'] = results['star_score'].fillna(0.0)
    
    # Reorder columns as requested (all metrics now show rankings)
    final_columns = [
        'author_id', 'author_name', 'publication_count', 'career_length', 
        'citation_count', 'citation_impact_ranking', 'average_taci_ranking', 'citation_accel_ranking',
        'fai_ranking', 'lai_ranking', 'weighted_bpr_ranking', 'weighted_lipr_ranking', 
        'ngc_ranking', 'rsm_ranking', 'is_rising_star', 'star_score'
    ]
    
    # Handle column name variations and ensure all columns exist
    column_mapping = {}
    
    for old_col, new_col in column_mapping.items():
        if old_col in results.columns:
            results = results.rename(columns={old_col: new_col})
    
    # Add missing columns with NaN values if they don't exist
    for col in final_columns:
        if col not in results.columns:
            results[col] = np.nan
    
    # Sort by original order to preserve input sequence instead of citation impact ranking
    results = results.sort_values('original_order', ascending=True)
    
    # Select and reorder columns (excluding original_order)
    results = results[final_columns]
    
    # Data cleaning: Convert all ranking columns to integers (but handle NaN values)
    ranking_columns = ['citation_impact_ranking', 'average_taci_ranking', 'citation_accel_ranking', 'fai_ranking', 
                      'lai_ranking', 'weighted_bpr_ranking', 'weighted_lipr_ranking',
                      'ngc_ranking', 'rsm_ranking']
    integer_columns = ['publication_count', 'career_length', 'citation_count']
    
    # Convert ranking columns to integers (but keep NaN as NaN)
    for col in ranking_columns + integer_columns:
        if col in results.columns:
            # Keep NaN as NaN, but convert non-NaN values to integers
            results[col] = results[col].apply(lambda x: int(x) if pd.notna(x) else x)
    
    # Save to CSV
    results.to_csv(output_file, index=False)
    
    print(f"\nResults saved to {output_file}")
    print(f"\nSummary:")
    print(f"Total team authors processed: {len(results)}")
    print(f"Authors with citation impact ranking: {results['citation_impact_ranking'].notna().sum()}")
    print(f"Authors with average TACI ranking: {results['average_taci_ranking'].notna().sum()}")
    print(f"Authors with citation acceleration ranking: {results['citation_accel_ranking'].notna().sum()}")
    print(f"Authors with FAI ranking: {results['fai_ranking'].notna().sum()}")
    print(f"Authors with LAI ranking: {results['lai_ranking'].notna().sum()}")
    print(f"Authors with breakthrough rankings: {results['weighted_bpr_ranking'].notna().sum()}")
    print(f"Authors with NGC ranking: {results['ngc_ranking'].notna().sum()}")
    print(f"Authors with RSM ranking: {results['rsm_ranking'].notna().sum()}")
    print(f"Authors marked as rising stars: {results['is_rising_star'].sum()}")
    
    # Display top performers (only those with citation impact data)
    top_performers = results[results['citation_impact_ranking'].notna()]
    
    if len(top_performers) > 0:
        print(f"\nTeam authors with global rankings:")
        for idx, row in top_performers.iterrows():
            rank_str = f"{int(row['citation_impact_ranking']):4d}" if pd.notna(row['citation_impact_ranking']) else "N/A "
            avg_taci_str = f"{int(row['average_taci_ranking']):4d}" if pd.notna(row['average_taci_ranking']) else "N/A "
            fai_rank_str = f"{int(row['fai_ranking']):4d}" if pd.notna(row['fai_ranking']) else "N/A "
            lai_rank_str = f"{int(row['lai_ranking']):4d}" if pd.notna(row['lai_ranking']) else "N/A "
            pub_str = f"{int(row['publication_count']):3d}" if pd.notna(row['publication_count']) else "N/A"
            
            print(f"{row['author_name']:25} | Citation: {rank_str} | "
                  f"Avg TACI: {avg_taci_str} | FAI: {fai_rank_str} | "
                  f"LAI: {lai_rank_str} | Pubs: {pub_str}")
    else:
        print(f"\nNo team authors found in citation impact rankings.")
    
    # Show authors missing from key metrics
    missing_citation_impact = results[results['citation_impact_ranking'].isna()]
    if len(missing_citation_impact) > 0:
        print(f"\nTeam authors not found in citation impact rankings:")
        for idx, row in missing_citation_impact.iterrows():
            print(f"  - {row['author_name']} (ID: {row['author_id']})")
    
    return results

if __name__ == "__main__":
    # Define file paths for different teams
    input_file = "cmu_team.txt"
    output_file = "cmu_team_rankings.csv"
    compile_team_metrics(input_file, output_file)

