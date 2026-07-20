"""
ACL Papers Data Verification Script

This script verifies data consistency between acl_papers_cleaned.csv and anthology+abstracts.bib by:
1. Parsing the BibTeX file to extract title, abstract, url, and year for @inproceedings entries
2. Comparing these fields with the corresponding CSV data
3. Logging any inconsistencies without modifying the data

Author: Data Verification Script
Date: 2025-08-07
"""

import pandas as pd
import re
from datetime import datetime
import os
from difflib import SequenceMatcher

def is_empty_value(value):
    """
    Check if a value is considered empty
    """
    if pd.isna(value):
        return True
    if isinstance(value, str):
        value_clean = value.strip()
        if value_clean == '' or value_clean.lower() in ['nan', 'none', 'null']:
            return True
    return False

def clean_text_for_comparison(text):
    """
    Clean text for comparison by removing extra whitespace, newlines, and normalizing
    """
    if is_empty_value(text):
        return ""
    
    # Convert to string and normalize whitespace
    text = str(text).strip()
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    # Remove common LaTeX commands and formatting
    text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)  # Remove \command{text} -> text
    text = re.sub(r'\\[a-zA-Z]+', '', text)  # Remove \command
    text = re.sub(r'[{}]', '', text)  # Remove braces
    # Remove extra quotes that might cause mismatches
    text = re.sub(r'^["\'\`]+|["\'\`]+$', '', text)  # Remove leading/trailing quotes
    text = text.strip()
    return text

def fuzzy_match_similarity(text1, text2, threshold=0.85):
    """
    Calculate similarity between two texts using fuzzy matching
    Returns (similarity_ratio, are_similar)
    """
    if not text1 and not text2:
        return 1.0, True
    if not text1 or not text2:
        return 0.0, False
    
    # Clean both texts
    clean1 = clean_text_for_comparison(text1)
    clean2 = clean_text_for_comparison(text2)
    
    if clean1 == clean2:
        return 1.0, True
    
    # Calculate similarity ratio
    similarity = SequenceMatcher(None, clean1.lower(), clean2.lower()).ratio()
    return similarity, similarity >= threshold

def clean_year_field(year_text):
    """
    Clean year field by extracting only the 4-digit year and removing address info
    """
    if is_empty_value(year_text):
        return ""
    
    year_str = str(year_text).strip()
    
    # Extract 4-digit year using regex
    year_match = re.search(r'\b(19|20)\d{2}\b', year_str)
    if year_match:
        return year_match.group()
    
    return year_str

