import pandas as pd
import numpy as np
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import threading
import json
from pathlib import Path

def calculate_citation_acceleration_vectorized(authorships_df, citation_details_df, authors_meta_df, 
                                             n_years=5, k_prior=5):
    """
    Vectorized calculation of citation acceleration scores.
    
    Parameters:
    - n_years: Number of recent years to use for regression
    - k_prior: Smoothing factor for Bayesian adjustment
    """
    print('Building citation profiles with vectorized operations...')
    
    # Create paper-to-citations mapping using vectorized operations
    print('Aggregating citations by paper and year...')
    paper_year_citations = citation_details_df.groupby(['target_paper_id', 'year_cited']).size().reset_index(name='citation_count')
    
    # Merge with authorships to get author-paper-year citations
    print('Mapping citations to authors...')
    author_paper_citations = authorships_df[['author_id', 'paper_id']].merge(
        paper_year_citations, 
        left_on='paper_id', 
        right_on='target_paper_id', 
        how='left'
    ).fillna(0)
    
    # Aggregate citations by author and year
    print('Aggregating citations by author and year...')
    author_year_citations = author_paper_citations.groupby(['author_id', 'year_cited'])['citation_count'].sum().reset_index()
    
    # Filter out zero citation years (from fillna)
    author_year_citations = author_year_citations[author_year_citations['citation_count'] > 0]
    
    print('Calculating acceleration scores using vectorized linear regression...')
    
    # Get unique authors who have citations
    authors_with_citations = author_year_citations['author_id'].unique()
    
    # Calculate accelerations for all authors at once
    acceleration_results = []
    
    # Group by author for vectorized processing
    grouped = author_year_citations.groupby('author_id')
    
    # First pass: collect all individual slopes for calculating field average
    all_slopes = []
    author_data = {}
    
    for author_id, group in grouped:
        years = group['year_cited'].values
        citations = group['citation_count'].values
        
        if len(years) < 2:
            continue
            
        # Sort by year
        sort_idx = np.argsort(years)
        years_sorted = years[sort_idx]
        citations_sorted = citations[sort_idx]
        
        # Use only recent years
        if len(years_sorted) > n_years:
            years_recent = years_sorted[-n_years:]
            citations_recent = citations_sorted[-n_years:]
        else:
            years_recent = years_sorted
            citations_recent = citations_sorted
            
        if len(years_recent) >= 2:
            # Calculate slope using vectorized operations
            X = years_recent.reshape(-1, 1)
            y = citations_recent
            
            # Use numpy for faster linear regression calculation
            X_mean = np.mean(X)
            y_mean = np.mean(y)
            numerator = np.sum((X.flatten() - X_mean) * (y - y_mean))
            denominator = np.sum((X.flatten() - X_mean) ** 2)
            
            if denominator != 0:
                slope = numerator / denominator
                all_slopes.append(slope)
                author_data[author_id] = {
                    'slope': slope,
                    'n_points': len(years_recent),
                    'year_citations': dict(zip(group['year_cited'], group['citation_count']))
                }
    
    # Calculate field-wide prior
    m_prior = np.mean(all_slopes) if all_slopes else 0.0
    print(f'Field-wide average acceleration (m_prior): {m_prior:.4f}')
    
    # Second pass: calculate smoothed accelerations
    print('Calculating smoothed acceleration scores...')
    
    # Get all authors from authorships (including those without citations)
    all_authors = authorships_df['author_id'].unique()
    
    # Create author name mapping
    author_names = authorships_df.groupby('author_id')['author_name'].first().to_dict()
    
    results = []
    
    for author_id in all_authors:
        # Get author metadata
        meta = authors_meta_df[authors_meta_df['author_id'] == author_id]
        if not meta.empty:
            first_name = meta.iloc[0]['first_name'] if pd.notna(meta.iloc[0]['first_name']) else ''
            last_name = meta.iloc[0]['last_name'] if pd.notna(meta.iloc[0]['last_name']) else ''
            career_length = meta.iloc[0]['career_length'] if pd.notna(meta.iloc[0]['career_length']) else ''
            author_name = f"{first_name} {last_name}".strip()
        else:
            author_name = author_names.get(author_id, '')
            career_length = ''
        
        # Calculate acceleration
        if author_id in author_data:
            data = author_data[author_id]
            m = data['slope']
            n_points = data['n_points']
            year_citations = data['year_citations']
            
            # Bayesian smoothing
            accel_score = (n_points * m + k_prior * m_prior) / (n_points + k_prior)
        else:
            accel_score = 0.0
            year_citations = {}
        
        results.append({
            'author_id': author_id,
            'author_name': author_name,
            'career_length': career_length,
            'accel_score': accel_score,
            'citations_by_year': json.dumps(year_citations, sort_keys=True)
        })
    
    return pd.DataFrame(results)

