#!/usr/bin/env python3
"""
Analysis script to extract and analyze author information from ACL papers dataset.
Finds all authors with non-None IDs, affiliations, and variants.
"""

import csv
import ast
from collections import defaultdict

def safe_eval(value):
    """Safely evaluate string representations of lists."""
    try:
        if value.strip() in ['[]', '', 'None']:
            return []
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        print(f"Warning: Could not parse value: {value}")
        return []

def analyze_author_data(csv_file, output_file):
    """
    Analyze author data from CSV file and extract authors with non-None information.
    
    Args:
        csv_file: Path to the input CSV file
        output_file: Path to the output text file
    """
    
    # Counters for summary statistics
    total_authors_processed = 0
    
    # Store unique author records using a set to avoid duplicates
    unique_author_records = set()
    # Also track all authors (including those without IDs) to find edge cases
    all_authors = set()
    # Collect author data for consolidation
    author_data_collector = {}
    
    print("Starting analysis of author data...")
    
    with open(csv_file, 'r', encoding='utf-8', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row_num, row in enumerate(reader, 1):
            if row_num % 1000 == 0:
                print(f"Processed {row_num} papers...")
            
            try:
                # Extract and parse the list columns
                authors = safe_eval(row['authors'])
                author_ids = safe_eval(row['author_ids'])
                author_affils = safe_eval(row['author_affils'])
                author_variants = safe_eval(row['author_variants'])
                
                # Ensure all lists have the same length
                max_len = max(len(authors), len(author_ids), len(author_affils), len(author_variants))
                
                # Pad lists to same length if needed
                while len(authors) < max_len:
                    authors.append('')
                while len(author_ids) < max_len:
                    author_ids.append(None)
                while len(author_affils) < max_len:
                    author_affils.append(None)
                while len(author_variants) < max_len:
                    author_variants.append([])
                
                # Process each author in this paper
                for i in range(len(authors)):
                    if authors[i]:  # Skip empty author names
                        total_authors_processed += 1
                        
                        author_name = authors[i]
                        author_id = author_ids[i] if i < len(author_ids) else None
                        author_affil = author_affils[i] if i < len(author_affils) else None
                        author_variant = author_variants[i] if i < len(author_variants) else []
                        
                        # Track all authors (for edge case analysis)
                        all_author_tuple = (
                            author_name,
                            author_id if author_id is not None and str(author_id).strip() != 'None' else None,
                            author_affil if author_affil is not None and str(author_affil).strip() not in ['None', ''] else None,
                            ', '.join(author_variant) if author_variant and len(author_variant) > 0 else None
                        )
                        all_authors.add(all_author_tuple)
                        
                        # Check if author has a non-None ID (used for disambiguation)
                        has_id = author_id is not None and str(author_id).strip() != 'None'
                        
                        if has_id:
                            # Create a unique tuple based on (name, id) combination only
                            # Collect all affiliations and variants for this author
                            author_key = (author_name, author_id)
                            
                            # Store affiliation if it's not N/A
                            affil_to_store = author_affil if author_affil is not None and str(author_affil).strip() not in ['None', ''] else None
                            variant_to_store = author_variant if author_variant and len(author_variant) > 0 else None
                            
                            # We'll consolidate these later
                            if author_key not in author_data_collector:
                                author_data_collector[author_key] = {
                                    'affiliations': set(),
                                    'variants': set()
                                }
                            
                            if affil_to_store:
                                author_data_collector[author_key]['affiliations'].add(affil_to_store)
                            if variant_to_store:
                                for variant in variant_to_store:
                                    author_data_collector[author_key]['variants'].add(variant)
                
            except Exception as e:
                print(f"Error processing row {row_num}: {e}")
                continue
    
    # Consolidate author data - create final unique records
    for (name, author_id), data in author_data_collector.items():
        affiliations_str = '; '.join(sorted(data['affiliations'])) if data['affiliations'] else 'N/A'
        variants_str = ', '.join(sorted(data['variants'])) if data['variants'] else 'N/A'
        
        author_tuple = (name, author_id, affiliations_str, variants_str)
        unique_author_records.add(author_tuple)
    
    # Calculate statistics from unique records
    authors_with_id = len(unique_author_records)  # All records have IDs (disambiguation cases)
    authors_with_affiliation = sum(1 for record in unique_author_records if record[2] != 'N/A')
    authors_with_variants = sum(1 for record in unique_author_records if record[3] != 'N/A')
    
    # Calculate total unique authors (including those without IDs)
    total_unique_authors = len(all_authors)
    
    # Additional analysis: find authors with same name but different IDs (disambiguation cases)
    name_groups = defaultdict(list)
    for record in unique_author_records:
        name_groups[record[0]].append(record)
    
    disambiguated_names = {name: records for name, records in name_groups.items() if len(records) > 1}
    
    # Edge case analysis: find names that appear both with and without IDs
    all_name_groups = defaultdict(list)
    for record in all_authors:
        all_name_groups[record[0]].append(record)
    
    edge_cases = {}
    for name, records in all_name_groups.items():
        has_id_records = [r for r in records if r[1] is not None]
        no_id_records = [r for r in records if r[1] is None]
        
        if has_id_records and no_id_records:
            # Consolidate no_id_records by collecting all unique affiliations and variants
            no_id_affiliations = set()
            no_id_variants = set()
            
            for record in no_id_records:
                if record[2]:  # affiliation is not None
                    no_id_affiliations.add(record[2])
                if record[3]:  # variants is not None
                    no_id_variants.add(record[3])
            
            # Create consolidated record for no-ID cases
            consolidated_no_id = (
                name,
                None,
                '; '.join(sorted(no_id_affiliations)) if no_id_affiliations else None,
                ', '.join(sorted(no_id_variants)) if no_id_variants else None
            )
            
            edge_cases[name] = {
                'with_id': has_id_records,
                'without_id': [consolidated_no_id]  # Single consolidated record
            }
    
    print(f"Finished processing. Writing {len(unique_author_records)} unique author records to {output_file}")
    
    # Write results to output file
    with open(output_file, 'w', encoding='utf-8') as outfile:
        # Write header
        outfile.write("ACL Papers Author Analysis Results\n")
        outfile.write("=" * 50 + "\n\n")
        
        # Write summary statistics
        outfile.write("SUMMARY STATISTICS:\n")
        outfile.write("-" * 20 + "\n")
        outfile.write(f"Total authors processed: {total_authors_processed:,}\n")
        outfile.write(f"Total unique authors in dataset: {total_unique_authors:,}\n")
        outfile.write(f"Unique (name, ID) combinations: {authors_with_id:,}\n")
        outfile.write(f"Authors with affiliation info: {authors_with_affiliation:,}\n")
        outfile.write(f"Authors with variant names: {authors_with_variants:,}\n")
        outfile.write(f"Disambiguated author names (same name, different IDs): {len(disambiguated_names):,}\n")
        outfile.write(f"Total disambiguation cases: {sum(len(records) for records in disambiguated_names.values()):,}\n")
        outfile.write(f"Edge cases (same name, some with ID, some without): {len(edge_cases):,}\n\n")
        
        # Write detailed records
        outfile.write("DETAILED AUTHOR RECORDS (Unique Name-ID Combinations):\n")
        outfile.write("-" * 50 + "\n")
        outfile.write("Format: Author_Name | Author_ID | Affiliation | Variants\n")
        outfile.write("-" * 80 + "\n")
        
        # Sort the unique records for consistent output
        sorted_records = sorted(unique_author_records)
        for record in sorted_records:
            name, author_id, affiliation, variants = record
            line = f"{name} | {author_id} | {affiliation} | {variants}\n"
            outfile.write(line)
        
        # Write disambiguation analysis
        if disambiguated_names:
            outfile.write(f"\n\nDISAMBIGUATION ANALYSIS:\n")
            outfile.write("-" * 25 + "\n")
            outfile.write("Authors with the same name but different IDs (disambiguation cases):\n\n")
            
            for name, records in sorted(disambiguated_names.items()):
                outfile.write(f"Name: {name}\n")
                for record in sorted(records):
                    _, author_id, affiliation, variants = record
                    outfile.write(f"  - ID: {author_id} | Affiliation: {affiliation} | Variants: {variants}\n")
                outfile.write("\n")
        
        # Write edge case analysis
        if edge_cases:
            outfile.write(f"\n\nEDGE CASE ANALYSIS:\n")
            outfile.write("-" * 20 + "\n")
            outfile.write("Authors with the same name where some have IDs and some don't:\n\n")
            
            for name, case_data in sorted(edge_cases.items()):
                outfile.write(f"Name: {name}\n")
                outfile.write("  With ID:\n")
                # Sort with None-safe key
                for record in sorted(case_data['with_id'], key=lambda x: (x[0], x[1] or '', x[2] or '', x[3] or '')):
                    _, author_id, affiliation, variants = record
                    affil_str = affiliation if affiliation else 'N/A'
                    variant_str = variants if variants else 'N/A'
                    outfile.write(f"    - ID: {author_id} | Affiliation: {affil_str} | Variants: {variant_str}\n")
                outfile.write("  Without ID:\n")
                for record in sorted(case_data['without_id'], key=lambda x: (x[0], x[1] or '', x[2] or '', x[3] or '')):
                    _, _, affiliation, variants = record
                    affil_str = affiliation if affiliation else 'N/A'
                    variant_str = variants if variants else 'N/A'
                    outfile.write(f"    - No ID | Affiliation: {affil_str} | Variants: {variant_str}\n")
                outfile.write("\n")
    
    # Print summary to console
    print("\nAnalysis Complete!")
    print("=" * 30)
    print(f"Total authors processed: {total_authors_processed:,}")
    print(f"Total unique authors in dataset: {total_unique_authors:,}")
    print(f"Unique (name, ID) combinations: {authors_with_id:,}")
    print(f"Authors with affiliation info: {authors_with_affiliation:,}")
    print(f"Authors with variant names: {authors_with_variants:,}")
    print(f"Disambiguated author names: {len(disambiguated_names):,}")
    print(f"Total disambiguation cases: {sum(len(records) for records in disambiguated_names.values()):,}")
    print(f"Edge cases (same name, some with ID, some without): {len(edge_cases):,}")
    print(f"Results saved to: {output_file}")

def main():
    csv_file = "acl_papers_cleaned.csv"
    output_file = "author_analysis_results.txt"
    
    analyze_author_data(csv_file, output_file)

if __name__ == "__main__":
    main()
