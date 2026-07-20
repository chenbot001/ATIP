"""
ACL Papers CSV Analysis Script

This script analyzes the ACL papers CSV file to generate comprehensive statistics
including paper counts, empty columns, year distributions, venue distributions,
author counts, and column fill rates.

Author: Analysis Script
Date: 2025-08-06
"""

import pandas as pd
import ast
import re
from collections import Counter, defaultdict
from datetime import datetime

def is_empty_value(value):
    """
    Check if a value is considered empty (None, empty string, empty list, etc.)
    """
    if pd.isna(value):
        return True
    if value == '':
        return True
    if value == '[]':
        return True
    if isinstance(value, str):
        # Check if it's a string representation of an empty list
        try:
            # Handle potential parsing issues more safely
            value_clean = value.strip()
            if value_clean == '[]':
                return True
            parsed = ast.literal_eval(value_clean)
            if isinstance(parsed, list) and len(parsed) == 0:
                return True
        except (ValueError, SyntaxError, TypeError):
            # If parsing fails, check for common empty patterns
            if value.strip() in ['[]', '{}', '()', 'None', 'nan', 'NaN']:
                return True
    return False

def extract_venue_info(row):
    """
    Extract venue information considering the special case for 'Findings'
    """
    venue = row['venue']
    tuple_id = row['tuple_id']
    
    if venue == 'Findings':
        # Parse the tuple_id to get the second element
        try:
            # Remove quotes and parse the tuple string
            tuple_str = tuple_id.strip("\"'")
            # Use regex to extract tuple elements
            match = re.match(r"\('([^']+)', '([^']+)', '[^']+'\)", tuple_str)
            if match:
                second_element = match.group(2)
                return f"{venue}-{second_element}"
        except:
            pass
    
    return venue

def analyze_authors(df):
    """
    Analyze unique authors from the authors column
    """
    unique_authors = set()
    
    for authors_str in df['authors']:
        if not is_empty_value(authors_str):
            try:
                # Handle potential parsing issues more safely
                if isinstance(authors_str, str):
                    authors_str_clean = authors_str.strip()
                    # Parse the string representation of the list
                    authors_list = ast.literal_eval(authors_str_clean)
                    if isinstance(authors_list, list):
                        for author in authors_list:
                            if isinstance(author, tuple) and len(author) >= 1:
                                # Extract name from tuple (name, id, affiliation)
                                author_name = str(author[0]).strip()
                                if author_name:
                                    unique_authors.add(author_name)
                            elif isinstance(author, str):
                                # Handle case where author is just a string
                                author_name = author.strip()
                                if author_name:
                                    unique_authors.add(author_name)
                else:
                    # Handle non-string cases
                    author_name = str(authors_str).strip()
                    if author_name and author_name not in ['nan', 'None']:
                        unique_authors.add(author_name)
            except (ValueError, SyntaxError, TypeError) as e:
                # If parsing fails, try to extract author names manually
                if isinstance(authors_str, str) and authors_str.strip():
                    # Try to extract names from malformed strings
                    author_str_clean = authors_str.strip()
                    if author_str_clean and author_str_clean not in ['[]', 'nan', 'None']:
                        # Simple fallback - treat as single author
                        unique_authors.add(author_str_clean)
    
    return len(unique_authors)

