import pandas as pd
import numpy as np
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import math
import threading

def calculate_paper_impact_vectorized(citations_df, papers_df, current_year=2025, lambda_decay=0.1, mu_decay=0.1):
    """
    Vectorized calculation of PaperImpact using pandas operations.
    
    Formula: PaperImpact(p) = sum(exp(-lambda * (T_current - T_c)) * exp(-mu * (T_c - T_p)))
    """
    # Create a paper_year lookup dictionary for fast access
    paper_year_lookup = dict(zip(papers_df['paper_id'], papers_df['year']))
    
    # Filter out invalid citation years (0 or negative)
    valid_citations = citations_df[citations_df['year_cited'] > 0].copy()
    print(f"Filtered out {len(citations_df) - len(valid_citations)} citations with invalid years")
    
    # Add paper publication year to citations dataframe
    valid_citations['paper_year'] = valid_citations['target_paper_id'].map(paper_year_lookup)
    
    # Remove citations to papers not in our dataset
    valid_citations = valid_citations.dropna(subset=['paper_year'])
    
    # Vectorized calculation of time differences
    valid_citations['recency_diff'] = current_year - valid_citations['year_cited']
    valid_citations['velocity_diff'] = valid_citations['year_cited'] - valid_citations['paper_year']
    
    # Clamp values to prevent overflow
    max_exponent = 700
    valid_citations['recency_diff'] = np.clip(valid_citations['recency_diff'], -max_exponent, max_exponent)
    valid_citations['velocity_diff'] = np.clip(valid_citations['velocity_diff'], -max_exponent, max_exponent)
    
    # Vectorized exponential calculations
    valid_citations['recency_factor'] = np.exp(-lambda_decay * valid_citations['recency_diff'])
    valid_citations['velocity_factor'] = np.exp(-mu_decay * valid_citations['velocity_diff'])
    valid_citations['citation_impact'] = valid_citations['recency_factor'] * valid_citations['velocity_factor']
    
    # Group by target paper and sum impacts
    paper_impacts = valid_citations.groupby('target_paper_id')['citation_impact'].sum().to_dict()
    
    # Initialize all papers with 0 impact (including those without citations)
    all_paper_impacts = dict.fromkeys(papers_df['paper_id'], 0.0)
    all_paper_impacts.update(paper_impacts)
    
    papers_with_citations = len(paper_impacts)
    print(f"Papers with citations: {papers_with_citations}")
    print(f"Papers without citations: {len(papers_df) - papers_with_citations}")
    
    return all_paper_impacts

def calculate_author_shares_vectorized(authorships_df):
    """
    Vectorized calculation of author shares for all papers.
    """
    # Calculate weights based on position (matching original logic exactly)
    authorships_df = authorships_df.copy()
    
    # Default weight for middle authors
    authorships_df['weight'] = 0.5
    
    # Set weights using the same if/elif logic as original
    # First author takes precedence over last author (for single-author papers)
    authorships_df.loc[authorships_df['is_last_author'] & ~authorships_df['is_first_author'], 'weight'] = 0.8
    authorships_df.loc[authorships_df['is_first_author'], 'weight'] = 1.0
    
    # Calculate total weight per paper
    paper_total_weights = authorships_df.groupby('paper_id')['weight'].sum()
    
    # Map total weights back to authorships
    authorships_df['total_paper_weight'] = authorships_df['paper_id'].map(paper_total_weights)
    
    # Calculate author share
    authorships_df['author_share'] = authorships_df['weight'] / authorships_df['total_paper_weight']
    
    return authorships_df[['author_id', 'paper_id', 'author_share']]

def calculate_author_total_citations_vectorized(authorships_df, citation_details_df):
    """
    Vectorized calculation of total citation count for each author.
    """
    # Calculate citations for each paper (vectorized)
    paper_citations = citation_details_df.groupby('target_paper_id').size().reset_index(name='citation_count')
    
    # Create a mapping from paper_id to citation_count for fast lookup
    paper_citation_map = dict(zip(paper_citations['target_paper_id'], paper_citations['citation_count']))
    
    # Get all papers by each author and calculate total citations (vectorized)
    author_citations = authorships_df.groupby('author_id')['paper_id'].apply(
        lambda papers: sum(paper_citation_map.get(paper_id, 0) for paper_id in papers)
    ).reset_index(name='total_citations')
    
    return author_citations