def load_data():
    """Load the required CSV files from data/database"""
    print("Loading data files...")
    
    # Load authorships data
    authorships_path = Path("data/database/authorships.csv")
    if not authorships_path.exists():
        raise FileNotFoundError(f"Authorships file not found: {authorships_path}")
    
    authorships_df = pd.read_csv(authorships_path, usecols=['author_id', 'paper_id', 'author_name'])
    print(f"Loaded authorships data: {len(authorships_df)} records")
    
    # Load citation details data
    citation_details_path = Path("data/database/citation_details.csv")
    if not citation_details_path.exists():
        raise FileNotFoundError(f"Citation details file not found: {citation_details_path}")
    
    citation_details_df = pd.read_csv(citation_details_path, usecols=['target_paper_id', 'year_cited'])
    print(f"Loaded citation details data: {len(citation_details_df)} records")
    
    # Load authors metadata
    authors_meta_path = Path("data/database/megatable_authors.csv")
    if not authors_meta_path.exists():
        raise FileNotFoundError(f"Authors metadata file not found: {authors_meta_path}")
    
    authors_meta_df = pd.read_csv(authors_meta_path, usecols=['author_id', 'first_name', 'last_name', 'career_length'])
    print(f"Loaded authors metadata: {len(authors_meta_df)} records")
    
    # Filter out invalid citation years
    citation_details_df = citation_details_df[citation_details_df['year_cited'] > 0]
    print(f"Using {len(citation_details_df)} valid citations")
    
    return authorships_df, citation_details_df, authors_meta_df

class CitationAccelInteractiveApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Citation Acceleration Calculator - Interactive")
        self.root.geometry("1000x700")
        
        # Data storage
        self.authorships_df = None
        self.citation_details_df = None
        self.authors_meta_df = None
        self.current_results_df = None
        
        # Load data
        self.load_data()
        
        # Create GUI
        self.create_widgets()
        
    def load_data(self):
        """Load all required data files"""
        try:
            self.authorships_df, self.citation_details_df, self.authors_meta_df = load_data()
            print(f"Data loaded successfully")
            
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
        title_label = ttk.Label(main_frame, text="Citation Acceleration Calculator", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Parameters frame
        params_frame = ttk.LabelFrame(main_frame, text="Parameters", padding="10")
        params_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        # N years lookback window parameter
        ttk.Label(params_frame, text="N Years Lookback:").grid(row=0, column=0, padx=(0, 10))
        self.n_years_var = tk.StringVar(value="5")
        n_years_values = [str(i) for i in range(3, 11)]  # 3 to 10 years
        self.n_years_combo = ttk.Combobox(params_frame, textvariable=self.n_years_var, 
                                         values=n_years_values, state="readonly", width=10)
        self.n_years_combo.grid(row=0, column=1, padx=(0, 20))
        
        # K prior parameter (fixed for now)
        ttk.Label(params_frame, text="K Prior (Smoothing):").grid(row=0, column=2, padx=(0, 10))
        self.k_prior_var = tk.StringVar(value="5")
        k_prior_values = [str(i) for i in range(1, 11)]  # 1 to 10
        self.k_prior_combo = ttk.Combobox(params_frame, textvariable=self.k_prior_var, 
                                         values=k_prior_values, state="readonly", width=10)
        self.k_prior_combo.grid(row=0, column=3, padx=(0, 20))
        
        # Calculate button
        self.calc_button = ttk.Button(main_frame, text="Calculate Acceleration", command=self.calculate_acceleration)
        self.calc_button.grid(row=2, column=0, columnspan=2, pady=(0, 10))
        
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
        self.tree = ttk.Treeview(results_frame, columns=("rank", "name", "career_length", "accel_score"), 
                                show="headings", height=15)
        self.tree.heading("rank", text="Rank")
        self.tree.heading("name", text="Author Name")
        self.tree.heading("career_length", text="Career Length")
        self.tree.heading("accel_score", text="Acceleration Score")
        
        # Set column widths with some stretchable columns
        self.tree.column("rank", width=60, minwidth=50, stretch=False)
        self.tree.column("name", width=400, minwidth=300, stretch=True)
        self.tree.column("career_length", width=120, minwidth=100, stretch=False)
        self.tree.column("accel_score", width=150, minwidth=120, stretch=False)
        
        # Store initial column configuration
        self.initial_columns = ("rank", "name", "career_length", "accel_score")
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def calculate_acceleration(self):
        """Calculate acceleration in a separate thread to avoid blocking the GUI"""
        self.calc_button.config(state="disabled")
        self.progress_var.set("Calculating...")
        
        # Start calculation in separate thread
        thread = threading.Thread(target=self._calculate_acceleration_thread)
        thread.daemon = True
        thread.start()
    
    def _calculate_acceleration_thread(self):
        """Calculate acceleration in background thread"""
        try:
            n_years = int(self.n_years_var.get())
            k_prior = int(self.k_prior_var.get())
            
            self.progress_var.set("Calculating citation acceleration scores...")
            
            # Calculate acceleration scores
            result = calculate_citation_acceleration_vectorized(
                self.authorships_df, self.citation_details_df, self.authors_meta_df,
                n_years=n_years, k_prior=k_prior
            )
            
            self.progress_var.set("Processing results...")
            
            # Sort by acceleration score (descending)
            result = result.sort_values('accel_score', ascending=False)
            
            # Round acceleration scores to 4 decimal places
            result['accel_score'] = result['accel_score'].round(4)
            
            # Store results for toggle functionality
            self.current_results_df = result.copy()
            
            # Update GUI with results
            self.root.after(0, self._update_results, result)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Calculation failed: {str(e)}"))
            self.root.after(0, lambda: self.progress_var.set("Error occurred"))
        finally:
            self.root.after(0, lambda: self.calc_button.config(state="normal"))
    
    def toggle_results_view(self):
        """Toggle between showing top and bottom results"""
        if self.current_results_df is None:
            messagebox.showwarning("Warning", "No results available. Please calculate acceleration first.")
            return
        
        current_view = self.toggle_var.get()
        
        if current_view == "Top":
            # Switch to bottom results
            self.toggle_var.set("Bottom")
            self.toggle_button.config(text="Show Top Results")
            self._update_results(self.current_results_df, show_bottom=True)
        else:
            # Switch to top results
            self.toggle_var.set("Top")
            self.toggle_button.config(text="Show Bottom Results")
            self._update_results(self.current_results_df, show_bottom=False)
    
    def _update_results(self, results_df, show_bottom=False):
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
            rank = i + 1
            name = row['author_name'] if pd.notna(row['author_name']) else f"Author {row['author_id']}"
            career_length = row['career_length'] if pd.notna(row['career_length']) else "N/A"
            accel_score = row['accel_score']
            
            self.tree.insert("", "end", values=(rank, name, career_length, f"{accel_score:.4f}"))
        
        self.progress_var.set(f"Completed! Showing {view_text} 30 of {len(results_df)} authors")

def main():
    root = tk.Tk()
    app = CitationAccelInteractiveApp(root)
    root.mainloop()

if __name__ == "__main__":
    main() 