def analyze_csv(csv_file_path, output_file_path):
    """
    Main analysis function
    """
    # Read the CSV file
    print(f"Reading CSV file: {csv_file_path}")
    # Use low_memory=False to avoid DtypeWarning and handle mixed types
    df = pd.read_csv(csv_file_path, low_memory=False)
    
    # Prepare results
    results = []
    results.append("=" * 60)
    results.append("ACL PAPERS CSV ANALYSIS REPORT")
    results.append("=" * 60)
    results.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    results.append(f"Source File: {csv_file_path}")
    results.append("")
    
    # 1. Total number of papers
    total_papers = len(df)
    results.append(f"1. TOTAL NUMBER OF PAPERS: {total_papers:,}")
    results.append("")
    
    # 2. Completely empty columns
    results.append("2. COMPLETELY EMPTY COLUMNS:")
    empty_columns = []
    for col in df.columns:
        if df[col].apply(is_empty_value).all():
            empty_columns.append(col)
    
    if empty_columns:
        for col in empty_columns:
            results.append(f"   - {col}")
    else:
        results.append("   No completely empty columns found.")
    results.append("")
    
    # 3. Distribution of publication years
    results.append("3. PUBLICATION YEAR DISTRIBUTION:")
    year_counts = df['year'].value_counts().sort_index()
    for year, count in year_counts.items():
        percentage = (count / total_papers) * 100
        results.append(f"   {year}: {count:,} papers ({percentage:.1f}%)")
    results.append("")
    
    # 4. Distribution of venues
    results.append("4. VENUE DISTRIBUTION:")
    venue_info = df.apply(extract_venue_info, axis=1)
    venue_counts = venue_info.value_counts()
    
    for venue, count in venue_counts.items():
        percentage = (count / total_papers) * 100
        results.append(f"   {venue}: {count:,} papers ({percentage:.1f}%)")
    results.append("")
    
    # 5. Number of unique authors
    results.append("5. UNIQUE AUTHORS ANALYSIS:")
    unique_author_count = analyze_authors(df)
    results.append(f"   Total unique authors: {unique_author_count:,}")
    results.append("")
    
    # 6. Preface and Table of Contents Analysis
    results.append("6. PREFACE AND TABLE OF CONTENTS:")
    preface_count = 0
    for tuple_id in df['tuple_id']:
        try:
            # Parse the tuple_id to get the third element
            tuple_str = str(tuple_id).strip("\"'")
            # Use regex to extract tuple elements
            match = re.match(r"\('([^']+)', '([^']+)', '([^']+)'\)", tuple_str)
            if match:
                third_element = match.group(3)
                if third_element == '0':
                    preface_count += 1
        except:
            pass
    
    percentage = (preface_count / total_papers) * 100 if total_papers > 0 else 0
    results.append(f"   Papers with tuple_id ending in '0' (preface/ToC): {preface_count:,} ({percentage:.1f}%)")
    results.append("")
    
    # 7. Column fill rates (for partially filled columns)
    results.append("7. COLUMN FILL RATES (Partially Filled Columns):")
    partially_filled = []
    
    for col in df.columns:
        non_empty_count = (~df[col].apply(is_empty_value)).sum()
        fill_rate = (non_empty_count / total_papers) * 100
        
        # Only include columns that are neither completely empty nor completely filled
        if 0 < fill_rate < 100:
            partially_filled.append((col, fill_rate, non_empty_count))
    
    if partially_filled:
        # Sort by fill rate descending
        partially_filled.sort(key=lambda x: x[1], reverse=True)
        for col, fill_rate, count in partially_filled:
            results.append(f"   {col}: {fill_rate:.1f}% filled ({count:,}/{total_papers:,} rows)")
    else:
        results.append("   No partially filled columns found.")
    results.append("")
    
    # Additional statistics
    results.append("8. ADDITIONAL STATISTICS:")
    results.append(f"   Total columns in dataset: {len(df.columns)}")
    results.append(f"   Completely filled columns: {len([c for c in df.columns if (~df[c].apply(is_empty_value)).sum() == total_papers])}")
    results.append(f"   Completely empty columns: {len(empty_columns)}")
    results.append(f"   Partially filled columns: {len(partially_filled)}")
    results.append("")
    
    # Column list
    results.append("9. ALL COLUMNS:")
    for i, col in enumerate(df.columns, 1):
        fill_count = (~df[col].apply(is_empty_value)).sum()
        fill_rate = (fill_count / total_papers) * 100
        results.append(f"   {i:2d}. {col:<20} ({fill_rate:5.1f}% filled)")
    
    results.append("")
    results.append("=" * 60)
    results.append("END OF REPORT")
    results.append("=" * 60)
    
    # Write results to file
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    
    print(f"Analysis complete! Results saved to: {output_file_path}")
    print(f"Total papers analyzed: {total_papers:,}")
    print(f"Unique authors found: {unique_author_count:,}")

if __name__ == "__main__":
    # File paths
    csv_file = "acl_papers_master.csv"
    output_file = "acl_papers_analysis.txt"

    try:
        analyze_csv(csv_file, output_file)
    except FileNotFoundError:
        print(f"Error: Could not find the CSV file '{csv_file}'")
        print("Please make sure the file exists in the current directory.")
    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        import traceback
        traceback.print_exc()
