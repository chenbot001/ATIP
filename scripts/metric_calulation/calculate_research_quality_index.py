"""
Research Quality Index (RQI) Calculator

This script calculates the Research Quality Index for all authors based on the methodology
described in the ATIP metric documentation. The RQI is calculated in two steps:

1. Paper Quality Index (PQI): A weighted combination of Citation, Award, and Venue scores
2. Research Quality Index (RQI): Author-level aggregation of PQI weighted by contribution

PERFORMANCE OPTIMIZATIONS:
- Replaced all for loops with pandas vectorized operations
- Used numpy.where() for conditional calculations
- Optimized data types during CSV loading
- Added timing decorators for performance monitoring
- Used efficient groupby operations and merges
- Minimized memory usage with selective column operations

Author: ATIP Team
Date: August 2025
"""

import pandas as pd
import numpy as np
import os
from pathlib import Path
import json
from datetime import datetime
import time
import warnings
warnings.filterwarnings('ignore')

def timing_decorator(func):
    """Decorator to time function execution."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"  ⏱️  {func.__name__} completed in {end_time - start_time:.2f} seconds")
        return result
    return wrapper

class ResearchQualityCalculator:
    def __init__(self, data_dir: str, current_year: int = 2025):
        """
        Initialize the Research Quality Calculator.
        
        Args:
            data_dir (str): Path to the data directory containing CSV files
            current_year (int): Current year for time-weighted calculations
        """
        self.data_dir = Path(data_dir)
        self.current_year = current_year
        
        # Default weights for PQI calculation (Citation > Award > Venue)
        self.weights = {
            'citation': 0.6,    # Primary signal - dynamic, data-driven
            'award': 0.3,       # Secondary signal - expert validation
            'venue': 0.1        # Tertiary signal - pre-publication static
        }
        
        # Time-weighted citation parameters
        self.lambda_recency = 0.1   # Recency decay constant
        self.mu_velocity = 0.2      # Velocity decay constant
        
        # Load data
        self.load_data()
        
    def load_data(self):
        """Load all required data files."""
        print("Loading data files...")
        
        # Load main data files with optimized dtypes where possible
        print("  Loading papers...")
        self.papers_df = pd.read_csv(
            self.data_dir / 'database' / 'megatable_papers.csv',
            dtype={'paper_id': 'int64', 'year': 'int16'}
        )
        
        print("  Loading citations...")
        self.citations_df = pd.read_csv(
            self.data_dir / 'database' / 'citation_details.csv',
            dtype={'target_paper_id': 'int64', 'citing_paper_id': 'int64', 'year_cited': 'int16'}
        )
        
        print("  Loading authorships...")
        self.authorships_df = pd.read_csv(
            self.data_dir / 'database' / 'authorships.csv',
            dtype={'author_id': 'int64', 'paper_id': 'int64', 'is_first_author': 'bool', 'is_last_author': 'bool'}
        )
        
        print(f"Loaded {len(self.papers_df)} papers")
        print(f"Loaded {len(self.citations_df)} citations")
        print(f"Loaded {len(self.authorships_df)} authorships")
        
    @timing_decorator
    def calculate_time_weighted_citations(self):
        """Calculate time-weighted citation scores for all papers."""
        print("Calculating time-weighted citation scores...")
        
        # Merge citations with paper publication years more efficiently
        citations_with_years = self.citations_df.merge(
            self.papers_df[['paper_id', 'year']], 
            left_on='target_paper_id', 
            right_on='paper_id',
            how='inner'  # Use inner join to filter out missing papers
        )
        
        # Vectorized calculation of time-weighted citation scores
        citations_with_years['recency_factor'] = np.exp(
            -self.lambda_recency * (self.current_year - citations_with_years['year_cited'])
        )
        citations_with_years['velocity_factor'] = np.exp(
            -self.mu_velocity * (citations_with_years['year_cited'] - citations_with_years['year'])
        )
        citations_with_years['weighted_citation'] = (
            citations_with_years['recency_factor'] * citations_with_years['velocity_factor']
        )
        
        # Efficient aggregation by paper
        paper_citation_scores = citations_with_years.groupby('target_paper_id', as_index=False).agg({
            'weighted_citation': 'sum'
        })
        paper_citation_scores.rename(columns={'target_paper_id': 'paper_id'}, inplace=True)
        
        return paper_citation_scores
    
    @timing_decorator
    def calculate_award_scores(self):
        """Calculate award scores for all papers."""
        print("Calculating award scores...")
        
        # Vectorized award scoring using pandas operations
        award_df = self.papers_df[['paper_id', 'awards']].copy()
        
        # Convert awards to string and check for empty/null values
        award_df['awards_str'] = award_df['awards'].astype(str)
        
        # Vectorized award scoring - any non-empty award gets score of 1.0
        award_df['award_score'] = np.where(
            (award_df['awards_str'] == '{}') | 
            (award_df['awards_str'] == 'nan') | 
            (award_df['awards'].isna()),
            0.0,
            1.0
        )
        
        return award_df[['paper_id', 'award_score']]
    
    @timing_decorator
    def calculate_venue_scores(self):
        """Calculate venue scores based on venue and track information."""
        print("Calculating venue scores...")
        
        # Vectorized venue scoring using pandas operations
        venue_df = self.papers_df[['paper_id', 'venue', 'track']].copy()
        
        # Convert to lowercase for comparison
        venue_df['venue_lower'] = venue_df['venue'].astype(str).str.lower()
        venue_df['track_lower'] = venue_df['track'].astype(str).str.lower()
        
        # Define venue scoring logic using vectorized operations
        venue_df['venue_score'] = 0.8  # Default score
        
        # Tier C: Findings papers
        venue_df.loc[venue_df['venue_lower'].str.contains('findings', na=False), 'venue_score'] = 0.4
        
        # Tier B: Demo papers
        venue_df.loc[
            venue_df['track_lower'].str.contains('demo|demonstration', na=False), 
            'venue_score'
        ] = 0.5
        
        # Tier A: Short papers
        venue_df.loc[venue_df['track_lower'].str.contains('short', na=False), 'venue_score'] = 0.8
        
        # Tier S: Top venues (assuming main proceedings)
        top_venues = ['acl', 'emnlp', 'naacl', 'coling', 'eacl']
        venue_df.loc[venue_df['venue_lower'].isin(top_venues), 'venue_score'] = 1.0
        
        return venue_df[['paper_id', 'venue_score']]
    
    @timing_decorator
    def calculate_paper_quality_index(self):
        """Calculate Paper Quality Index (PQI) for all papers."""
        print("Calculating Paper Quality Index (PQI)...")
        
        # Get all component scores
        citation_scores = self.calculate_time_weighted_citations()
        award_scores = self.calculate_award_scores()
        venue_scores = self.calculate_venue_scores()
        
        # Start with all papers
        pqi_df = self.papers_df[['paper_id']].copy()
        
        # Merge all scores efficiently with left joins
        pqi_df = pqi_df.merge(citation_scores, on='paper_id', how='left')
        pqi_df = pqi_df.merge(award_scores, on='paper_id', how='left')
        pqi_df = pqi_df.merge(venue_scores, on='paper_id', how='left')
        
        # Fill missing values using vectorized operations
        pqi_df['weighted_citation'] = pqi_df['weighted_citation'].fillna(0)
        pqi_df['award_score'] = pqi_df['award_score'].fillna(0)
        pqi_df['venue_score'] = pqi_df['venue_score'].fillna(0)
        
        # Vectorized normalization to 0-1 scale
        citation_max = pqi_df['weighted_citation'].max()
        award_max = pqi_df['award_score'].max()
        venue_max = pqi_df['venue_score'].max()
        
        pqi_df['citation_norm'] = np.where(citation_max > 0, pqi_df['weighted_citation'] / citation_max, 0)
        pqi_df['award_norm'] = np.where(award_max > 0, pqi_df['award_score'] / award_max, 0)
        pqi_df['venue_norm'] = np.where(venue_max > 0, pqi_df['venue_score'] / venue_max, 0)
        
        # Vectorized PQI calculation
        pqi_df['pqi'] = (
            self.weights['citation'] * pqi_df['citation_norm'] +
            self.weights['award'] * pqi_df['award_norm'] +
            self.weights['venue'] * pqi_df['venue_norm']
        )
        
        return pqi_df[['paper_id', 'pqi', 'citation_norm', 'award_norm', 'venue_norm']]
    
    @timing_decorator
    def calculate_author_shares(self):
        """Calculate author contribution shares for each paper."""
        print("Calculating author contribution shares...")
        
        # Start with authorships dataframe
        author_shares_df = self.authorships_df[['author_id', 'paper_id', 'is_first_author', 'is_last_author']].copy()
        
        # Vectorized weight calculation
        author_shares_df['weight'] = np.where(
            author_shares_df['is_first_author'], 1.0,
            np.where(author_shares_df['is_last_author'], 0.8, 0.5)
        )
        
        # Calculate total weight per paper
        paper_weights = author_shares_df.groupby('paper_id')['weight'].sum().reset_index()
        paper_weights.rename(columns={'weight': 'total_weight'}, inplace=True)
        
        # Merge back and calculate shares
        author_shares_df = author_shares_df.merge(paper_weights, on='paper_id', how='left')
        author_shares_df['author_share'] = np.where(
            author_shares_df['total_weight'] > 0,
            author_shares_df['weight'] / author_shares_df['total_weight'],
            0
        )
        
        return author_shares_df[['author_id', 'paper_id', 'weight', 'author_share']]
    
    @timing_decorator
    def calculate_research_quality_index(self):
        """Calculate Research Quality Index (RQI) for all authors."""
        print("Calculating Research Quality Index (RQI)...")
        
        # Get PQI scores and author shares
        pqi_df = self.calculate_paper_quality_index()
        author_shares_df = self.calculate_author_shares()
        
        # Merge PQI with author shares
        author_pqi = author_shares_df.merge(
            pqi_df[['paper_id', 'pqi']], 
            on='paper_id', 
            how='left'
        )
        
        # Fill missing PQI values
        author_pqi['pqi'] = author_pqi['pqi'].fillna(0)
        
        # Calculate weighted PQI and total shares for each author
        author_pqi['weighted_pqi'] = author_pqi['author_share'] * author_pqi['pqi']
        
        # Aggregate by author
        rqi_results = author_pqi.groupby('author_id').agg({
            'weighted_pqi': 'sum',
            'author_share': 'sum',
            'paper_id': 'count'
        }).reset_index()
        
        # Calculate RQI as weighted average
        rqi_results['rqi'] = np.where(
            rqi_results['author_share'] > 0,
            rqi_results['weighted_pqi'] / rqi_results['author_share'],
            0
        )
        
        # Rename columns for clarity
        rqi_results.rename(columns={
            'paper_id': 'total_papers',
            'author_share': 'total_contribution_share'
        }, inplace=True)
        
        return rqi_results
    
    def add_author_info(self, rqi_df):
        """Add author names and other info to RQI results."""
        print("Adding author information...")
        
        # Get unique author info
        author_info = self.authorships_df.groupby('author_id').agg({
            'author_name': 'first'
        }).reset_index()
        
        # Merge with RQI results
        rqi_with_info = rqi_df.merge(author_info, on='author_id', how='left')
        
        return rqi_with_info
    
    def run_calculation(self, output_file=None):
        """Run the complete RQI calculation pipeline."""
        print("=" * 60)
        print("RESEARCH QUALITY INDEX (RQI) CALCULATION")
        print("=" * 60)
        print(f"Current year: {self.current_year}")
        print(f"Weights - Citation: {self.weights['citation']}, Award: {self.weights['award']}, Venue: {self.weights['venue']}")
        print()
        
        # Calculate RQI
        rqi_results = self.calculate_research_quality_index()
        
        # Add author information
        rqi_final = self.add_author_info(rqi_results)
        
        # Sort by RQI score (descending)
        rqi_final = rqi_final.sort_values('rqi', ascending=False).reset_index(drop=True)
        
        # Add ranking
        rqi_final['rqi_rank'] = range(1, len(rqi_final) + 1)
        
        # Reorder columns
        column_order = [
            'rqi_rank', 'author_id', 'author_name', 'rqi', 
            'total_papers', 'total_contribution_share', 'weighted_pqi'
        ]
        rqi_final = rqi_final[column_order]
        
        # Display summary statistics
        print(f"Calculated RQI for {len(rqi_final)} authors")
        print(f"RQI Statistics:")
        print(f"  Mean: {rqi_final['rqi'].mean():.4f}")
        print(f"  Median: {rqi_final['rqi'].median():.4f}")
        print(f"  Std: {rqi_final['rqi'].std():.4f}")
        print(f"  Min: {rqi_final['rqi'].min():.4f}")
        print(f"  Max: {rqi_final['rqi'].max():.4f}")
        print()
        
        # Display top 10 authors
        print("Top 10 Authors by Research Quality Index:")
        print("-" * 40)
        top_10 = rqi_final.head(10)
        for _, row in top_10.iterrows():
            print(f"{row['rqi_rank']:2d}. {row['author_name']:<30} RQI: {row['rqi']:.4f} (Papers: {row['total_papers']})")
        
        # Save results if output file specified
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            rqi_final.to_csv(output_path, index=False)
            print(f"\nResults saved to: {output_path}")
            
            # Also save metadata
            metadata = {
                'calculation_date': datetime.now().isoformat(),
                'current_year': self.current_year,
                'weights': self.weights,
                'lambda_recency': self.lambda_recency,
                'mu_velocity': self.mu_velocity,
                'total_authors': len(rqi_final),
                'total_papers': len(self.papers_df),
                'total_citations': len(self.citations_df)
            }
            
            metadata_path = output_path.parent / f"{output_path.stem}_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            print(f"Metadata saved to: {metadata_path}")
        
        return rqi_final


def main():
    """Main function to run the RQI calculation."""
    # Set up paths
    project_root = Path(__file__).parent.parent
    data_dir = project_root / 'data'
    output_dir = project_root / 'data' / 'derived_metrics'
    
    # Initialize calculator
    calculator = ResearchQualityCalculator(data_dir=str(data_dir))
    
    # Run calculation
    output_file = output_dir / 'research_quality_index.csv'
    results = calculator.run_calculation(output_file=str(output_file))
    
    print(f"\nRQI calculation completed successfully!")
    print(f"Results available in DataFrame and saved to {output_file}")


if __name__ == "__main__":
    main()
