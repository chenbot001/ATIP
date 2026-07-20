import pandas as pd
import numpy as np

def calculate_industry_collaboration_score():
    """
    Calculate Industry Collaboration Score (ICS) for each author.
    
    ICS = Number of collaborations with industry coauthors / Total number of collaborations
    
    Industry coauthors are identified by their latest affiliation containing specific keywords.
    """
    
    # Define industry keywords
    industry_keywords = [
        "Google", "Microsoft", "Amazon", "Meta", "Apple", 
        "Alibaba", "Tencent", "Baidu", "ByteDance", "Huawei", 
        "IBM", "NVIDIA", "Salesforce"
    ]
    
    print("Loading data files...")
    
    # Read the three CSV files
    coauthors_df = pd.read_csv('data/coauthors_by_author.csv')
    history_df = pd.read_csv('data/author_history.csv')
    authors_df = pd.read_csv('data/database/megatable_authors.csv')
    
    print(f"Loaded {len(coauthors_df)} coauthor relationships")
    print(f"Loaded {len(history_df)} author history records")
    print(f"Loaded {len(authors_df)} author records")
    
    # Get the latest affiliation for each author from history
    print("Processing author affiliations...")
    
    # Sort by author_id and assume the last record is the most recent
    history_sorted = history_df.sort_values(['author_id']).groupby('author_id').last().reset_index()
    
    # Create a mapping of author_id to whether they are industry-affiliated
    def is_industry_affiliated(affiliation):
        if pd.isna(affiliation):
            return False
        affiliation_str = str(affiliation).lower()
        return any(keyword.lower() in affiliation_str for keyword in industry_keywords)
    
    history_sorted['is_industry'] = history_sorted['affiliation'].apply(is_industry_affiliated)
    industry_status = dict(zip(history_sorted['author_id'], history_sorted['is_industry']))
    
    print(f"Identified {sum(history_sorted['is_industry'])} industry-affiliated authors")
    
    # Calculate ICS for each author
    print("Calculating Industry Collaboration Score for each author...")
    
    # Select required columns from authors table
    authors_subset = authors_df[['author_id', 'first_name', 'last_name']].copy()
    
    # Create author_name column
    authors_subset['author_name'] = authors_subset.apply(
        lambda row: row['first_name'] + ' ' + row['last_name'] 
        if pd.notna(row['last_name']) 
        else row['first_name'], 
        axis=1
    )
    
    # Initialize columns
    authors_subset['industry_collab_score'] = 0.0
    
    # Calculate ICS for each author
    for idx, author_row in authors_subset.iterrows():
        author_id = author_row['author_id']
        
        # Get all coauthors for this author
        author_coauthors = coauthors_df[coauthors_df['author_id'] == author_id]
        
        if len(author_coauthors) == 0:
            continue
            
        # Calculate total collaborations
        total_collaborations = author_coauthors['num_collaborations'].sum()
        
        # Calculate industry collaborations
        industry_collaborations = 0
        for _, coauthor_row in author_coauthors.iterrows():
            coauthor_id = coauthor_row['coauthor_id']
            num_collab = coauthor_row['num_collaborations']
            
            # Check if this coauthor is industry-affiliated
            if industry_status.get(coauthor_id, False):
                industry_collaborations += num_collab
        
        # Calculate ICS
        if total_collaborations > 0:
            ics = industry_collaborations / total_collaborations
        else:
            ics = 0.0
            
        authors_subset.at[idx, 'industry_collab_score'] = ics
        
        # Print progress every 1000 authors
        if (idx + 1) % 1000 == 0:
            print(f"Processed {idx + 1}/{len(authors_subset)} authors")
    
    # Normalize ICS to 0-100 scale
    print("Normalizing scores...")
    
    min_ics = authors_subset['industry_collab_score'].min()
    max_ics = authors_subset['industry_collab_score'].max()
    
    if max_ics > min_ics:
        authors_subset['industry_collab_score_normalized'] = 100 * (
            (authors_subset['industry_collab_score'] - min_ics) / (max_ics - min_ics)
        )
    else:
        authors_subset['industry_collab_score_normalized'] = 0.0
    
    # Select final columns
    result_df = authors_subset[[
        'author_id', 'author_name', 'industry_collab_score', 'industry_collab_score_normalized'
    ]]
    
    # Save to CSV file
    output_file = 'Industry_Collaboration_Score.csv'
    result_df.to_csv(output_file, index=False)
    
    print(f"\nICS calculation completed!")
    print(f"Results saved to: {output_file}")
    print(f"Total authors processed: {len(result_df)}")
    
    # Display statistics
    print(f"\nStatistics:")
    print(f"Mean ICS: {result_df['industry_collab_score'].mean():.4f}")
    print(f"Median ICS: {result_df['industry_collab_score'].median():.4f}")
    print(f"Max ICS: {result_df['industry_collab_score'].max():.4f}")
    print(f"Min ICS: {result_df['industry_collab_score'].min():.4f}")
    print(f"Authors with ICS > 0: {(result_df['industry_collab_score'] > 0).sum()}")
    
    print(f"\nSample results:")
    print(result_df.head(10))
    
    # Show top industry collaborators
    print(f"\nTop 10 authors by industry collaboration score:")
    top_industry = result_df.nlargest(10, 'industry_collab_score')[['author_name', 'industry_collab_score', 'industry_collab_score_normalized']]
    print(top_industry)
    
    return result_df

if __name__ == "__main__":
    result = calculate_industry_collaboration_score()
