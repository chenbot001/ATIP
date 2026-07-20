import pandas as pd
import numpy as np
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import threading

def compute_year_thresholds_vectorized(papers, bpr_percentile, lipr_percentile):
    """Compute percentile citation thresholds for each year using vectorized operations."""
    print(f'Computing year thresholds (vectorized) - BPR: {bpr_percentile}%, LIPR: {lipr_percentile}%...')
    
    # Remove NaN values and group by year
    papers_clean = papers.dropna(subset=['citation_count'])
    
    # Use vectorized percentile calculation
    thresholds = papers_clean.groupby('year')['citation_count'].agg([
        lambda x: np.percentile(x, bpr_percentile),  # T_BPR
        lambda x: np.percentile(x, lipr_percentile)  # T_LIPR
    ]).rename(columns={'<lambda_0>': 'T_BPR', '<lambda_1>': 'T_LIPR'})
    
    return thresholds.to_dict('index')

def classify_papers_vectorized(auth_papers, year_thresholds):
    """Classify papers using vectorized operations instead of apply()."""
    print('Classifying papers (vectorized)...')
    
    # Create a DataFrame from thresholds for efficient merging
    thresholds_df = pd.DataFrame.from_dict(year_thresholds, orient='index').reset_index()
    thresholds_df.columns = ['year', 'T_BPR', 'T_LIPR']
    
    # Merge with auth_papers to get thresholds for each paper
    auth_papers_with_thresholds = auth_papers.merge(thresholds_df, on='year', how='left')
    
    # Vectorized classification using numpy where
    conditions = [
        auth_papers_with_thresholds['citation_count'] > auth_papers_with_thresholds['T_BPR'],
        auth_papers_with_thresholds['citation_count'] < auth_papers_with_thresholds['T_LIPR']
    ]
    choices = ['bpr', 'lipr']
    
    # Default to 'mid' for papers that don't meet either condition
    auth_papers_with_thresholds['impact_class'] = np.select(conditions, choices, default='mid')
    
    # Handle papers with no threshold data
    no_threshold_mask = auth_papers_with_thresholds['T_BPR'].isna()
    auth_papers_with_thresholds.loc[no_threshold_mask, 'impact_class'] = 'none'
    
    return auth_papers_with_thresholds[['author_id', 'author_name', 'paper_id', 'year', 'citation_count', 'impact_class']]

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

class BPRInteractiveApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BPR Calculator - Interactive")
        self.root.geometry("900x700")
        
        # Data storage
        self.authorships_df = None
        self.papers_df = None
        self.current_results_df = None
        self.current_metric_col = None
        
        # Load data
        self.load_data()
        
        # Create GUI
        self.create_widgets()
        
    def load_data(self):
        """Load all required data files"""
        try:
            print('Loading data...')
            self.authorships_df = pd.read_csv('data/database/authorships.csv', 
                                            usecols=['author_id', 'author_name', 'paper_id'])
            self.papers_df = pd.read_csv('data/database/megatable_papers.csv', 
                                       usecols=['paper_id', 'year', 'citation_count'])
            
            print('Merging data...')
            self.auth_papers = pd.merge(self.authorships_df, self.papers_df, on='paper_id', how='inner')
            
            print(f"Loaded {len(self.authorships_df)} authorships")
            print(f"Loaded {len(self.papers_df)} papers")
            print(f"Merged into {len(self.auth_papers)} author-paper records")
            
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
        title_label = ttk.Label(main_frame, text="BPR Calculator", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Parameters frame
        params_frame = ttk.LabelFrame(main_frame, text="Parameters", padding="10")
        params_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        # BPR percentile
        ttk.Label(params_frame, text="BPR Percentile:").grid(row=0, column=0, padx=(0, 10))
        self.bpr_percentile_var = tk.StringVar(value="95")
        bpr_percentile_values = [str(i) for i in range(80, 101, 5)]  # 80 to 100 in steps of 5
        self.bpr_percentile_combo = ttk.Combobox(params_frame, textvariable=self.bpr_percentile_var, 
                                                 values=bpr_percentile_values, state="readonly", width=10)
        self.bpr_percentile_combo.grid(row=0, column=1, padx=(0, 20))
        
        # LIPR percentile
        ttk.Label(params_frame, text="LIPR Percentile:").grid(row=0, column=2, padx=(0, 10))
        self.lipr_percentile_var = tk.StringVar(value="40")
        lipr_percentile_values = [str(i) for i in range(20, 61, 5)]  # 20 to 60 in steps of 5
        self.lipr_percentile_combo = ttk.Combobox(params_frame, textvariable=self.lipr_percentile_var, 
                                                  values=lipr_percentile_values, state="readonly", width=10)
        self.lipr_percentile_combo.grid(row=0, column=3, padx=(0, 20))
        
        # Metric selection
        ttk.Label(params_frame, text="Display Metric:").grid(row=0, column=4, padx=(0, 10))
        self.metric_var = tk.StringVar(value="Weighted BPR")
        metric_values = ["Weighted BPR", "Weighted LIPR"]
        self.metric_combo = ttk.Combobox(params_frame, textvariable=self.metric_var, 
                                        values=metric_values, state="readonly", width=15)
        self.metric_combo.grid(row=0, column=5)
        
        # Calculate button
        self.calc_button = ttk.Button(main_frame, text="Calculate BPR", command=self.calculate_bpr)
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
        self.tree = ttk.Treeview(results_frame, columns=("rank", "name", "papers", "col1", "col2", "metric"), 
                                show="headings", height=15)
        self.tree.heading("rank", text="Rank")
        self.tree.heading("name", text="Author Name")
        self.tree.heading("papers", text="Papers")
        self.tree.heading("col1", text="BP")
        self.tree.heading("col2", text="BPR")
        self.tree.heading("metric", text="Weighted BPR")  # Default heading
        
        # Set column widths with some stretchable columns
        self.tree.column("rank", width=60, minwidth=50, stretch=False)
        self.tree.column("name", width=300, minwidth=200, stretch=True)
        self.tree.column("papers", width=80, minwidth=60, stretch=False)
        self.tree.column("col1", width=80, minwidth=60, stretch=False)
        self.tree.column("col2", width=100, minwidth=80, stretch=False)
        self.tree.column("metric", width=120, minwidth=100, stretch=False)
        
        # Store initial column configuration
        self.initial_columns = ("rank", "name", "papers", "col1", "col2", "metric")
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def calculate_bpr(self):
        """Calculate BPR in a separate thread to avoid blocking the GUI"""
        self.calc_button.config(state="disabled")
        self.progress_var.set("Calculating...")
        
        # Start calculation in separate thread
        thread = threading.Thread(target=self._calculate_bpr_thread)
        thread.daemon = True
        thread.start()
    
    def _calculate_bpr_thread(self):
        """Calculate BPR in background thread"""
        try:
            bpr_percentile = int(self.bpr_percentile_var.get())
            lipr_percentile = int(self.lipr_percentile_var.get())
            metric_choice = self.metric_var.get()
            
            self.progress_var.set("Computing year thresholds...")
            
            # Compute year thresholds
            year_thresholds = compute_year_thresholds_vectorized(self.papers_df, bpr_percentile, lipr_percentile)
            
            self.progress_var.set("Classifying papers...")
            
            # Classify papers
            classified_papers = classify_papers_vectorized(self.auth_papers, year_thresholds)
            
            self.progress_var.set("Calculating BPR/LIPR ratios...")
            
            # Calculate BPR/LIPR ratios
            result = calc_bpr_lipr_vectorized(classified_papers)
            
            self.progress_var.set("Applying smoothing...")
            
            # Apply smoothing
            result = apply_smoothing_vectorized(result, smoothing_k=5)
            
            self.progress_var.set("Processing results...")
            
            # Round floating point values
            float_columns = ['BPR', 'LIPR', 'weighted_BPR', 'weighted_LIPR']
            for col in float_columns:
                result[col] = result[col].round(4)
            
            # Determine which metric to display
            if metric_choice == "Weighted BPR":
                result = result.sort_values('weighted_BPR', ascending=False)
                metric_col = 'weighted_BPR'
            else:  # Weighted LIPR
                result = result.sort_values('weighted_LIPR', ascending=False)
                metric_col = 'weighted_LIPR'
            
            # Store results for toggle functionality
            self.current_results_df = result.copy()
            self.current_metric_col = metric_col
            
            # Update GUI with results
            self.root.after(0, self._update_results, result, metric_col)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Calculation failed: {str(e)}"))
            self.root.after(0, lambda: self.progress_var.set("Error occurred"))
        finally:
            self.root.after(0, lambda: self.calc_button.config(state="normal"))
    
    def toggle_results_view(self):
        """Toggle between showing top and bottom results"""
        if self.current_results_df is None or self.current_metric_col is None:
            messagebox.showwarning("Warning", "No results available. Please calculate BPR first.")
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
        
        # Update the metric column heading based on the chosen metric
        metric_choice = self.metric_var.get()
        self.tree.heading("metric", text=metric_choice)
        
        # Configure column headers and data based on selected metric
        if "BPR" in metric_choice:
            # Show BP and BPR data
            self.tree.heading("col1", text="BP")
            self.tree.heading("col2", text="BPR")
        else:
            # Show LIP and LIPR data
            self.tree.heading("col1", text="LIP")
            self.tree.heading("col2", text="LIPR")
        
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
            papers = row['paper_count']
            metric_value = row[metric_col]
            
            # Set values based on selected metric
            if "BPR" in metric_choice:
                col1_value = row['BP']
                col2_value = f"{row['BPR']:.4f}"
            else:
                col1_value = row['LIP']
                col2_value = f"{row['LIPR']:.4f}"
            
            self.tree.insert("", "end", values=(rank, name, papers, col1_value, col2_value, f"{metric_value:.4f}"))
        
        self.progress_var.set(f"Completed! Showing {view_text} 30 of {len(results_df)} authors")

def main():
    root = tk.Tk()
    app = BPRInteractiveApp(root)
    root.mainloop()

if __name__ == "__main__":
    main() 