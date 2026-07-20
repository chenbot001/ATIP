import pandas as pd
import ast
import os
import re
from collections import defaultdict

def safe_literal_eval(value):
    """Safely convert string representation to list, handling various formats"""
    if pd.isna(value):
        return []
    
    # If it's already a list, return it
    if isinstance(value, list):
        return value
    
    # If it's a string, try to parse it
    if isinstance(value, str):
        try:
            # Try literal_eval first
            result = ast.literal_eval(value)
            if isinstance(result, list):
                return result
            else:
                return [str(result)]
        except (ValueError, SyntaxError):
            # If literal_eval fails, try splitting by comma and cleaning
            if value.startswith('[') and value.endswith(']'):
                # Remove brackets and split
                inner = value[1:-1]
                if inner.strip():
                    items = [item.strip().strip('\'"') for item in inner.split(',')]
                    return [item for item in items if item]
                else:
                    return []
            else:
                return [value]
    
    return [str(value)]

def comprehensive_author_analysis(csv_file_path):
    """
    Comprehensive analysis of authors and author_ids to find unique ACL and DBLP authors.
    
    Args:
        csv_file_path (str): Path to the CSV file
    
    Returns:
        dict: Comprehensive statistics
    """
    
    print(f"Reading CSV file: {csv_file_path}")
    df = pd.read_csv(csv_file_path)
    
    print(f"Total rows in dataset: {len(df)}")
    
    # Check required columns
    required_cols = ['authors', 'author_ids', 'dblp_authors']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: Missing columns: {missing_cols}")
        print(f"Available columns: {list(df.columns)}")
        return None
    
    # Initialize collections for unique authors
    unique_acl_authors = set()  # (name, id) pairs where id can be None
    unique_dblp_authors = set()  # unique DBLP author names
    name_none_pairs = defaultdict(int)  # Count of (name, None) pairs
    dblp_authors_with_numbers = set()  # DBLP authors with 4-digit numbers
    dblp_base_names_with_numbers = defaultdict(set)  # Map base names to their 4-digit numbers
    
    # Process each row
    parsing_errors = 0
    for row_num, (idx, row) in enumerate(df.iterrows(), 1):
        try:
            # Parse authors, author_ids, and dblp_authors columns
            authors_list = safe_literal_eval(row['authors'])
            author_ids_list = safe_literal_eval(row['author_ids'])
            dblp_authors_list = safe_literal_eval(row['dblp_authors'])
            
            # Handle DBLP authors (simpler case)
            for dblp_author in dblp_authors_list:
                if dblp_author and str(dblp_author).strip():
                    clean_dblp_name = str(dblp_author).strip()
                    unique_dblp_authors.add(clean_dblp_name)
                    
                    # Check if this DBLP author name has a 4-digit number
                    match = re.search(r'\b(\d{4})\b', clean_dblp_name)
                    if match:
                        dblp_authors_with_numbers.add(clean_dblp_name)
                        
                        # Extract the base name (without the 4-digit number)
                        four_digit_number = match.group(1)
                        base_name = re.sub(r'\s*\b\d{4}\b\s*', ' ', clean_dblp_name).strip()
                        base_name = re.sub(r'\s+', ' ', base_name)  # Clean up extra spaces
                        
                        # Store the mapping of base name to 4-digit numbers
                        dblp_base_names_with_numbers[base_name].add(four_digit_number)
            
            # Handle ACL authors (more complex due to name-id pairing)
            # Ensure both lists have the same length by padding with None
            max_len = max(len(authors_list), len(author_ids_list))
            
            # Create properly sized lists
            padded_authors = []
            padded_ids = []
            
            for i in range(max_len):
                author = authors_list[i] if i < len(authors_list) else None
                author_id = author_ids_list[i] if i < len(author_ids_list) else None
                padded_authors.append(author)
                padded_ids.append(author_id)
            
            # Create (name, id) pairs
            for author_name, author_id in zip(padded_authors, padded_ids):
                if author_name and str(author_name).strip():
                    clean_name = str(author_name).strip()
                    clean_id = author_id if author_id is not None and str(author_id).strip() != 'None' else None
                    
                    # Add to unique ACL authors
                    author_pair = (clean_name, clean_id)
                    unique_acl_authors.add(author_pair)
                    
                    # Count (name, None) pairs
                    if clean_id is None:
                        name_none_pairs[clean_name] += 1
        
        except Exception as e:
            parsing_errors += 1
            if parsing_errors <= 5:  # Show first 5 errors
                print(f"Error parsing row {row_num}: {e}")
                print(f"  authors: {row['authors']}")
                print(f"  author_ids: {row['author_ids']}")
                print(f"  dblp_authors: {row['dblp_authors']}")
    
    if parsing_errors > 5:
        print(f"... and {parsing_errors - 5} more parsing errors")
    
    # Analyze the results
    total_unique_acl_authors = len(unique_acl_authors)
    acl_authors_with_ids = len([pair for pair in unique_acl_authors if pair[1] is not None])
    acl_authors_without_ids = len([pair for pair in unique_acl_authors if pair[1] is None])
    total_unique_dblp_authors = len(unique_dblp_authors)
    dblp_authors_with_numbers_count = len(dblp_authors_with_numbers)
    dblp_authors_without_numbers_count = total_unique_dblp_authors - dblp_authors_with_numbers_count
    
    # DBLP disambiguation analysis
    dblp_base_names_count = len(dblp_base_names_with_numbers)
    dblp_disambiguated_names = {base_name: numbers for base_name, numbers in dblp_base_names_with_numbers.items() if len(numbers) > 1}
    dblp_disambiguated_names_count = len(dblp_disambiguated_names)
    
    # Examples of disambiguated names
    disambiguated_examples = []
    for base_name, numbers in list(dblp_disambiguated_names.items())[:5]:
        full_names = [f"{base_name} {num}" for num in sorted(numbers)]
        disambiguated_examples.append((base_name, sorted(numbers), full_names))
    
    # Find unique names (regardless of ID)
    unique_acl_names = set(pair[0] for pair in unique_acl_authors)
    total_unique_acl_names = len(unique_acl_names)
    
    # Find names that appear with multiple different IDs (excluding None)
    name_to_ids = defaultdict(set)
    for name, author_id in unique_acl_authors:
        if author_id is not None:
            name_to_ids[name].add(author_id)
    
    names_with_multiple_ids = {name: ids for name, ids in name_to_ids.items() if len(ids) > 1}
    
    # Calculate total ACL authors using the specific logic:
    # (name, None) pairs count as ONE author per name
    # Each (name, distinct ID) pair counts as a DIFFERENT author
    
    # First, get all names that appear with None
    names_with_none = set()
    for name, author_id in unique_acl_authors:
        if author_id is None:
            names_with_none.add(name)
    
    # Count authors with IDs (each (name, id) pair is a separate author)
    authors_with_ids_count = acl_authors_with_ids
    
    # Count authors with None (each name counts as ONE author regardless of how many (name, None) pairs)
    authors_with_none_count = len(names_with_none)
    
    # Total ACL authors according to the specified logic
    total_acl_authors_by_logic = authors_with_ids_count + authors_with_none_count
    
    stats = {
        'total_rows': len(df),
        'parsing_errors': parsing_errors,
        'unique_acl_authors': total_unique_acl_authors,
        'unique_acl_names': total_unique_acl_names,
        'acl_authors_with_ids': acl_authors_with_ids,
        'acl_authors_without_ids': acl_authors_without_ids,
        'unique_dblp_authors': total_unique_dblp_authors,
        'dblp_authors_with_numbers': dblp_authors_with_numbers_count,
        'dblp_authors_without_numbers': dblp_authors_without_numbers_count,
        'dblp_base_names_count': dblp_base_names_count,
        'dblp_disambiguated_names_count': dblp_disambiguated_names_count,
        'dblp_disambiguated_examples': disambiguated_examples,
        'names_with_multiple_ids': len(names_with_multiple_ids),
        'names_with_multiple_ids_detail': names_with_multiple_ids,
        'most_common_name_none_pairs': dict(sorted(name_none_pairs.items(), key=lambda x: x[1], reverse=True)[:10]),
        'total_acl_authors_by_logic': total_acl_authors_by_logic,
        'authors_with_ids_count': authors_with_ids_count,
        'authors_with_none_count': authors_with_none_count,
        'dblp_authors_with_numbers_examples': list(dblp_authors_with_numbers)[:10]
    }
    
    return stats

