import pandas as pd
import numpy as np

def calculate_breakthrough_paper_score():
    """
    Calculate Breakthrough Paper Score (BPS) for each author.
    
    BPS = max(ZScore + AwardBoost) for all papers by the author
    where ZScore is standardized citation count for that year
    and AwardBoost is based on awards received
    """
    
    print("Loading data files...")
    
    # Read the four CSV files
    papers_df = pd.read_csv('data/database/megatable_papers.csv')
    awards_df = pd.read_csv('data/paper_awards.csv')
    authorships_df = pd.read_csv('data/database/authorships.csv')
    authors_df = pd.read_csv('data/database/megatable_authors.csv')
    
    print(f"Loaded {len(papers_df)} papers")
    print(f"Loaded {len(awards_df)} award records")
    print(f"Loaded {len(authorships_df)} authorship records")
    print(f"Loaded {len(authors_df)} author records")
    
    # Select required columns
    papers_subset = papers_df[['paper_id', 'year', 'citation_count']].copy()
    awards_subset = awards_df[['paper_id', 'category']].copy()
    authorships_subset = authorships_df[['author_id', 'paper_id']].copy()
    authors_subset = authors_df[['author_id', 'first_name', 'last_name']].copy()
    
    # Remove papers with missing citation counts or years
    papers_subset = papers_subset.dropna(subset=['citation_count', 'year'])
    
    print(f"Papers with valid citation data: {len(papers_subset)}")
    
    # Step 1: Calculate ZScore for each paper
    print("Calculating ZScore for each paper...")
    
    # Calculate mean and std for each year
    yearly_stats = papers_subset.groupby('year')['citation_count'].agg(['mean', 'std']).reset_index()
    yearly_stats.columns = ['year', 'mean_citations', 'std_citations']
    
    # Merge with papers
    papers_with_stats = papers_subset.merge(yearly_stats, on='year', how='left')
    
    # Calculate ZScore (handle std = 0 case)
    papers_with_stats['zscore'] = papers_with_stats.apply(
        lambda row: (row['citation_count'] - row['mean_citations']) / row['std_citations'] 
        if row['std_citations'] > 0 
        else 0.0, 
        axis=1
    )
    
    print(f"Calculated ZScore for {len(papers_with_stats)} papers")
    
    # Step 2: Calculate AwardBoost for each paper
    print("Calculating AwardBoost for each paper...")
    
    def get_award_boost(category):
        if pd.isna(category):
            return 0
        category_lower = str(category).lower()
        if 'best overall paper' in category_lower:
            return 3
        elif 'outstanding paper' in category_lower:
            return 2
        elif any(x in category_lower for x in ['area chair', 'resource', 'award']):
            return 1
        else:
            return 0
    
    # Create award boost mapping
    awards_subset['award_boost'] = awards_subset['category'].apply(get_award_boost)
    award_boost_map = dict(zip(awards_subset['paper_id'], awards_subset['award_boost']))
    
    # Add award boost to papers (default 0 for papers without awards)
    papers_with_stats['award_boost'] = papers_with_stats['paper_id'].map(award_boost_map).fillna(0)
    
    print(f"Papers with awards: {(papers_with_stats['award_boost'] > 0).sum()}")
    
    # Step 3: Calculate PaperScore
    papers_with_stats['paper_score'] = papers_with_stats['zscore'] + papers_with_stats['award_boost']
    
    print("Sample paper scores:")
    print(papers_with_stats[['paper_id', 'year', 'citation_count', 'zscore', 'award_boost', 'paper_score']].head())
    
    # Step 4: Calculate BPS for each author
    print("Calculating BPS for each author...")
    
    # Merge papers with authorships
    author_papers = authorships_subset.merge(papers_with_stats, on='paper_id', how='inner')
    
    # Find maximum paper score for each author
    author_bps = author_papers.groupby('author_id')['paper_score'].max().reset_index()
    author_bps.columns = ['author_id', 'breakthrough_paper_score']
    
    print(f"Calculated BPS for {len(author_bps)} authors")
    
    # Step 5: Create author names and merge
    authors_subset['author_name'] = authors_subset.apply(
        lambda row: row['first_name'] + ' ' + row['last_name'] 
        if pd.notna(row['last_name']) 
        else row['first_name'], 
        axis=1
    )
    
    # Merge with author information
    result_df = authors_subset[['author_id', 'author_name']].merge(
        author_bps, on='author_id', how='left'
    )
    
    # Fill NaN values with 0 for authors without papers
    result_df['breakthrough_paper_score'] = result_df['breakthrough_paper_score'].fillna(0)
    
    # Step 6: Normalize BPS to 0-100 scale
    print("Normalizing BPS scores...")
    
    min_bps = result_df['breakthrough_paper_score'].min()
    max_bps = result_df['breakthrough_paper_score'].max()
    
    if max_bps > min_bps:
        result_df['breakthrough_paper_score_normalized'] = 100 * (
            (result_df['breakthrough_paper_score'] - min_bps) / (max_bps - min_bps)
        )
    else:
        result_df['breakthrough_paper_score_normalized'] = 0.0
    
    # Step 7: Save to CSV file
    output_file = 'Breakthrough_Paper_Score.csv'
    result_df.to_csv(output_file, index=False)
    
    print(f"\nBPS calculation completed!")
    print(f"Results saved to: {output_file}")
    print(f"Total authors processed: {len(result_df)}")
    
    # Display statistics
    print(f"\nStatistics:")
    print(f"Mean BPS: {result_df['breakthrough_paper_score'].mean():.4f}")
    print(f"Median BPS: {result_df['breakthrough_paper_score'].median():.4f}")
    print(f"Max BPS: {result_df['breakthrough_paper_score'].max():.4f}")
    print(f"Min BPS: {result_df['breakthrough_paper_score'].min():.4f}")
    print(f"Authors with BPS > 0: {(result_df['breakthrough_paper_score'] > 0).sum()}")
    
    print(f"\nSample results:")
    print(result_df.head(10))
    
    # Show top breakthrough paper authors
    print(f"\nTop 10 authors by breakthrough paper score:")
    top_bps = result_df.nlargest(10, 'breakthrough_paper_score')[
        ['author_name', 'breakthrough_paper_score', 'breakthrough_paper_score_normalized']
    ]
    print(top_bps)
    
    # Show distribution of award boosts
    print(f"\nAward distribution:")
    award_counts = papers_with_stats['award_boost'].value_counts().sort_index()
    for boost, count in award_counts.items():
        boost_name = {0: "No award", 1: "Other/Resource/Area Chair", 2: "Outstanding", 3: "Best Overall"}
        print(f"AwardBoost {boost} ({boost_name.get(boost, 'Unknown')}): {count} papers")
    
    return result_df

if __name__ == "__main__":
    result = calculate_breakthrough_paper_score()
