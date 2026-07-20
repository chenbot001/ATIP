import pandas as pd
import numpy as np
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import math
import threading
from typing import Dict, List

def calculate_paper_impacts(citation_details_df: pd.DataFrame, papers_df: pd.DataFrame, 
                          lambda_decay=0.7, mu_decay=0.7, current_year=2025) -> Dict[int, float]:
    """
    Calculates the time-weighted impact for every paper.
    Uses configurable lambda and mu suitable for identifying Rising Stars.
    """
    paper_year_lookup = dict(zip(papers_df['paper_id'], papers_df['year']))
    
    citations = citation_details_df[citation_details_df['year_cited'] > 0].copy()
    citations['paper_year'] = citations['target_paper_id'].map(paper_year_lookup)
    citations.dropna(subset=['paper_year'], inplace=True)

    citations['recency_diff'] = current_year - citations['year_cited']
    citations['velocity_diff'] = citations['year_cited'] - citations['paper_year']

    recency_factor = np.exp(-lambda_decay * citations['recency_diff'])
    velocity_factor = np.exp(-mu_decay * citations['velocity_diff'])
    citations['citation_impact'] = recency_factor * velocity_factor
    
    paper_impacts = citations.groupby('target_paper_id')['citation_impact'].sum().to_dict()
    
    return paper_impacts

def calculate_taci_avg(authorships_df: pd.DataFrame, paper_impacts: Dict[int, float]) -> pd.DataFrame:
    """Calculates the average TACI score for each author."""
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
    ).reset_index()
    
    author_taci['taci_avg'] = author_taci['taci_contribution'] / author_taci['paper_count']
    return author_taci[['author_id', 'taci_avg']]

def calculate_citation_acceleration(authorships_df: pd.DataFrame, citation_details_df: pd.DataFrame, 
                                  author_ids: List[int], lookback_years=5, smoothing_k=5) -> pd.DataFrame:
    """Calculates the Citation Acceleration (CA) for a cohort of authors."""
    citations = citation_details_df.merge(authorships_df[['paper_id', 'author_id']], 
                                        left_on='target_paper_id', right_on='paper_id')
    citations = citations[citations['author_id'].isin(author_ids)]

    velocity_df = citations.groupby(['author_id', 'year_cited']).size().reset_index(name='citations')

    def get_slope(data: pd.DataFrame) -> float:
        data = data.tail(lookback_years)
        if len(data) < 2:
            return 0.0
        relative_years = data['year_cited'] - data['year_cited'].min()
        slope, _ = np.polyfit(relative_years, data['citations'], 1)
        return slope

    raw_acceleration = velocity_df.groupby('author_id', group_keys=False).apply(
        lambda x: get_slope(x), include_groups=False).to_dict()

    ca_df = pd.DataFrame({'author_id': author_ids})
    ca_df['ca_raw'] = ca_df['author_id'].map(raw_acceleration).fillna(0)
    
    paper_counts = authorships_df[authorships_df['author_id'].isin(author_ids)].groupby('author_id').size()
    ca_df['paper_count'] = ca_df['author_id'].map(paper_counts).fillna(0)

    ca_prior = ca_df['ca_raw'].mean()
    
    ca_df['ca_smoothed'] = ((ca_df['paper_count'] * ca_df['ca_raw']) + (smoothing_k * ca_prior)) / (ca_df['paper_count'] + smoothing_k)
    
    return ca_df[['author_id', 'ca_smoothed']]

def calculate_author_ratios(authorships_df: pd.DataFrame) -> pd.DataFrame:
    """Calculates publication count, FAR, and LAR for all authors."""
    author_stats = authorships_df.groupby('author_id').agg(
        publication_count=('paper_id', 'nunique'),
        first_author_count=('is_first_author', 'sum'),
        last_author_count=('is_last_author', 'sum')
    ).reset_index()
    
    author_stats['far'] = author_stats['first_author_count'] / author_stats['publication_count']
    author_stats['lar'] = author_stats['last_author_count'] / author_stats['publication_count']
    
    return author_stats[['author_id', 'publication_count', 'far', 'lar']]