def count_non_none_author_ids(csv_file_path):
    """
    Analyze the author_ids column to count non-None IDs.
    
    Args:
        csv_file_path (str): Path to the CSV file containing author_ids column
    
    Returns:
        dict: Statistics about the author_ids column
    """
    
    # Read the CSV file
    print(f"Reading CSV file: {csv_file_path}")
    df = pd.read_csv(csv_file_path)
    
    print(f"Total rows in dataset: {len(df)}")
    
    # Check if author_ids column exists
    if 'author_ids' not in df.columns:
        print("Error: 'author_ids' column not found in the dataset")
        print(f"Available columns: {list(df.columns)}")
        return None
    
    # Initialize counters
    total_ids = 0
    non_none_ids = 0
    rows_with_non_none = 0
    total_rows = len(df)
    
    # Process each row
    for row_num, (idx, row) in enumerate(df.iterrows(), 1):
        author_ids_str = row['author_ids']
        
        try:
            # Convert string representation of list to actual list
            author_ids_list = ast.literal_eval(author_ids_str)
            
            # Count total IDs in this row
            total_ids += len(author_ids_list)
            
            # Count non-None IDs in this row
            non_none_in_row = sum(1 for id_val in author_ids_list if id_val is not None)
            non_none_ids += non_none_in_row
            
            # Check if this row has any non-None IDs
            if non_none_in_row > 0:
                rows_with_non_none += 1
                print(f"Row {row_num}: Found {non_none_in_row} non-None IDs: {[id_val for id_val in author_ids_list if id_val is not None]}")
        
        except (ValueError, SyntaxError) as e:
            print(f"Error parsing author_ids in row {row_num}: {author_ids_str}")
            print(f"Error details: {e}")
            continue
    
    # Calculate statistics
    stats = {
        'total_rows': total_rows,
        'total_author_id_slots': total_ids,
        'non_none_ids': non_none_ids,
        'none_ids': total_ids - non_none_ids,
        'rows_with_non_none_ids': rows_with_non_none,
        'percentage_non_none': (non_none_ids / total_ids * 100) if total_ids > 0 else 0,
        'percentage_rows_with_non_none': (rows_with_non_none / total_rows * 100) if total_rows > 0 else 0
    }
    
    return stats