def calculate_all_taci_scores_vectorized(authorships_df, paper_impacts, authors_df):
    """
    Vectorized calculation of TACI scores for all authors.
    """
    # Calculate author shares for all papers
    author_shares_df = calculate_author_shares_vectorized(authorships_df)
    
    # Convert paper_impacts to Series for vectorized operations
    paper_impacts_series = pd.Series(paper_impacts)
    
    # Map paper impacts to authorships
    author_shares_df['paper_impact'] = author_shares_df['paper_id'].map(paper_impacts_series).fillna(0)
    
    # Calculate contribution of each authorship to TACI
    author_shares_df['taci_contribution'] = author_shares_df['author_share'] * author_shares_df['paper_impact']
    
    # Group by author and calculate totals
    author_taci = author_shares_df.groupby('author_id').agg({
        'taci_contribution': 'sum',
        'paper_id': 'count'
    }).rename(columns={'paper_id': 'paper_count', 'taci_contribution': 'total_taci'})
    
    # Apply log normalization to total TACI
    author_taci['log_normalized_taci'] = np.log1p(author_taci['total_taci'])
    
    # Calculate average TACI (average of raw TACI scores, then log normalize)
    author_taci['average_taci'] = np.log1p(author_taci['total_taci'] / author_taci['paper_count'])
    
    return author_taci

class TACIInteractiveApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TACI Calculator - Interactive")
        self.root.geometry("800x600")
        
        # Data storage
        self.authorships_df = None
        self.citation_details_df = None
        self.papers_df = None
        self.authors_df = None
        self.paper_impacts = None
        self.current_results_df = None
        self.current_metric_col = None
        
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
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="TACI Calculator", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Parameters frame
        params_frame = ttk.LabelFrame(main_frame, text="Parameters", padding="10")
        params_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        # Lambda parameter
        ttk.Label(params_frame, text="Lambda Decay:").grid(row=0, column=0, padx=(0, 10))
        self.lambda_var = tk.StringVar(value="0.1")
        lambda_values = [f"{i/10:.1f}" for i in range(1, 11)]  # 0.1 to 1.0
        self.lambda_combo = ttk.Combobox(params_frame, textvariable=self.lambda_var, values=lambda_values, state="readonly", width=10)
        self.lambda_combo.grid(row=0, column=1, padx=(0, 20))
        
        # Mu parameter
        ttk.Label(params_frame, text="Mu Decay:").grid(row=0, column=2, padx=(0, 10))
        self.mu_var = tk.StringVar(value="0.1")
        mu_values = [f"{i/10:.1f}" for i in range(1, 11)]  # 0.1 to 1.0
        self.mu_combo = ttk.Combobox(params_frame, textvariable=self.mu_var, values=mu_values, state="readonly", width=10)
        self.mu_combo.grid(row=0, column=3, padx=(0, 20))
        
        # Metric selection
        ttk.Label(params_frame, text="Metric:").grid(row=0, column=4, padx=(0, 10))
        self.metric_var = tk.StringVar(value="TACI")
        metric_values = ["TACI", "Average TACI"]
        self.metric_combo = ttk.Combobox(params_frame, textvariable=self.metric_var, values=metric_values, state="readonly", width=15)
        self.metric_combo.grid(row=0, column=5, padx=(0, 20))
        
        # Minimum paper count
        ttk.Label(params_frame, text="Min Papers:").grid(row=0, column=6, padx=(0, 10))
        self.min_papers_var = tk.StringVar(value="5")
        min_papers_values = [str(i) for i in range(1, 21)]  # 1 to 20 papers
        self.min_papers_combo = ttk.Combobox(params_frame, textvariable=self.min_papers_var, values=min_papers_values, state="readonly", width=10)
        self.min_papers_combo.grid(row=0, column=7)
        
        # Rank button
        self.rank_button = ttk.Button(main_frame, text="Calculate Rankings", command=self.calculate_rankings)
        self.rank_button.grid(row=2, column=0, columnspan=2, pady=(0, 10))
        
        # Toggle button for top/bottom results
        self.toggle_var = tk.StringVar(value="Top")
        self.toggle_button = ttk.Button(main_frame, text="Show Top Results", command=self.toggle_results_view)
        self.toggle_button.grid(row=2, column=2, columnspan=1, pady=(0, 10))
        
        # Progress bar
        self.progress_var = tk.StringVar(value="Ready")
        self.progress_label = ttk.Label(main_frame, textvariable=self.progress_var)
        self.progress_label.grid(row=3, column=0, columnspan=3, pady=(0, 10))
        
        # Results frame
        results_frame = ttk.LabelFrame(main_frame, text="Top 30 Results", padding="10")
        results_frame.grid(row=4, column=0, columnspan=3, sticky="nsew")
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Create treeview for results
        self.tree = ttk.Treeview(results_frame, columns=("rank", "name", "papers", "citations", "metric"), show="headings", height=15)
        self.tree.heading("rank", text="Rank")
        self.tree.heading("name", text="Author Name")
        self.tree.heading("papers", text="Paper Count")
        self.tree.heading("citations", text="Total Citations")
        self.tree.heading("metric", text="Metric Value")
        
        self.tree.column("rank", width=50)
        self.tree.column("name", width=250)
        self.tree.column("papers", width=100)
        self.tree.column("citations", width=120)
        self.tree.column("metric", width=150)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def calculate_rankings(self):
        """Calculate rankings in a separate thread to avoid blocking the GUI"""
        self.rank_button.config(state="disabled")
        self.progress_var.set("Calculating...")
        
        # Start calculation in separate thread
        thread = threading.Thread(target=self._calculate_rankings_thread)
        thread.daemon = True
        thread.start()
    
    def _calculate_rankings_thread(self):
        """Calculate rankings in background thread"""
        try:
            lambda_decay = float(self.lambda_var.get())
            mu_decay = float(self.mu_var.get())
            metric_choice = self.metric_var.get()
            min_papers = int(self.min_papers_var.get())
            
            self.progress_var.set("Calculating paper impacts...")
            
            # Calculate paper impacts
            paper_impacts = calculate_paper_impact_vectorized(
                self.citation_details_df, self.papers_df, 
                lambda_decay=lambda_decay, mu_decay=mu_decay
            )
            
            self.progress_var.set("Filtering authors...")
            
            # Filter authors with minimum paper count
            if self.authors_df is not None:
                authors_with_many_papers = self.authors_df[self.authors_df['publication_count'] >= min_papers]
                filtered_author_ids = set(authors_with_many_papers['author_id'].unique())
                if self.authorships_df is not None:
                    filtered_authorships = self.authorships_df[self.authorships_df['author_id'].isin(filtered_author_ids)]
                else:
                    raise ValueError("authorships_df is None")
            else:
                raise ValueError("authors_df is None")
            
            self.progress_var.set("Calculating TACI scores...")
            
            # Calculate TACI scores
            author_taci_results = calculate_all_taci_scores_vectorized(filtered_authorships, paper_impacts, self.authors_df)
            
            self.progress_var.set("Calculating citation counts...")
            
            # Calculate total citations for each author
            author_citations = calculate_author_total_citations_vectorized(filtered_authorships, self.citation_details_df)
            
            self.progress_var.set("Processing results...")
            
            # Merge with author names and citations
            if self.authors_df is not None:
                author_names = self.authors_df[['author_id', 'first_name', 'last_name']].copy()
                author_names['author_full_name'] = author_names['first_name'].fillna('') + ' ' + author_names['last_name'].fillna('')
                author_names['author_full_name'] = author_names['author_full_name'].str.strip()
                
                # Merge results with names and citations
                results_df = author_taci_results.reset_index().merge(
                    author_names[['author_id', 'author_full_name']], 
                    on='author_id', how='left'
                ).merge(
                    author_citations[['author_id', 'total_citations']],
                    on='author_id', how='left'
                )
                
                # Handle missing names
                missing_names = results_df['author_full_name'].isna()
                if missing_names.any() and self.authorships_df is not None:
                    fallback_names = self.authorships_df.groupby('author_id')['author_name'].first()
                    results_df.loc[missing_names, 'author_full_name'] = results_df.loc[missing_names, 'author_id'].map(fallback_names)
                
                # Fill missing citations with 0
                results_df['total_citations'] = results_df['total_citations'].fillna(0)
            else:
                # Fallback if authors_df is None
                results_df = author_taci_results.reset_index().copy()
                results_df['author_full_name'] = f"Author {results_df['author_id']}"
                results_df = results_df.merge(
                    author_citations[['author_id', 'total_citations']],
                    on='author_id', how='left'
                )
                results_df['total_citations'] = results_df['total_citations'].fillna(0)
            
            # Rename columns
            results_df = results_df.rename(columns={
                'log_normalized_taci': 'TACI',
                'average_taci': 'average_TACI'
            })
            
            # Sort by chosen metric
            if metric_choice == "TACI":
                results_df = results_df.sort_values('TACI', ascending=False)
                metric_col = 'TACI'
            else:
                results_df = results_df.sort_values('average_TACI', ascending=False)
                metric_col = 'average_TACI'
            
            # Normalize scores to 0-100 scale
            if len(results_df) > 0:
                max_metric = results_df[metric_col].max()
                if max_metric > 0:
                    results_df[metric_col] = (results_df[metric_col] / max_metric) * 100
            
            # Round scores
            results_df[metric_col] = results_df[metric_col].round(2)
            
            # Store results for toggle functionality
            self.current_results_df = results_df.copy()
            self.current_metric_col = metric_col
            
            # Update GUI with results
            self.root.after(0, self._update_results, results_df, metric_col)
            
        except Exception as e:
            error_message = f"Calculation failed: {str(e)}"
            self.root.after(0, lambda: messagebox.showerror("Error", error_message))
            self.root.after(0, lambda: self.progress_var.set("Error occurred"))
        finally:
            self.root.after(0, lambda: self.rank_button.config(state="normal"))
    

    
    def toggle_results_view(self):
        """Toggle between showing top and bottom results"""
        if self.current_results_df is None or self.current_metric_col is None:
            messagebox.showwarning("Warning", "No results available. Please calculate rankings first.")
            return
        
        current_view = self.toggle_var.get()
        
        if current_view == "Top":
            # Switch to bottom results
            self.toggle_var.set("Bottom")
            self.toggle_button.config(text="Show Top Results")
            self._update_results(self.current_results_df, self.current_metric_col, show_bottom=True)
        else:
            # Switch to top results
            self.toggle_var.set("Top")
            self.toggle_button.config(text="Show Bottom Results")
            self._update_results(self.current_results_df, self.current_metric_col, show_bottom=False)
    
    def _update_results(self, results_df, metric_col, show_bottom=False):
        """Update the results table"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Get top or bottom 30 results
        if show_bottom:
            display_results = results_df.tail(30)
            view_text = "bottom"
        else:
            display_results = results_df.head(30)
            view_text = "top"
        
        for i, (idx, row) in enumerate(display_results.iterrows()):
            rank = i + 1  # Use enumerate to get proper sequential ranking
            name = row['author_full_name'] if pd.notna(row['author_full_name']) else f"Author {row['author_id']}"
            papers = row['paper_count']
            citations = row['total_citations']
            metric_value = row[metric_col]
            
            self.tree.insert("", "end", values=(rank, name, papers, citations, f"{metric_value:.2f}"))
        
        self.progress_var.set(f"Completed! Showing {view_text} 30 of {len(results_df)} authors")

def main():
    root = tk.Tk()
    app = TACIInteractiveApp(root)
    root.mainloop()

if __name__ == "__main__":
    main() 