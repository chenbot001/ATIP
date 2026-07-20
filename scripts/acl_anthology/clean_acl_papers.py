"""
ACL Papers CSV Cleaning Script

This script cleans the ACL papers CSV file by removing:
1. Preface/ToC papers (3rd tuple element of tuple_id = '0')
2. Papers from venues other than ACL, EMNLP, NAACL, or Findings
3. Findings papers where the 2nd tuple element is not 'acl', 'emnlp', or 'naacl'

Author: Cleaning Script
Date: 2025-08-07
"""

import pandas as pd
import re
from datetime import datetime

def parse_tuple_id(tuple_id_str):
    """
    Parse tuple_id string and extract the three elements
    Returns (first, second, third) or (None, None, None) if parsing fails
    """
    try:
        # Remove quotes and parse the tuple string
        tuple_str = str(tuple_id_str).strip("\"'")
        # Use regex to extract tuple elements
        match = re.match(r"\('([^']+)', '([^']+)', '([^']+)'\)", tuple_str)
        if match:
            return match.group(1), match.group(2), match.group(3)
    except:
        pass
    return None, None, None

def should_keep_row(row):
    """
    Determine if a row should be kept based on the filtering criteria
    Returns True if the row should be kept, False otherwise
    """
    venue = row['venue']
    tuple_id = row['tuple_id']
    
    # Parse the tuple_id
    first_elem, second_elem, third_elem = parse_tuple_id(tuple_id)
    
    # Condition 1: Remove preface/ToC papers (3rd element = '0')
    if third_elem == '0':
        return False
    
    # Condition 2: Keep only papers from ACL, EMNLP, NAACL, or Findings
    valid_venues = {'ACL', 'EMNLP', 'NAACL', 'Findings'}
    if venue not in valid_venues:
        return False
    
    # Condition 3: For Findings papers, check 2nd tuple element
    if venue == 'Findings':
        valid_findings_types = {'acl', 'emnlp', 'naacl'}
        if second_elem not in valid_findings_types:
            return False
    
    return True

def clean_csv(input_file, output_file):
    """
    Clean the CSV file according to the specified criteria
    """
    print(f"Reading CSV file: {input_file}")
    # Use low_memory=False to avoid DtypeWarning
    df = pd.read_csv(input_file, low_memory=False)
    
    initial_count = len(df)
    print(f"Initial number of papers: {initial_count:,}")
    
    # Count papers by category before cleaning
    print("\nBefore cleaning - Paper counts by venue:")
    venue_counts = df['venue'].value_counts()
    for venue, count in venue_counts.items():
        print(f"  {venue}: {count:,}")
    
    # Count preface/ToC papers
    preface_count = 0
    for _, row in df.iterrows():
        _, _, third_elem = parse_tuple_id(row['tuple_id'])
        if third_elem == '0':
            preface_count += 1
    
    print(f"\nPreface/ToC papers (3rd tuple element = '0'): {preface_count:,}")
    
    # Apply filtering
    print("\nApplying filters...")
    mask = df.apply(should_keep_row, axis=1)
    cleaned_df = df[mask].copy()
    
    final_count = len(cleaned_df)
    removed_count = initial_count - final_count
    
    print(f"\nAfter cleaning:")
    print(f"  Papers kept: {final_count:,}")
    print(f"  Papers removed: {removed_count:,}")
    print(f"  Removal rate: {(removed_count/initial_count)*100:.1f}%")
    
    # Count papers by category after cleaning
    print("\nAfter cleaning - Paper counts by venue:")
    cleaned_venue_counts = cleaned_df['venue'].value_counts()
    for venue, count in cleaned_venue_counts.items():
        print(f"  {venue}: {count:,}")
    
    # Special analysis for Findings papers
    findings_df = cleaned_df[cleaned_df['venue'] == 'Findings']
    if not findings_df.empty:
        print("\nFindings papers by type (2nd tuple element):")
        findings_types = {}
        for _, row in findings_df.iterrows():
            _, second_elem, _ = parse_tuple_id(row['tuple_id'])
            if second_elem:
                findings_types[second_elem] = findings_types.get(second_elem, 0) + 1
        
        for finding_type, count in sorted(findings_types.items()):
            print(f"  Findings-{finding_type}: {count:,}")
    
    # Save cleaned data
    print(f"\nSaving cleaned data to: {output_file}")
    cleaned_df.to_csv(output_file, index=False, encoding='utf-8')
    
    # Generate summary report
    report_lines = [
        "=" * 60,
        "ACL PAPERS CLEANING REPORT",
        "=" * 60,
        f"Cleaning Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Input File: {input_file}",
        f"Output File: {output_file}",
        "",
        "FILTERING CRITERIA APPLIED:",
        "1. Removed preface/ToC papers (3rd tuple element = '0')",
        "2. Kept only papers from venues: ACL, EMNLP, NAACL, Findings",
        "3. For Findings papers, kept only those with 2nd tuple element: acl, emnlp, naacl",
        "",
        "RESULTS:",
        f"  Initial papers: {initial_count:,}",
        f"  Final papers: {final_count:,}",
        f"  Papers removed: {removed_count:,}",
        f"  Removal rate: {(removed_count/initial_count)*100:.1f}%",
        "",
        "FINAL VENUE DISTRIBUTION:",
    ]
    
    for venue, count in sorted(cleaned_venue_counts.items()):
        percentage = (count / final_count) * 100
        report_lines.append(f"  {venue}: {count:,} papers ({percentage:.1f}%)")
    
    if not findings_df.empty:
        report_lines.extend([
            "",
            "FINDINGS BREAKDOWN:",
        ])
        for finding_type, count in sorted(findings_types.items()):
            percentage = (count / len(findings_df)) * 100
            report_lines.append(f"  Findings-{finding_type}: {count:,} papers ({percentage:.1f}%)")
    
    report_lines.extend([
        "",
        "=" * 60,
        "END OF CLEANING REPORT",
        "=" * 60
    ])
    
    # Save report
    # report_file = output_file.replace('.csv', '_cleaning_report.txt')
    # with open(report_file, 'w', encoding='utf-8') as f:
    #     f.write('\n'.join(report_lines))
    
    # print(f"Cleaning report saved to: {report_file}")
    print("Cleaning completed successfully!")

if __name__ == "__main__":
    input_file = "acl_papers_master.csv"
    output_file = "acl_papers_cleaned.csv"
    
    try:
        clean_csv(input_file, output_file)
    except FileNotFoundError:
        print(f"Error: Could not find the input CSV file '{input_file}'")
        print("Please make sure the file exists in the current directory.")
    except Exception as e:
        print(f"Error during cleaning: {str(e)}")
        import traceback
        traceback.print_exc()