def print_statistics(stats):
    """Print formatted statistics"""
    if stats is None:
        return
    
    print("\n" + "="*50)
    print("AUTHOR IDS ANALYSIS RESULTS")
    print("="*50)
    print(f"Total rows in dataset: {stats['total_rows']:,}")
    print(f"Total author ID slots: {stats['total_author_id_slots']:,}")
    print(f"Non-None IDs: {stats['non_none_ids']:,}")
    print(f"None IDs: {stats['none_ids']:,}")
    print(f"Rows with at least one non-None ID: {stats['rows_with_non_none_ids']:,}")
    print(f"Percentage of non-None IDs: {stats['percentage_non_none']:.2f}%")
    print(f"Percentage of rows with non-None IDs: {stats['percentage_rows_with_non_none']:.2f}%")
    print("="*50)

def print_comprehensive_statistics(stats):
    """Print formatted comprehensive statistics"""
    if stats is None:
        return
    
    print("\n" + "="*60)
    print("COMPREHENSIVE AUTHOR ANALYSIS RESULTS")
    print("="*60)
    print(f"Total papers in dataset: {stats['total_rows']:,}")
    if stats['parsing_errors'] > 0:
        print(f"Parsing errors encountered: {stats['parsing_errors']}")
    
    print("\n" + "-"*40)
    print("ACL AUTHORS ANALYSIS")
    print("-"*40)
    print(f"Unique ACL author (name, ID) pairs: {stats['unique_acl_authors']:,}")
    print(f"Unique ACL author names: {stats['unique_acl_names']:,}")
    print(f"ACL authors with IDs: {stats['acl_authors_with_ids']:,}")
    print(f"ACL authors without IDs (name, None): {stats['acl_authors_without_ids']:,}")
    print(f"Names appearing with multiple IDs: {stats['names_with_multiple_ids']}")
    
    print(f"\n{'='*20} TOTAL ACL AUTHORS BY LOGIC {'='*20}")
    print(f"Authors with distinct IDs: {stats['authors_with_ids_count']:,}")
    print(f"Authors with None (grouped by name): {stats['authors_with_none_count']:,}")
    print(f"TOTAL ACL AUTHORS: {stats['total_acl_authors_by_logic']:,}")
    print("="*60)
    
    print("\n" + "-"*40)
    print("DBLP AUTHORS ANALYSIS")
    print("-"*40)
    print(f"Unique DBLP authors: {stats['unique_dblp_authors']:,}")
    print(f"DBLP authors with 4-digit numbers: {stats['dblp_authors_with_numbers']:,}")
    print(f"DBLP authors without 4-digit numbers: {stats['dblp_authors_without_numbers']:,}")
    print(f"Percentage with 4-digit numbers: {(stats['dblp_authors_with_numbers'] / stats['unique_dblp_authors'] * 100):.2f}%")
    
    print(f"\nDISAMBIGUATION ANALYSIS:")
    print(f"Base names that have 4-digit disambiguation: {stats['dblp_base_names_count']:,}")
    print(f"Base names with multiple 4-digit variants: {stats['dblp_disambiguated_names_count']:,}")
    if stats['dblp_base_names_count'] > 0:
        print(f"Percentage of base names with multiple variants: {(stats['dblp_disambiguated_names_count'] / stats['dblp_base_names_count'] * 100):.2f}%")
    
    print("-"*40)
    
    if stats['names_with_multiple_ids'] > 0:
        print("\n" + "-"*40)
        print("ADDITIONAL STATISTICS")
        print("-"*40)
        print(f"ACL names with multiple IDs: {stats['names_with_multiple_ids']}")
    
    print("="*60)

