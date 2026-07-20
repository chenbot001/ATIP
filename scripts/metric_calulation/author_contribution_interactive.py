import pandas as pd
import numpy as np
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import threading
from pathlib import Path

def load_data():
    """Load the required CSV files from data/database"""
    print("Loading data files...")
    
    # Load authorships data
    authorships_path = Path("data/database/authorships.csv")
    if not authorships_path.exists():
        raise FileNotFoundError(f"Authorships file not found: {authorships_path}")
    
    authorships = pd.read_csv(authorships_path)
    print(f"Loaded authorships data: {len(authorships)} records")
    
    # Load papers data
    papers_path = Path("data/database/megatable_papers.csv")
    if not papers_path.exists():
        raise FileNotFoundError(f"Papers file not found: {papers_path}")
    
    papers = pd.read_csv(papers_path)
    print(f"Loaded papers data: {len(papers)} records")
    
    return authorships, papers

def calculate_author_contribution_metrics_vectorized(authorships, papers):
    """
    Calculate author contribution metrics using vectorized operations
    
    Args:
        authorships: DataFrame with author_id, paper_id, is_first_author, is_last_author
        papers: DataFrame with paper_id, citation_count
    
    Returns:
        DataFrame with author_id, author_name, FAR, FAI, LAR, LAI
    """
    print("Calculating author contribution metrics (vectorized)...")
    
    # Merge authorships with papers to get citation counts
    merged = authorships.merge(papers[['paper_id', 'citation_count']], 
                              on='paper_id', how='left')
    
    # Fill NaN citation counts with 0
    merged['citation_count'] = merged['citation_count'].fillna(0)
    
    # Create boolean columns for easier aggregation
    merged['is_first_author_bool'] = merged['is_first_author'].astype(bool)
    merged['is_last_author_bool'] = merged['is_last_author'].astype(bool)
    
    # Calculate weighted citations for first and last author papers
    merged['first_author_citations'] = np.where(merged['is_first_author_bool'], 
                                               merged['citation_count'], 0)
    merged['last_author_citations'] = np.where(merged['is_last_author_bool'], 
                                              merged['citation_count'], 0)
    
    print("Aggregating metrics by author (vectorized)...")
    
    # Group by author and calculate all metrics at once using vectorized operations
    author_metrics = merged.groupby(['author_id', 'author_name']).agg({
        'paper_id': 'count',                          # total_papers
        'citation_count': 'sum',                      # total_citations
        'is_first_author_bool': 'sum',               # first_authorships
        'first_author_citations': 'sum',             # FAI (First Author Impact)
        'is_last_author_bool': 'sum',                # last_authorships
        'last_author_citations': 'sum'               # LAI (Last Author Impact)
    }).reset_index()
    
    # Rename columns for clarity
    author_metrics.columns = [
        'author_id', 'author_name', 'total_papers', 'total_citations',
        'first_authorships', 'FAI', 'last_authorships', 'LAI'
    ]
    
    print("Calculating ratios (vectorized)...")
    
    # Calculate ratios using vectorized operations
    author_metrics['FAR'] = np.where(author_metrics['total_papers'] > 0,
                                    author_metrics['first_authorships'] / author_metrics['total_papers'],
                                    0.0)
    
    author_metrics['LAR'] = np.where(author_metrics['total_papers'] > 0,
                                    author_metrics['last_authorships'] / author_metrics['total_papers'],
                                    0.0)
    
    # Round all floating point values to 4 decimal places
    float_columns = ['FAR', 'LAR', 'FAI', 'LAI']
    for col in float_columns:
        author_metrics[col] = author_metrics[col].round(4)
    
    # Reorder columns to match original output format
    final_columns = [
        'author_id', 'author_name', 'total_papers', 'total_citations',
        'first_authorships', 'FAR', 'FAI', 'last_authorships', 'LAR', 'LAI'
    ]
    
    return author_metrics[final_columns]

class AuthorContributionInteractiveApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Author Contribution Calculator - Interactive")
        self.root.geometry("1000x700")
        
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
            self.authorships_df, self.papers_df = load_data()
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
        title_label = ttk.Label(main_frame, text="Author Contribution Calculator", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Parameters frame
        params_frame = ttk.LabelFrame(main_frame, text="Parameters", padding="10")
        params_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        # Metric selection
        ttk.Label(params_frame, text="Display Metric:").grid(row=0, column=0, padx=(0, 10))
        self.metric_var = tk.StringVar(value="FAR")
        metric_values = ["FAR", "FAI", "LAR", "LAI"]
        self.metric_combo = ttk.Combobox(params_frame, textvariable=self.metric_var, 
                                        values=metric_values, state="readonly", width=15)
        self.metric_combo.grid(row=0, column=1, padx=(0, 20))
        
        # Minimum papers parameter
        ttk.Label(params_frame, text="Min Papers:").grid(row=0, column=2, padx=(0, 10))
        self.min_papers_var = tk.StringVar(value="1")
        min_papers_values = [str(i) for i in range(1, 11)]  # 1 to 10
        self.min_papers_combo = ttk.Combobox(params_frame, textvariable=self.min_papers_var, 
                                            values=min_papers_values, state="readonly", width=10)
        self.min_papers_combo.grid(row=0, column=3, padx=(0, 20))
        
        # Calculate button
        self.calc_button = ttk.Button(main_frame, text="Calculate Metrics", command=self.calculate_metrics)
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
        self.tree = ttk.Treeview(results_frame, columns=("rank", "name", "papers", "citations", "far", "fai", "lar", "lai", "metric"), 
                                show="headings", height=15)
        self.tree.heading("rank", text="Rank")
        self.tree.heading("name", text="Author Name")
        self.tree.heading("papers", text="Papers")
        self.tree.heading("citations", text="Citations")
        self.tree.heading("far", text="FAR")
        self.tree.heading("fai", text="FAI")
        self.tree.heading("lar", text="LAR")
        self.tree.heading("lai", text="LAI")
        self.tree.heading("metric", text="Target Metric")  # Default heading
        
        # Set column widths with some stretchable columns
        self.tree.column("rank", width=60, minwidth=50, stretch=False)
        self.tree.column("name", width=300, minwidth=200, stretch=True)
        self.tree.column("papers", width=80, minwidth=60, stretch=False)
        self.tree.column("citations", width=80, minwidth=60, stretch=False)
        self.tree.column("far", width=80, minwidth=60, stretch=False)
        self.tree.column("fai", width=80, minwidth=60, stretch=False)
        self.tree.column("lar", width=80, minwidth=60, stretch=False)
        self.tree.column("lai", width=80, minwidth=60, stretch=False)
        self.tree.column("metric", width=100, minwidth=80, stretch=False)
        
        # Store initial column configuration
        self.initial_columns = ("rank", "name", "papers", "citations", "far", "fai", "lar", "lai", "metric")
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def calculate_metrics(self):
        """Calculate metrics in a separate thread to avoid blocking the GUI"""
        self.calc_button.config(state="disabled")
        self.progress_var.set("Calculating...")
        
        # Start calculation in separate thread
        thread = threading.Thread(target=self._calculate_metrics_thread)
        thread.daemon = True
        thread.start()
    
    def _calculate_metrics_thread(self):
        """Calculate metrics in background thread"""
        try:
            metric_choice = self.metric_var.get()
            min_papers = int(self.min_papers_var.get())
            
            self.progress_var.set("Calculating author contribution metrics...")
            
            # Calculate metrics
            result = calculate_author_contribution_metrics_vectorized(self.authorships_df, self.papers_df)
            
            # Filter by minimum paper count
            result = result[result['total_papers'] >= min_papers]
            
            self.progress_var.set("Processing results...")
            
            # Determine which metric to display and sort
            if metric_choice == "FAR":
                result = result.sort_values('FAR', ascending=False)
                metric_col = 'FAR'
            elif metric_choice == "FAI":
                result = result.sort_values('FAI', ascending=False)
                metric_col = 'FAI'
            elif metric_choice == "LAR":
                result = result.sort_values('LAR', ascending=False)
                metric_col = 'LAR'
            else:  # LAI
                result = result.sort_values('LAI', ascending=False)
                metric_col = 'LAI'
            
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
            messagebox.showwarning("Warning", "No results available. Please calculate metrics first.")
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
        
        # Update the metric column heading to always show "Target Metric"
        self.tree.heading("metric", text="Target Metric")
        
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
            papers = row['total_papers']
            citations = row['total_citations']
            far = row['FAR']
            fai = row['FAI']
            lar = row['LAR']
            lai = row['LAI']
            metric_value = row[metric_col]
            
            self.tree.insert("", "end", values=(rank, name, papers, citations, 
                                               f"{far:.4f}", f"{fai:.4f}", 
                                               f"{lar:.4f}", f"{lai:.4f}", 
                                               f"{metric_value:.4f}"))
        
        self.progress_var.set(f"Completed! Showing {view_text} 30 of {len(results_df)} authors")

def main():
    root = tk.Tk()
    app = AuthorContributionInteractiveApp(root)
    root.mainloop()

if __name__ == "__main__":
    main() 