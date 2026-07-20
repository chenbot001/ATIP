#!/usr/bin/env python3
"""
ACL-DBLP Author Mapping Analysis Script

This script analyzes the author mapping CSV file to compare the lengths of 
'authors' and 'dblp_authors' lists and reports any mismatches.

Author: AI Assistant
Date: August 11, 2025
"""

import pandas as pd
import ast
import numpy as np
from collections import Counter

def parse_author_list(author_str):
    """
    Parse author string representation into a list.
    
    Args:
        author_str: String representation of author list or actual list
        
    Returns:
        list: Parsed list of authors, empty list if parsing fails or None
    """
    if pd.isna(author_str):
        return []
    
    if isinstance(author_str, list):
        return author_str
    
    if isinstance(author_str, str):
        try:
            # Try to parse as Python literal (list)
            return ast.literal_eval(author_str)
        except:
            # If parsing fails, treat as single author
            return [author_str.strip()] if author_str.strip() else []
    
    return []

def analyze_author_mapping():
    """
    Analyze the ACL-DBLP author mapping CSV file for length mismatches.
    """
    
    # Load the mapping file
    mapping_file = 'revised_data/acl_dblp_author_mapping.csv'
    output_file = 'revised_data/acl_dblp_author_analysis.txt'
    
    print("Loading ACL-DBLP author mapping file...")
    
    # Create a list to store all output lines
    output_lines = []
    
    def add_output(text):
        """Add text to both console output and file output."""
        print(text)
        output_lines.append(text)
    
    try:
        df = pd.read_csv(mapping_file)
        add_output(f"Loaded {len(df):,} papers")
        
        # Parse author lists
        add_output("Parsing author lists...")
        df['acl_authors_parsed'] = df['authors'].apply(parse_author_list)
        df['dblp_authors_parsed'] = df['dblp_authors'].apply(parse_author_list)
        
        # Calculate list lengths
        df['acl_author_count'] = df['acl_authors_parsed'].apply(len)
        df['dblp_author_count'] = df['dblp_authors_parsed'].apply(len)
        
        # Find papers with DBLP matches (non-null dblp_authors)
        papers_with_dblp = df[df['dblp_authors'].notna()].copy()
        papers_without_dblp = df[df['dblp_authors'].isna()].copy()
        
        add_output(f"\nPapers with DBLP matches: {len(papers_with_dblp):,}")
        add_output(f"Papers without DBLP matches: {len(papers_without_dblp):,}")
        
        # Analyze length differences for papers with DBLP matches
        papers_with_dblp['length_diff'] = papers_with_dblp['acl_author_count'] - papers_with_dblp['dblp_author_count']
        
        # Find mismatches (where lengths differ)
        mismatched_papers = papers_with_dblp[papers_with_dblp['length_diff'] != 0]
        perfect_matches = papers_with_dblp[papers_with_dblp['length_diff'] == 0]
        
        # Print summary statistics
        add_output("\n" + "="*80)
        add_output("AUTHOR LIST LENGTH ANALYSIS SUMMARY")
        add_output("="*80)
        add_output(f"Analysis Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        add_output(f"Total papers analyzed: {len(df):,}")
        add_output(f"Papers with DBLP author data: {len(papers_with_dblp):,}")
        add_output(f"Papers without DBLP author data: {len(papers_without_dblp):,}")
        add_output("")
        add_output("LENGTH COMPARISON (for papers with DBLP matches):")
        add_output(f"Perfect length matches: {len(perfect_matches):,} ({len(perfect_matches)/len(papers_with_dblp)*100:.1f}%)")
        add_output(f"Length mismatches: {len(mismatched_papers):,} ({len(mismatched_papers)/len(papers_with_dblp)*100:.1f}%)")
        
        if len(mismatched_papers) > 0:
            # Analyze types of mismatches
            length_diff_counts = Counter(mismatched_papers['length_diff'])
            
            add_output("\nMISMATCH BREAKDOWN:")
            add_output("Difference (ACL - DBLP) | Count | Description")
            add_output("-" * 50)
            for diff in sorted(length_diff_counts.keys()):
                count = length_diff_counts[diff]
                if diff > 0:
                    desc = f"ACL has {diff} more author(s)"
                else:
                    desc = f"DBLP has {abs(diff)} more author(s)"
                add_output(f"{diff:>8} | {count:>5} | {desc}")
            
            # Show detailed examples of mismatches - top 3 highest differences
            add_output(f"\nDETAILED MISMATCH EXAMPLES (top 3 highest differences):")
            add_output("="*80)
            
            # Sort by absolute difference and get top 3
            top_mismatches = mismatched_papers.reindex(mismatched_papers['length_diff'].abs().sort_values(ascending=False).index).head(3)
            
            for idx, (_, row) in enumerate(top_mismatches.iterrows()):
                add_output(f"\n{idx+1}. Paper ID: {row['paper_id']}")
                add_output(f"   Title: {row['title'][:60]}...")
                add_output(f"   ACL Authors ({row['acl_author_count']}): {row['acl_authors_parsed']}")
                add_output(f"   DBLP Authors ({row['dblp_author_count']}): {row['dblp_authors_parsed']}")
                add_output(f"   Difference: {row['length_diff']} (ACL - DBLP)")
                add_output(f"   Absolute Difference: {abs(row['length_diff'])}")
        
        # Statistics about author counts
        add_output(f"\nAUTHOR COUNT STATISTICS:")
        add_output(f"ACL author count - Mean: {papers_with_dblp['acl_author_count'].mean():.1f}, "
              f"Median: {papers_with_dblp['acl_author_count'].median():.1f}, "
              f"Max: {papers_with_dblp['acl_author_count'].max()}")
        add_output(f"DBLP author count - Mean: {papers_with_dblp['dblp_author_count'].mean():.1f}, "
              f"Median: {papers_with_dblp['dblp_author_count'].median():.1f}, "
              f"Max: {papers_with_dblp['dblp_author_count'].max()}")
        
        # Add section for all mismatched paper IDs
        if len(mismatched_papers) > 0:
            add_output(f"\nALL PAPERS WITH AUTHOR COUNT MISMATCHES:")
            add_output("="*80)
            add_output(f"Total mismatched papers: {len(mismatched_papers)}")
            add_output("\nPaper IDs (sorted by absolute difference, highest first):")
            
            # Sort by absolute difference
            sorted_mismatches = mismatched_papers.sort_values('length_diff', key=abs, ascending=False)
            
            for idx, (_, row) in enumerate(sorted_mismatches.iterrows(), 1):
                diff_desc = f"ACL:{row['acl_author_count']} vs DBLP:{row['dblp_author_count']} (diff:{row['length_diff']:+d})"
                add_output(f"{idx:3d}. {row['paper_id']} - {diff_desc}")
        
        add_output("="*80)
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        
        print(f"\nAnalysis summary saved to: {output_file}")
        
        # Return summary for further analysis if needed
        return {
            'total_papers': len(df),
            'papers_with_dblp': len(papers_with_dblp),
            'perfect_matches': len(perfect_matches),
            'mismatched_papers': len(mismatched_papers),
            'mismatch_details': length_diff_counts,
            'output_file': output_file
        }
        
    except FileNotFoundError:
        print(f"Error: File '{mapping_file}' not found.")
        return None
    except Exception as e:
        print(f"Error analyzing mapping file: {str(e)}")
        return None

def main():
    """Main function to execute the analysis."""
    print("Starting ACL-DBLP author mapping analysis...")
    results = analyze_author_mapping()
    
    if results:
        print("\nAnalysis completed successfully.")
    else:
        print("\nAnalysis failed.")

if __name__ == "__main__":
    main()