def save_summary_to_file(stats, filename="revised_data/author_analysis_summary.txt"):
    """Save the comprehensive statistics summary to a text file"""
    if stats is None:
        return
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("="*70 + "\n")
        f.write("COMPREHENSIVE AUTHOR ANALYSIS SUMMARY\n")
        f.write("="*70 + "\n")
        f.write(f"Generated on: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Dataset: revised_data/acl_dblp_author_mapping.csv\n\n")
        
        f.write("DATASET OVERVIEW\n")
        f.write("-" * 20 + "\n")
        f.write(f"Total papers in dataset: {stats['total_rows']:,}\n")
        if stats['parsing_errors'] > 0:
            f.write(f"Parsing errors encountered: {stats['parsing_errors']}\n")
        f.write("\n")
        
        f.write("ACL AUTHORS ANALYSIS\n")
        f.write("-" * 20 + "\n")
        f.write(f"Unique ACL author (name, ID) pairs: {stats['unique_acl_authors']:,}\n")
        f.write(f"Unique ACL author names: {stats['unique_acl_names']:,}\n")
        f.write(f"ACL authors with IDs: {stats['acl_authors_with_ids']:,}\n")
        f.write(f"ACL authors without IDs (name, None): {stats['acl_authors_without_ids']:,}\n")
        f.write(f"Names appearing with multiple IDs: {stats['names_with_multiple_ids']}\n")
        f.write(f"\nTOTAL ACL AUTHORS BY LOGIC:\n")
        f.write(f"Authors with distinct IDs: {stats['authors_with_ids_count']:,}\n")
        f.write(f"Authors with None (grouped by name): {stats['authors_with_none_count']:,}\n")
        f.write(f"TOTAL ACL AUTHORS: {stats['total_acl_authors_by_logic']:,}\n\n")
        
        f.write("DBLP AUTHORS ANALYSIS\n")
        f.write("-" * 20 + "\n")
        f.write(f"Unique DBLP authors: {stats['unique_dblp_authors']:,}\n")
        f.write(f"DBLP authors with 4-digit numbers: {stats['dblp_authors_with_numbers']:,}\n")
        f.write(f"DBLP authors without 4-digit numbers: {stats['dblp_authors_without_numbers']:,}\n")
        f.write(f"Percentage with 4-digit numbers: {(stats['dblp_authors_with_numbers'] / stats['unique_dblp_authors'] * 100):.2f}%\n")
        f.write(f"\nDISAMBIGUATION ANALYSIS:\n")
        f.write(f"Base names that have 4-digit disambiguation: {stats['dblp_base_names_count']:,}\n")
        f.write(f"Base names with multiple 4-digit variants: {stats['dblp_disambiguated_names_count']:,}\n")
        if stats['dblp_base_names_count'] > 0:
            f.write(f"Percentage of base names with multiple variants: {(stats['dblp_disambiguated_names_count'] / stats['dblp_base_names_count'] * 100):.2f}%\n")
        f.write("\n")
        
        f.write("="*70 + "\n")
        f.write("FINAL SUMMARY\n")
        f.write("="*70 + "\n")
        f.write(f"Total unique ACL authors: {stats['total_acl_authors_by_logic']:,}\n")
        f.write(f"Total unique DBLP authors: {stats['unique_dblp_authors']:,}\n")
        f.write(f"DBLP authors with 4-digit disambiguation: {stats['dblp_authors_with_numbers']:,} ({(stats['dblp_authors_with_numbers'] / stats['unique_dblp_authors'] * 100):.1f}%)\n")
        f.write(f"DBLP base names using disambiguation: {stats['dblp_base_names_count']:,}\n")
        f.write(f"DBLP base names with multiple variants: {stats['dblp_disambiguated_names_count']:,}\n")
        f.write(f"ACL authors with assigned IDs: {stats['acl_authors_with_ids']:,}\n")
        f.write(f"Papers in dataset: {stats['total_rows']:,}\n")
        f.write("="*70 + "\n")
    
    print(f"\nSummary saved to: {filename}")

