import pandas as pd
import numpy as np
import os

# --- Configuration ---
# File paths
AUTH_FILE = 'data/database/authorships.csv'
PAPER_FILE = 'data/database/megatable_papers.csv'
CITATION_FILE = 'data/database/citation_details.csv'
OUTPUT_FILE = 'data/derived_metrics/author_breakthroughs.csv'
# Smoothing factor (confidence threshold)
SMOOTHING_K = 5

# --- Data Loading and Merging ---
print('Loading data...')
authorships = pd.read_csv(AUTH_FILE, usecols=['author_id', 'author_name', 'paper_id'])
papers = pd.read_csv(PAPER_FILE, usecols=['paper_id', 'year', 'citation_count'])
citations = pd.read_csv(CITATION_FILE, usecols=['target_paper_id', 'year_cited'])

print('Merging data...')
auth_papers = pd.merge(authorships, papers, on='paper_id', how='inner')

# --- Vectorized Threshold Calculation ---
def compute_year_thresholds_vectorized(papers):
    """Compute 95th and 40th percentile citation thresholds for each year using vectorized operations."""
    print('Computing year thresholds (vectorized)...')
    
    # Remove NaN values and group by year
    papers_clean = papers.dropna(subset=['citation_count'])
    
    # Use vectorized percentile calculation
    thresholds = papers_clean.groupby('year')['citation_count'].agg([
        lambda x: np.percentile(x, 95),  # T95
        lambda x: np.percentile(x, 40)   # T40
    ]).rename(columns={'<lambda_0>': 'T95', '<lambda_1>': 'T40'})
    
    return thresholds.to_dict('index')

year_thresholds = compute_year_thresholds_vectorized(papers)

# --- Vectorized Paper Classification ---
def classify_papers_vectorized(auth_papers, year_thresholds):
    """Classify papers using vectorized operations instead of apply()."""
    print('Classifying papers (vectorized)...')
    
    # Create a DataFrame from thresholds for efficient merging
    thresholds_df = pd.DataFrame.from_dict(year_thresholds, orient='index').reset_index()
    thresholds_df.columns = ['year', 'T95', 'T40']
    
    # Merge with auth_papers to get thresholds for each paper
    auth_papers_with_thresholds = auth_papers.merge(thresholds_df, on='year', how='left')
    
    # Vectorized classification using numpy where
    conditions = [
        auth_papers_with_thresholds['citation_count'] > auth_papers_with_thresholds['T95'],
        auth_papers_with_thresholds['citation_count'] < auth_papers_with_thresholds['T40']
    ]
    choices = ['bpr', 'lipr']
    
    # Default to 'mid' for papers that don't meet either condition
    auth_papers_with_thresholds['impact_class'] = np.select(conditions, choices, default='mid')
    
    # Handle papers with no threshold data
    no_threshold_mask = auth_papers_with_thresholds['T95'].isna()
    auth_papers_with_thresholds.loc[no_threshold_mask, 'impact_class'] = 'none'
    
    return auth_papers_with_thresholds[['author_id', 'author_name', 'paper_id', 'year', 'citation_count', 'impact_class']]

auth_papers = classify_papers_vectorized(auth_papers, year_thresholds)

# --- Calculate Total Citations per Author ---
def calculate_total_citations_vectorized(authorships, citations):
    """Calculate total citations per author using vectorized operations."""
    print('Calculating total citations per author...')
    
    # Count citations per paper
    paper_citations = citations.groupby('target_paper_id').size().reset_index(name='total_paper_citations')
    
    # Merge with authorships to get author-paper-citations mapping
    author_paper_citations = authorships[['author_id', 'paper_id']].merge(
        paper_citations, 
        left_on='paper_id', 
        right_on='target_paper_id', 
        how='left'
    ).fillna(0)
    
    # Sum citations by author
    author_total_citations = author_paper_citations.groupby('author_id')['total_paper_citations'].sum().reset_index()
    author_total_citations.columns = ['author_id', 'total_citations']
    
    return author_total_citations

author_citations = calculate_total_citations_vectorized(authorships, citations)

