import pandas as pd
import numpy as np

def calculate_early_career_velocity():
    """
    Calculate Early Career Velocity (ECV) for each author.
    
    ECV = Total citations of papers published in first 3 years / min(career_length, 3)
    
    Where first 3 years is defined as:
    career_start_year = 2025 - career_length + 1
    early_career_end_year = career_start_year + 2
    """
    
    # Read the three CSV files
    print("Loading data files...")
    authors_df = pd.read_csv('data/database/megatable_authors.csv')
    authorships_df = pd.read_csv('data/database/authorships.csv')
    papers_df = pd.read_csv('data/database/megatable_papers.csv')
    
    print(f"Loaded {len(authors_df)} authors, {len(authorships_df)} authorships, {len(papers_df)} papers")
    
    # Select only the required columns
    authors_df = authors_df[['author_id', 'first_name', 'last_name', 'career_length']]
    authorships_df = authorships_df[['author_id', 'paper_id']]
    papers_df = papers_df[['paper_id', 'year', 'citation_count']]
    
    # Remove rows with missing critical values (but keep rows with missing last_name)
    authors_df = authors_df.dropna(subset=['author_id', 'first_name', 'career_length'])
    papers_df = papers_df.dropna()
    
    # Calculate career start year and early career end year for each author
    authors_df['career_start_year'] = 2025 - authors_df['career_length'] + 1
    authors_df['early_career_end_year'] = authors_df['career_start_year'] + 2
    
    # Create author name: use first_name + last_name if both exist, otherwise just first_name
    authors_df['author_name'] = authors_df.apply(
        lambda row: row['first_name'] + ' ' + row['last_name'] 
        if pd.notna(row['last_name']) 
        else row['first_name'], 
        axis=1
    )
    
    # Initialize ECV column
    authors_df['ecv'] = 0.0
    
    print("Calculating ECV for each author...")
    
    # Process each author
    for idx, author_row in authors_df.iterrows():
        author_id = author_row['author_id']
        career_start_year = author_row['career_start_year']
        early_career_end_year = author_row['early_career_end_year']
        career_length = author_row['career_length']
        
        # Get all papers by this author
        author_papers = authorships_df[authorships_df['author_id'] == author_id]['paper_id'].tolist()
        
        if not author_papers:
            continue
            
        # Get papers published in the early career period (first 3 years)
        early_career_papers = papers_df[
            (papers_df['paper_id'].isin(author_papers)) &
            (papers_df['year'] >= career_start_year) &
            (papers_df['year'] <= early_career_end_year)
        ]
        
        # Calculate total citations for early career papers
        total_early_citations = early_career_papers['citation_count'].sum()
        
        # Calculate ECV
        denominator = min(career_length, 3)
        if denominator > 0:
            ecv = total_early_citations / denominator
        else:
            ecv = 0.0
            
        authors_df.at[idx, 'ecv'] = ecv
        
        # Print progress every 1000 authors
        if (idx + 1) % 1000 == 0:
            print(f"Processed {idx + 1}/{len(authors_df)} authors")
    
    # Select only the required output columns
    result_df = authors_df[['author_id', 'author_name', 'ecv']]
    
    # Save to CSV file
    output_file = 'Early_Career_Velocity.csv'
    result_df.to_csv(output_file, index=False)
    
    print(f"\nECV calculation completed!")
    print(f"Results saved to: {output_file}")
    print(f"Total authors processed: {len(result_df)}")
    print(f"\nSample results:")
    print(result_df.head(10))
    
    # Display some statistics
    print(f"\nStatistics:")
    print(f"Mean ECV: {result_df['ecv'].mean():.2f}")
    print(f"Median ECV: {result_df['ecv'].median():.2f}")
    print(f"Max ECV: {result_df['ecv'].max():.2f}")
    print(f"Min ECV: {result_df['ecv'].min():.2f}")
    print(f"Authors with ECV > 0: {(result_df['ecv'] > 0).sum()}")
    
    return result_df

if __name__ == "__main__":
    result = calculate_early_career_velocity()