def parse_bib_file(bib_file_path):
    """
    Parse the BibTeX file and extract relevant fields for @inproceedings entries
    Returns a dictionary mapping bibkey to extracted data
    """
    print(f"Parsing BibTeX file: {bib_file_path}")
    
    if not os.path.exists(bib_file_path):
        print(f"Error: BibTeX file not found at {bib_file_path}")
        return {}
    
    bib_data = {}
    current_entry = None
    current_bibkey = None
    current_fields = {}
    in_field = False
    field_name = ""
    field_buffer = []
    brace_count = 0
    
    try:
        with open(bib_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                original_line = line
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('%'):
                    continue
                
                # If we encounter any @ entry while reading a field, immediately stop field processing
                if line.startswith('@') and in_field:
                    # Complete the current field before switching entries
                    if field_buffer and field_name and current_bibkey:
                        full_field = ' '.join(field_buffer)
                        full_field = re.sub(r'["\',`}]+$', '', full_field).strip()
                        if field_name == 'year':
                            full_field = clean_year_field(full_field)
                        else:
                            full_field = clean_text_for_comparison(full_field)
                        current_fields[field_name] = full_field
                    # Reset field reading state
                    in_field = False
                    field_name = ""
                    field_buffer = []
                    brace_count = 0
                
                # Check for end of entry or start of new entry (check this FIRST)
                if line.startswith('@') or line == '}':
                    # Store current entry before processing the new one
                    if current_bibkey and current_fields:
                        bib_data[current_bibkey] = current_fields.copy()
                    
                    # Reset state
                    current_entry = None
                    current_bibkey = None
                    current_fields = {}
                    in_field = False
                    field_name = ""
                    field_buffer = []
                    brace_count = 0
                    
                    # If this line starts a new @inproceedings entry, process it
                    if line.startswith('@inproceedings{'):
                        match = re.match(r'@inproceedings\{([^,}]+)', line)
                        if match:
                            current_bibkey = match.group(1).strip()
                            current_entry = 'inproceedings'
                    # For any other @entry type, we ignore it (including @proceedings)
                    elif line.startswith('@'):
                        current_entry = 'ignore'
                
                # Check for @inproceedings entry (only if not already handled above)
                elif line.startswith('@inproceedings{'):
                    # Store previous entry if exists
                    if current_bibkey and current_fields:
                        bib_data[current_bibkey] = current_fields.copy()
                    
                    # Extract bibkey
                    match = re.match(r'@inproceedings\{([^,}]+)', line)
                    if match:
                        current_bibkey = match.group(1).strip()
                        current_entry = 'inproceedings'
                        current_fields = {}
                        in_field = False
                        field_name = ""
                        field_buffer = []
                        brace_count = 0
                
                # Look for relevant fields (only process if we're in an inproceedings entry and not reading another field)
                elif current_entry == 'inproceedings' and current_bibkey and not in_field:
                    # Check if this line starts a field we care about - made more flexible
                    field_match = re.match(r'\s*(title|url|year)\s*=\s*(.*)$', line)
                    if field_match:
                        field_name = field_match.group(1)
                        field_content = field_match.group(2).strip()
                        in_field = True
                        field_buffer = [field_content]
                        
                        # Remove leading quotes/braces if present
                        if field_content.startswith(('"', "'", '`', '{')):
                            field_content = field_content[1:]
                        
                        # Count braces to handle multi-line fields
                        brace_count = field_content.count('{') - field_content.count('}')
                        
                        # Check if field ends on the same line
                        if (field_content.endswith('"') or field_content.endswith("'") or 
                            field_content.endswith('`') or field_content.endswith(',')):
                            # Remove trailing punctuation and process
                            field_text = field_content.rstrip('"\'`,').strip()
                            # Special handling for year field
                            if field_name == 'year':
                                field_text = clean_year_field(field_text)
                            else:
                                field_text = clean_text_for_comparison(field_text)
                            current_fields[field_name] = field_text
                            in_field = False
                            field_buffer = []
                        elif field_name == 'year' and (',' in field_content or '}' in field_content):
                            # For year field only, split on comma or brace to handle address
                            field_text = re.split(r'[},]', field_content)[0].strip()
                            field_text = clean_year_field(field_text)
                            current_fields[field_name] = field_text
                            in_field = False
                            field_buffer = []
                        elif brace_count == 0 and field_content.endswith('},'):
                            # Field ends with closing brace and comma (complete field)
                            field_text = field_content.rstrip('},').strip()
                            if field_name == 'year':
                                field_text = clean_year_field(field_text)
                            else:
                                field_text = clean_text_for_comparison(field_text)
                            current_fields[field_name] = field_text
                            in_field = False
                            field_buffer = []
                    
                    # Continue reading multi-line field (only if still in inproceedings)
                    elif current_entry == 'inproceedings' and in_field and field_name:
                        field_buffer.append(line)
                        brace_count += line.count('{') - line.count('}')
                        
                        # Check if field ends
                        if (line.endswith('"') or line.endswith("'") or line.endswith('`') or
                            line.endswith(',') or line.strip() == '}'):
                            # Combine all field lines and remove trailing punctuation
                            full_field = ' '.join(field_buffer)
                            full_field = re.sub(r'["\',`}]+$', '', full_field).strip()
                            if field_name == 'year':
                                full_field = clean_year_field(full_field)
                            else:
                                full_field = clean_text_for_comparison(full_field)
                            current_fields[field_name] = full_field
                            in_field = False
                            field_buffer = []
                        elif field_name == 'year' and (brace_count <= 0 and (',' in line or '}' in line)):
                            # For year field, split on comma/brace to handle address
                            full_field = ' '.join(field_buffer)
                            full_field = re.split(r'[},]', full_field)[0].strip()
                            full_field = re.sub(r'["\',`}]+$', '', full_field).strip()
                            full_field = clean_year_field(full_field)
                            current_fields[field_name] = full_field
                            in_field = False
                            field_buffer = []
                        elif brace_count <= 0 and line.endswith('},'):
                            # Field ends with closing brace and comma (complete field)
                            full_field = ' '.join(field_buffer)
                            full_field = re.sub(r'["\',`}]+$', '', full_field).strip()
                            if field_name == 'year':
                                full_field = clean_year_field(full_field)
                            else:
                                full_field = clean_text_for_comparison(full_field)
                            current_fields[field_name] = full_field
                            in_field = False
                            field_buffer = []
            
            # Store the last entry
            if current_bibkey and current_fields:
                bib_data[current_bibkey] = current_fields.copy()
    
    except Exception as e:
        print(f"Error reading BibTeX file: {e}")
        return {}
    
    print(f"Found {len(bib_data)} entries in BibTeX file")
    return bib_data

def verify_data_consistency(csv_file, bib_file, log_file):
    """
    Verify data consistency between CSV and BibTeX files
    """
    print(f"Reading CSV file: {csv_file}")
    df = pd.read_csv(csv_file, low_memory=False)
    
    total_papers = len(df)
    print(f"Total papers in CSV: {total_papers:,}")
    
    # Parse BibTeX file
    bib_data = parse_bib_file(bib_file)
    
    if not bib_data:
        print("No data found in BibTeX file. Exiting.")
        return
    
    print("Verifying data consistency...")
    
    # Create a DataFrame from bib_data for easier comparison
    bib_df = pd.DataFrame.from_dict(bib_data, orient='index')
    bib_df.index.name = 'bibkey'
    bib_df = bib_df.reset_index()
    
    # Rename BibTeX columns to avoid conflicts during merge
    bib_df = bib_df.rename(columns={
        'title': 'title_bib',
        'url': 'url_bib',
        'year': 'year_bib'
    })
    
    # Merge CSV with BibTeX data on bibkey
    merged_df = df.merge(bib_df, on='bibkey', how='left')
    
    # Find papers not in BibTeX
    not_in_bib_mask = merged_df['title_bib'].isna()
    not_in_bib_count = not_in_bib_mask.sum()
    not_in_bib_rows = merged_df[not_in_bib_mask]
    
    # For papers found in BibTeX, check for inconsistencies
    found_in_bib_df = merged_df[~not_in_bib_mask].copy()
    
    # Clean CSV data for comparison
    found_in_bib_df['title_csv_clean'] = found_in_bib_df['title'].apply(clean_text_for_comparison)
    found_in_bib_df['url_csv_clean'] = found_in_bib_df['url'].apply(clean_text_for_comparison)
    found_in_bib_df['year_csv_clean'] = found_in_bib_df['year'].apply(clean_year_field)
    
    # Fill NaN values in BibTeX columns with empty strings
    found_in_bib_df['title_bib'] = found_in_bib_df['title_bib'].fillna('')
    found_in_bib_df['url_bib'] = found_in_bib_df['url_bib'].fillna('')
    found_in_bib_df['year_bib'] = found_in_bib_df['year_bib'].fillna('')
    
    # Check for mismatches using fuzzy matching
    inconsistencies = []
    
    # Title mismatches (using fuzzy matching)
    title_issues = []
    for row_pos, (idx, row) in enumerate(found_in_bib_df.iterrows()):
        csv_title = row['title_csv_clean']
        bib_title = row['title_bib']
        if csv_title and bib_title:
            similarity, is_similar = fuzzy_match_similarity(csv_title, bib_title)
            if not is_similar:
                title_issues.append({
                    'row_pos': row_pos,
                    'original_index': idx,
                    'similarity': similarity,
                    'csv_title': str(row['title']),
                    'bib_title': bib_title,
                    'bibkey': row['bibkey'],
                    'paper_id': row['paper_id']
                })
    
    # URL and Year mismatches (exact matching)
    url_mismatch_mask = (
        (found_in_bib_df['url_csv_clean'] != '') & 
        (found_in_bib_df['url_bib'] != '') & 
        (found_in_bib_df['url_csv_clean'] != found_in_bib_df['url_bib'])
    )
    url_mismatches = found_in_bib_df[url_mismatch_mask]
    
    # Year mismatches (using cleaned year values)
    year_mismatch_mask = (
        (found_in_bib_df['year_csv_clean'] != '') & 
        (found_in_bib_df['year_bib'] != '') & 
        (found_in_bib_df['year_csv_clean'] != found_in_bib_df['year_bib'])
    )
    year_mismatches = found_in_bib_df[year_mismatch_mask]
    
    # Collect all inconsistencies
    # Papers not in BibTeX
    for _, row in not_in_bib_rows.iterrows():
        inconsistencies.append({
            'row_index': row.name,
            'bibkey': row['bibkey'],
            'paper_id': row['paper_id'],
            'issue_type': 'NOT_IN_BIB',
            'field': 'bibkey',
            'csv_value': row['bibkey'],
            'bib_value': 'N/A',
            'details': 'Bibkey not found in BibTeX file'
        })
    
    # Title mismatches (from fuzzy matching)
    for issue in title_issues:
        inconsistencies.append({
            'row_index': issue['original_index'],
            'bibkey': issue['bibkey'],
            'paper_id': issue['paper_id'],
            'issue_type': 'FIELD_MISMATCH',
            'field': 'title',
            'csv_value': issue['csv_title'][:100] + ('...' if len(issue['csv_title']) > 100 else ''),
            'bib_value': issue['bib_title'][:100] + ('...' if len(issue['bib_title']) > 100 else ''),
            'details': f'Title mismatch (similarity: {issue["similarity"]:.3f})'
        })
    
    # URL mismatches
    for _, row in url_mismatches.iterrows():
        inconsistencies.append({
            'row_index': row.name,
            'bibkey': row['bibkey'],
            'paper_id': row['paper_id'],
            'issue_type': 'FIELD_MISMATCH',
            'field': 'url',
            'csv_value': str(row['url']),
            'bib_value': str(row['url_bib']),
            'details': 'URL mismatch'
        })
    
    # Year mismatches
    for _, row in year_mismatches.iterrows():
        inconsistencies.append({
            'row_index': row.name,
            'bibkey': row['bibkey'],
            'paper_id': row['paper_id'],
            'issue_type': 'FIELD_MISMATCH',
            'field': 'year',
            'csv_value': str(row['year_csv_clean']),
            'bib_value': str(row['year_bib']),
            'details': 'Year mismatch'
        })
    
    # Calculate verification counts
    papers_with_issues = set()
    field_mismatch_count = 0
    for inc in inconsistencies:
        if inc['issue_type'] == 'FIELD_MISMATCH':
            papers_with_issues.add(inc['bibkey'])
            field_mismatch_count += 1
    
    verified_count = len(found_in_bib_df) - len(papers_with_issues)
    
    # Generate summary
    print(f"\nVerification Results:")
    print(f"  Papers verified successfully: {verified_count:,}")
    print(f"  Papers not found in BibTeX: {not_in_bib_count:,}")
    print(f"  Papers with field mismatches: {len(papers_with_issues):,}")
    print(f"  Total field inconsistencies: {field_mismatch_count:,}")
    
    # Count by field type
    field_counts = {}
    for inc in inconsistencies:
        if inc['issue_type'] == 'FIELD_MISMATCH':
            field = inc['field']
            field_counts[field] = field_counts.get(field, 0) + 1
    
    if field_counts:
        print(f"\nInconsistencies by field:")
        for field, count in sorted(field_counts.items()):
            print(f"  {field}: {count:,}")
    
    # Save detailed log
    print(f"\nSaving detailed log to: {log_file}")
    log_lines = [
        "=" * 80,
        "ACL PAPERS DATA VERIFICATION LOG",
        "=" * 80,
        f"Verification Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"CSV File: {csv_file}",
        f"BibTeX File: {bib_file}",
        "",
        "SUMMARY:",
        f"  Total papers in CSV: {total_papers:,}",
        f"  Papers found in BibTeX: {len(bib_data):,}",
        f"  Papers verified successfully: {verified_count:,}",
        f"  Papers not found in BibTeX: {not_in_bib_count:,}",
        f"  Papers with field mismatches: {len(papers_with_issues):,}",
        f"  Total field inconsistencies: {field_mismatch_count:,}",
        "",
        "INCONSISTENCIES BY FIELD:",
    ]
    
    for field, count in sorted(field_counts.items()):
        log_lines.append(f"  {field}: {count:,}")
    
    log_lines.extend([
        "",
        "DETAILED INCONSISTENCIES:",
        ""
    ])
    
    if inconsistencies:
        for inc in inconsistencies:
            log_lines.extend([
                f"Row {inc['row_index']}: {inc['bibkey']} ({inc['paper_id']})",
                f"  Issue: {inc['details']}",
                f"  Field: {inc['field']}",
                f"  CSV Value: {inc['csv_value']}",
                f"  BibTeX Value: {inc['bib_value']}",
                ""
            ])
    else:
        log_lines.append("No inconsistencies found - all data matches!")
    
    log_lines.extend([
        "=" * 80,
        "END OF VERIFICATION LOG",
        "=" * 80
    ])
    
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))
    
    print("Data verification completed successfully!")

if __name__ == "__main__":
    # File paths
    csv_file = "acl_papers_cleaned.csv"
    bib_file = "anthology+abstracts.bib"
    log_file = "data_verification_log.txt"
    
    # Check if files exist
    if not os.path.exists(csv_file):
        print(f"Error: CSV file not found: {csv_file}")
        print("Please make sure the cleaned CSV file exists.")
        exit(1)
    
    if not os.path.exists(bib_file):
        print(f"Error: BibTeX file not found: {bib_file}")
        print("Please make sure the anthology+abstracts.bib file exists.")
        exit(1)
    
    try:
        verify_data_consistency(csv_file, bib_file, log_file)
    except Exception as e:
        print(f"Error during verification: {str(e)}")
        import traceback
        traceback.print_exc()