# --- Vectorized Ratio Calculation ---
def calc_bpr_lipr_vectorized(auth_papers):
    """Calculate BPR and LIPR ratios using vectorized operations."""
    print('Aggregating by author to calculate ratios (vectorized)...')
    
    # Create dummy variables for each impact class
    auth_papers['is_bpr'] = (auth_papers['impact_class'] == 'bpr').astype(int)
    auth_papers['is_lipr'] = (auth_papers['impact_class'] == 'lipr').astype(int)
    
    # Group by author and aggregate using vectorized operations
    result = auth_papers.groupby(['author_id', 'author_name']).agg({
        'paper_id': 'count',        # Total paper count
        'is_bpr': 'sum',           # Breakthrough paper count
        'is_lipr': 'sum'           # Low-impact paper count
    }).rename(columns={
        'paper_id': 'paper_count',
        'is_bpr': 'BP',
        'is_lipr': 'LIP'
    }).reset_index()
    
    # Vectorized ratio calculations
    result['BPR'] = np.where(result['paper_count'] > 0, 
                            result['BP'] / result['paper_count'], 
                            0.0)
    result['LIPR'] = np.where(result['paper_count'] > 0, 
                             result['LIP'] / result['paper_count'], 
                             0.0)
    
    return result

result = calc_bpr_lipr_vectorized(auth_papers)

# --- Merge with total citations ---
print('Merging with total citations data...')
result = result.merge(author_citations, on='author_id', how='left')
result['total_citations'] = result['total_citations'].fillna(0).astype(int)

# --- Vectorized Confidence-Weighted Smoothing ---
def apply_smoothing_vectorized(result, smoothing_k):
    """Apply confidence-weighted smoothing using vectorized operations."""
    print('Calculating prior means for smoothing...')
    
    # Calculate priors (field-wide averages)
    bpr_prior = result['BPR'].mean()
    lipr_prior = result['LIPR'].mean()
    
    print(f'BPR prior (field average): {bpr_prior:.4f}')
    print(f'LIPR prior (field average): {lipr_prior:.4f}')
    
    print('Applying smoothing (vectorized)...')
    
    # Vectorized smoothing calculation
    n = result['paper_count']
    
    # Apply Bayesian smoothing formula vectorized
    result['weighted_BPR'] = (n * result['BPR'] + smoothing_k * bpr_prior) / (n + smoothing_k)
    result['weighted_LIPR'] = (n * result['LIPR'] + smoothing_k * lipr_prior) / (n + smoothing_k)
    
    return result

result = apply_smoothing_vectorized(result, SMOOTHING_K)

# --- Round all floating point values to 2 decimal places ---
print('Rounding floating point values to 2 decimal places...')
float_columns = ['BPR', 'LIPR', 'weighted_BPR', 'weighted_LIPR']
for col in float_columns:
    result[col] = result[col].round(2)

# --- Save Final Output ---
print(f'Saving to {OUTPUT_FILE}...')
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

# Reorder columns as specified
final_columns = [
    'author_id', 'author_name', 'paper_count', 'total_citations',
    'BP', 'BPR', 'weighted_BPR', 
    'LIP', 'LIPR', 'weighted_LIPR'
]
result = result[final_columns]

# Sort by weighted_BPR for better readability
result = result.sort_values('weighted_BPR', ascending=False)

result.to_csv(OUTPUT_FILE, index=False)

print('Breakthrough Paper Ratio calculation complete!')
print(f'Total authors processed: {len(result)}')

# Print some statistics
if len(result) > 0:
    print(f"\nBPR Statistics:")
    print(f"Mean BPR (raw): {result['BPR'].mean():.4f}")
    print(f"Mean BPR (weighted): {result['weighted_BPR'].mean():.4f}")
    print(f"Max BPR (weighted): {result['weighted_BPR'].max():.4f}")
    
    print(f"\nLIPR Statistics:")
    print(f"Mean LIPR (raw): {result['LIPR'].mean():.4f}")
    print(f"Mean LIPR (weighted): {result['weighted_LIPR'].mean():.4f}")
    print(f"Max LIPR (weighted): {result['weighted_LIPR'].max():.4f}")
    
    print(f"\nCitation Statistics:")
    non_zero_citations = result[result['total_citations'] > 0]
    print(f"Authors with citations: {len(non_zero_citations)}")
    if len(non_zero_citations) > 0:
        print(f"Mean total citations: {non_zero_citations['total_citations'].mean():.2f}")
        print(f"Median total citations: {non_zero_citations['total_citations'].median():.0f}")
        print(f"Max total citations: {non_zero_citations['total_citations'].max():.0f}")
    
print('Done.')