def main():
    # Define the path to the CSV file
    csv_file = "revised_data/acl_dblp_author_mapping.csv"
    
    # Check if file exists
    if not os.path.exists(csv_file):
        print(f"Error: File {csv_file} not found")
        return
    
    print("Starting comprehensive author analysis...")
    
    # Run comprehensive analysis
    comprehensive_stats = comprehensive_author_analysis(csv_file)
    print_comprehensive_statistics(comprehensive_stats)
    
    # Save summary to file
    save_summary_to_file(comprehensive_stats)
    
    # Print final summary
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)
    if comprehensive_stats:
        print(f"Total unique ACL authors: {comprehensive_stats['total_acl_authors_by_logic']:,}")
        print(f"Total unique DBLP authors: {comprehensive_stats['unique_dblp_authors']:,}")
        print(f"DBLP authors with 4-digit disambiguation: {comprehensive_stats['dblp_authors_with_numbers']:,} ({(comprehensive_stats['dblp_authors_with_numbers'] / comprehensive_stats['unique_dblp_authors'] * 100):.1f}%)")
        print(f"DBLP base names using disambiguation: {comprehensive_stats['dblp_base_names_count']:,}")
        print(f"DBLP base names with multiple variants: {comprehensive_stats['dblp_disambiguated_names_count']:,}")
        print(f"ACL authors with assigned IDs: {comprehensive_stats['acl_authors_with_ids']:,}")
        print(f"Papers in dataset: {comprehensive_stats['total_rows']:,}")
    print("="*70)

if __name__ == "__main__":
    main()
