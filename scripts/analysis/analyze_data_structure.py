#!/usr/bin/env python3
"""
Script to analyze the column structure of CSV files in the data folder.
This helps understand the structure of large CSV files without loading them entirely.
"""

import os
import pandas as pd
import csv
from pathlib import Path
import re

def infer_datatype(value):
    """
    Infer the datatype of a value.
    
    Args:
        value (str): The value to analyze
        
    Returns:
        str: The inferred datatype
    """
    if value is None or value == '':
        return 'empty'
    
    # Try to convert to int
    try:
        int(value)
        return 'int'
    except ValueError:
        pass
    
    # Try to convert to float
    try:
        float(value)
        return 'float'
    except ValueError:
        pass
    
    # Check if it's a boolean
    if value.lower() in ['true', 'false', '1', '0']:
        return 'bool'
    
    # Check if it's a date (basic pattern)
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
        r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
    ]
    for pattern in date_patterns:
        if re.match(pattern, value):
            return 'date'
    
    # Check if it's a URL
    if value.startswith(('http://', 'https://', 'www.')):
        return 'url'
    
    # Check if it's an email
    if '@' in value and '.' in value:
        return 'email'
    
    # Default to string
    return 'string'

def check_int_range(values, column_name):
    """
    Check if integer values exceed regular int range and should be bigint.
    
    Args:
        values (list): List of values in the column
        column_name (str): Name of the column for logging
        
    Returns:
        str: 'int' or 'bigint'
    """
    # Regular int range: -2,147,483,648 to 2,147,483,647
    INT_MAX = 2147483647
    INT_MIN = -2147483648
    
    max_val = None
    min_val = None
    
    for value in values:
        if value and value != '':
            try:
                val = int(value)
                if max_val is None:
                    max_val = val
                elif val > max_val:
                    max_val = val
                if min_val is None:
                    min_val = val
                elif val < min_val:
                    min_val = val
            except (ValueError, TypeError):
                continue
    
    if max_val is not None:
        if max_val > INT_MAX or min_val < INT_MIN:
            print(f"  Column '{column_name}': max={max_val}, min={min_val} -> using bigint")
            return 'bigint'
        else:
            print(f"  Column '{column_name}': max={max_val}, min={min_val} -> using int")
            return 'int'
    
    return 'int'

def analyze_csv_structure(csv_file_path):
    """
    Analyze the structure of a CSV file and return column information.
    
    Args:
        csv_file_path (str): Path to the CSV file
        
    Returns:
        dict: Dictionary containing file info and column structure
    """
    file_info = {
        'file_name': os.path.basename(csv_file_path),
        'file_size_mb': round(os.path.getsize(csv_file_path) / (1024 * 1024), 2),
        'columns': [],
        'column_types': {},
        'total_rows': 0
    }
    
    try:
        # Read the header and first data row to get column names and types
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            file_info['columns'] = header
            
            # Try to read the first data row for type inference
            try:
                first_row = next(reader)
                # Infer types from the first row
                for i, value in enumerate(first_row):
                    if i < len(header):
                        col_name = header[i]
                        file_info['column_types'][col_name] = infer_datatype(value)
            except StopIteration:
                # File has only header, no data rows
                pass
            
            # Count total rows (excluding header)
            f.seek(0)  # Reset file pointer
            reader = csv.reader(f)
            next(reader)  # Skip header
            row_count = sum(1 for row in reader)
            file_info['total_rows'] = row_count
        
        # For integer columns, check if they need to be bigint
        print(f"Analyzing integer ranges for {csv_file_path.name}...")
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            # Collect all values for each column
            column_data = {col: [] for col in header}
            
            # Read all rows to collect data
            for row in reader:
                for i, value in enumerate(row):
                    if i < len(header):
                        column_data[header[i]].append(value)
            
            # Check integer columns for range
            for col_name, values in column_data.items():
                if col_name in file_info['column_types'] and file_info['column_types'][col_name] == 'int':
                    refined_type = check_int_range(values, col_name)
                    file_info['column_types'][col_name] = refined_type
            
    except Exception as e:
        file_info['error'] = str(e)
    
    return file_info

def main():
    """Main function to analyze all CSV files in the data folder."""
    
    # Define paths
    data_folder = Path("./revised_data")
    output_file = Path("./revised_data/data_structure_analysis.txt")
    
    # Ensure data folder exists
    if not data_folder.exists():
        print(f"Data folder not found: {data_folder}")
        return
    
    # Find all CSV files
    csv_files = list(data_folder.glob("*.csv"))
    
    if not csv_files:
        print("No CSV files found in the data folder.")
        return
    
    print(f"Found {len(csv_files)} CSV files to analyze...")
    
    # Analyze each CSV file
    results = []
    for csv_file in csv_files:
        print(f"Analyzing: {csv_file.name}")
        result = analyze_csv_structure(csv_file)
        results.append(result)
    
    # Write results to text file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("CSV FILES STRUCTURE ANALYSIS\n")
        f.write("=" * 50 + "\n\n")
        
        for i, result in enumerate(results, 1):
            f.write(f"{i}. FILE: {result['file_name']}\n")
            f.write(f"   Size: {result['file_size_mb']} MB\n")
            f.write(f"   Total Rows: {result['total_rows']:,}\n")
            f.write(f"   Columns ({len(result['columns'])}):\n")
            
            for j, col in enumerate(result['columns'], 1):
                # Add type annotation if available
                if col in result.get('column_types', {}):
                    type_suffix = f" ({result['column_types'][col]})"
                    f.write(f"     {j:2d}. {col}{type_suffix}\n")
                else:
                    f.write(f"     {j:2d}. {col}\n")
            
            if 'error' in result:
                f.write(f"   ERROR: {result['error']}\n")
            
            f.write("\n" + "-" * 50 + "\n\n")
    
    print(f"Analysis complete! Results written to: {output_file}")
    print(f"Analyzed {len(results)} CSV files.")

if __name__ == "__main__":
    main() 