def calculate_rising_stars(authors_df: pd.DataFrame, papers_df: pd.DataFrame, 
                         authorships_df: pd.DataFrame, citation_details_df: pd.DataFrame,
                         lambda_decay=0.7, mu_decay=0.7, ca_lookback_years=5,
                         pub_count_threshold=10, lar_threshold=0.25, far_threshold=0.50,
                         smoothing_k=5, rising_star_percentile=0.95) -> pd.DataFrame:
    """
    Main function to orchestrate the Rising Star calculation with configurable parameters.
    """
    
    # Step 1: Calculate contribution ratios for all authors
    author_ratios_df = calculate_author_ratios(authorships_df)

    # Step 2: Merge ratios with the main authors dataframe
    authors_with_stats_df = authors_df.merge(author_ratios_df, on='author_id', how='left', suffixes=('', '_calc'))
    
    # Use the calculated publication count and handle any naming conflicts
    if 'publication_count_calc' in authors_with_stats_df.columns:
        authors_with_stats_df['publication_count'] = authors_with_stats_df['publication_count_calc']
        authors_with_stats_df.drop('publication_count_calc', axis=1, inplace=True)
    
    # Fill NaN values with 0 for authors with no publications
    authors_with_stats_df['publication_count'] = authors_with_stats_df['publication_count'].fillna(0)
    authors_with_stats_df['far'] = authors_with_stats_df['far'].fillna(0)
    authors_with_stats_df['lar'] = authors_with_stats_df['lar'].fillna(0)

    # Step 3: Apply the multi-factor filter to define the cohort
    is_low_pub_count = authors_with_stats_df['publication_count'] < pub_count_threshold
    is_low_lar = authors_with_stats_df['lar'] < lar_threshold
    is_high_far = authors_with_stats_df['far'] > far_threshold

    early_career_authors = authors_with_stats_df[is_low_pub_count & is_low_lar & is_high_far]

    cohort_author_ids = early_career_authors['author_id'].tolist()
    
    if len(cohort_author_ids) == 0:
        # Return empty DataFrame with correct structure
        empty_df = pd.DataFrame(columns=['author_id', 'author_name', 'publication_count', 'far', 'lar', 'star_score'])
        return empty_df
    
    authorships_cohort = authorships_df[authorships_df['author_id'].isin(cohort_author_ids)]

    # --- Calculate Metrics for the Cohort ---
    paper_impacts = calculate_paper_impacts(citation_details_df, papers_df, lambda_decay, mu_decay)
    taci_scores = calculate_taci_avg(authorships_cohort, paper_impacts)
    ca_scores = calculate_citation_acceleration(authorships_cohort, citation_details_df, 
                                              cohort_author_ids, ca_lookback_years, smoothing_k)

    # --- Combine and Normalize ---
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
    score_threshold = results_df['star_score'].quantile(rising_star_percentile)
    results_df['is_rising_star'] = results_df['star_score'] >= score_threshold
    
    # --- Format Final Output ---
    results_df['author_name'] = results_df['first_name'].fillna('') + ' ' + results_df['last_name'].fillna('')
    results_df['author_name'] = results_df['author_name'].str.strip()
    
    final_cols = ['author_id', 'author_name', 'publication_count', 'far', 'lar', 'star_score']
    
    return results_df[final_cols].sort_values(by='star_score', ascending=False)

class RisingStarInteractiveApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Rising Star Calculator - Interactive")
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)  # Set minimum window size
        
        # Data storage
        self.authorships_df = None
        self.citation_details_df = None
        self.papers_df = None
        self.authors_df = None
        self.current_results_df = None
        
        # Load data
        self.load_data()
        
        # Create GUI
        self.create_widgets()
        
    def load_data(self):
        """Load all required data files"""
        try:
            data_dir = "data/database"
            
            print("Loading data files...")
            self.authorships_df = pd.read_csv(os.path.join(data_dir, "authorships.csv"))
            self.citation_details_df = pd.read_csv(os.path.join(data_dir, "citation_details.csv"))
            self.papers_df = pd.read_csv(os.path.join(data_dir, "megatable_papers.csv"))
            self.authors_df = pd.read_csv(os.path.join(data_dir, "megatable_authors.csv"))
            
            print(f"Loaded {len(self.authorships_df)} authorships")
            print(f"Loaded {len(self.citation_details_df)} citation details")
            print(f"Loaded {len(self.papers_df)} papers")
            print(f"Loaded {len(self.authors_df)} authors")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load data: {str(e)}")
            self.root.destroy()
    
    def create_widgets(self):
        """Create the GUI widgets"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(5, weight=1)  # Make the results frame expandable
        
        # Title
        title_label = ttk.Label(main_frame, text="Rising Star Calculator", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # Parameters frame
        params_frame = ttk.LabelFrame(main_frame, text="Adjustable Parameters", padding="10")
        params_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
        # TACI Parameters section
        taci_frame = ttk.LabelFrame(params_frame, text="TACI Parameters", padding="5")
        taci_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        # Lambda parameter
        ttk.Label(taci_frame, text="Lambda Decay:").grid(row=0, column=0, padx=(0, 10))
        self.lambda_var = tk.StringVar(value="0.7")
        lambda_values = [f"{i/10:.1f}" for i in range(1, 21)]  # 0.1 to 2.0
        self.lambda_combo = ttk.Combobox(taci_frame, textvariable=self.lambda_var, values=lambda_values, state="readonly", width=8)
        self.lambda_combo.grid(row=0, column=1, padx=(0, 20))
        
        # Mu parameter
        ttk.Label(taci_frame, text="Mu Decay:").grid(row=0, column=2, padx=(0, 10))
        self.mu_var = tk.StringVar(value="0.7")
        mu_values = [f"{i/10:.1f}" for i in range(1, 21)]  # 0.1 to 2.0
        self.mu_combo = ttk.Combobox(taci_frame, textvariable=self.mu_var, values=mu_values, state="readonly", width=8)
        self.mu_combo.grid(row=0, column=3)
        
        # Citation Acceleration Parameters section
        ca_frame = ttk.LabelFrame(params_frame, text="Citation Acceleration Parameters", padding="5")
        ca_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        # CA Lookback Years
        ttk.Label(ca_frame, text="CA Lookback Years:").grid(row=0, column=0, padx=(0, 10))
        self.ca_lookback_var = tk.StringVar(value="5")
        ca_lookback_values = [str(i) for i in range(2, 11)]  # 2 to 10 years
        self.ca_lookback_combo = ttk.Combobox(ca_frame, textvariable=self.ca_lookback_var, values=ca_lookback_values, state="readonly", width=8)
        self.ca_lookback_combo.grid(row=0, column=1)
        
        # Threshold Parameters section
        threshold_frame = ttk.LabelFrame(params_frame, text="Early Career Filter Thresholds", padding="5")
        threshold_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        # Publication Count Threshold
        ttk.Label(threshold_frame, text="Max Publication Count:").grid(row=0, column=0, padx=(0, 10))
        self.pub_count_var = tk.StringVar(value="10")
        pub_count_values = [str(i) for i in range(5, 21)]  # 5 to 20 papers
        self.pub_count_combo = ttk.Combobox(threshold_frame, textvariable=self.pub_count_var, values=pub_count_values, state="readonly", width=8)
        self.pub_count_combo.grid(row=0, column=1, padx=(0, 20))
        
        # LAR Threshold
        ttk.Label(threshold_frame, text="Max LAR (Last Author Ratio):").grid(row=0, column=2, padx=(0, 10))
        self.lar_threshold_var = tk.StringVar(value="0.25")
        lar_threshold_values = [f"{i/100:.2f}" for i in range(10, 51, 5)]  # 0.10 to 0.50
        self.lar_threshold_combo = ttk.Combobox(threshold_frame, textvariable=self.lar_threshold_var, values=lar_threshold_values, state="readonly", width=8)
        self.lar_threshold_combo.grid(row=0, column=3, padx=(0, 20))
        
        # FAR Threshold
        ttk.Label(threshold_frame, text="Min FAR (First Author Ratio):").grid(row=0, column=4, padx=(0, 10))
        self.far_threshold_var = tk.StringVar(value="0.50")
        far_threshold_values = [f"{i/100:.2f}" for i in range(30, 81, 5)]  # 0.30 to 0.80
        self.far_threshold_combo = ttk.Combobox(threshold_frame, textvariable=self.far_threshold_var, values=far_threshold_values, state="readonly", width=8)
        self.far_threshold_combo.grid(row=0, column=5)
        
        # Fixed Parameters Display
        fixed_frame = ttk.LabelFrame(params_frame, text="Fixed Parameters", padding="5")
        fixed_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        ttk.Label(fixed_frame, text="Smoothing Constant: 5", font=("Arial", 9)).grid(row=0, column=0, padx=(0, 20))
        ttk.Label(fixed_frame, text="Rising Star Percentile: 0.95 (Top 5%)", font=("Arial", 9)).grid(row=0, column=1)
        
        # Calculate button
        self.calculate_button = ttk.Button(main_frame, text="Calculate Rising Stars", command=self.calculate_rising_stars)
        self.calculate_button.grid(row=3, column=0, pady=(10, 10))
        
        # Progress bar
        self.progress_var = tk.StringVar(value="Ready")
        self.progress_label = ttk.Label(main_frame, textvariable=self.progress_var)
        self.progress_label.grid(row=4, column=0, pady=(0, 10))
        
        # Results frame
        results_frame = ttk.LabelFrame(main_frame, text="Rising Star Results", padding="10")
        results_frame.grid(row=5, column=0, sticky="nsew")
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Create treeview for results
        self.tree = ttk.Treeview(results_frame, columns=("rank", "author_id", "name", "pub_count", "far", "lar", "score"), show="headings")
        self.tree.heading("rank", text="Rank")
        self.tree.heading("author_id", text="Author ID")
        self.tree.heading("name", text="Author Name")
        self.tree.heading("pub_count", text="Pub Count")
        self.tree.heading("far", text="FAR")
        self.tree.heading("lar", text="LAR")
        self.tree.heading("score", text="Rising Star Score")
        
        self.tree.column("rank", width=60)
        self.tree.column("author_id", width=100)
        self.tree.column("name", width=250)
        self.tree.column("pub_count", width=80)
        self.tree.column("far", width=80)
        self.tree.column("lar", width=80)
        self.tree.column("score", width=150)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def calculate_rising_stars(self):
        """Calculate rising stars in a separate thread to avoid blocking the GUI"""
        self.calculate_button.config(state="disabled")
        self.progress_var.set("Calculating...")
        
        # Start calculation in separate thread
        thread = threading.Thread(target=self._calculate_rising_stars_thread)
        thread.daemon = True
        thread.start()
    
    def _calculate_rising_stars_thread(self):
        """Calculate rising stars in background thread"""
        try:
            # Check if data is loaded
            if (self.authors_df is None or self.papers_df is None or 
                self.authorships_df is None or self.citation_details_df is None):
                raise ValueError("Data not properly loaded")
            
            # Get parameter values
            lambda_decay = float(self.lambda_var.get())
            mu_decay = float(self.mu_var.get())
            ca_lookback_years = int(self.ca_lookback_var.get())
            pub_count_threshold = int(self.pub_count_var.get())
            lar_threshold = float(self.lar_threshold_var.get())
            far_threshold = float(self.far_threshold_var.get())
            
            self.progress_var.set("Identifying early career cohort...")
            
            # Calculate rising stars
            results_df = calculate_rising_stars(
                self.authors_df, self.papers_df, self.authorships_df, self.citation_details_df,
                lambda_decay=lambda_decay, mu_decay=mu_decay, ca_lookback_years=ca_lookback_years,
                pub_count_threshold=pub_count_threshold, lar_threshold=lar_threshold, 
                far_threshold=far_threshold, smoothing_k=5, rising_star_percentile=0.95
            )
            
            self.progress_var.set("Processing results...")
            
            # Store results
            self.current_results_df = results_df.copy()
            
            # Update GUI with results
            self.root.after(0, self._update_results, results_df)
            
        except Exception as e:
            error_msg = f"Calculation failed: {str(e)}"
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
            self.root.after(0, lambda: self.progress_var.set("Error occurred"))
        finally:
            self.root.after(0, lambda: self.calculate_button.config(state="normal"))
    
    def _update_results(self, results_df):
        """Update the results table"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if len(results_df) == 0:
            self.progress_var.set("No rising stars found with current parameters.")
            return
        
        # Display all results
        for i, (idx, row) in enumerate(results_df.iterrows()):
            rank = i + 1
            author_id = row['author_id']
            name = row['author_name'] if pd.notna(row['author_name']) else f"Author {author_id}"
            pub_count = int(row['publication_count']) if pd.notna(row['publication_count']) else 0
            far = f"{row['far']:.3f}" if pd.notna(row['far']) else "0.000"
            lar = f"{row['lar']:.3f}" if pd.notna(row['lar']) else "0.000"
            score = row['star_score']
            
            self.tree.insert("", "end", values=(rank, author_id, name, pub_count, far, lar, f"{score:.6f}"))
        
        self.progress_var.set(f"Completed! Found {len(results_df)} potential rising stars.")

def main():
    root = tk.Tk()
    app = RisingStarInteractiveApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
