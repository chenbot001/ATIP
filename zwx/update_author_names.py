#!/usr/bin/env python3
"""
Author Names Update Script
Update author names across multiple CSV files using complete data from author_profiles.csv
"""

import pandas as pd
import numpy as np
import os
from typing import Dict, List, Tuple


def load_author_name_mapping():
    """Load author profiles and create author_id to full_name mapping"""
    print("Loading author profiles data...")
    
    try:
        profiles_df = pd.read_csv('/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/author_profiles.csv')
        print(f"Author profiles data: {len(profiles_df)} records")
        
        # Create full name mapping dictionary
        name_mapping = {}
        valid_count = 0
        
        for _, row in profiles_df.iterrows():
            author_id = row['author_id']
            first_name = row['first_name']
            last_name = row['last_name']
            
            # Only create mapping for valid data
            if pd.notna(author_id) and pd.notna(first_name) and pd.notna(last_name):
                first_name_str = str(first_name).strip()
                last_name_str = str(last_name).strip()
                
                if first_name_str and last_name_str:
                    full_name = f"{first_name_str} {last_name_str}"
                    name_mapping[author_id] = full_name
                    valid_count += 1
        
        print(f"Created name mappings: {valid_count} valid entries")
        return name_mapping
        
    except Exception as e:
        print(f"Error loading author profiles: {e}")
        return None


def update_csv_file(file_path: str, name_mapping: Dict, field_mappings: List[Tuple[str, str]]) -> bool:
    """
    Update a CSV file with new author names
    
    Args:
        file_path: Path to the CSV file
        name_mapping: Dictionary mapping author_id to full_name
        field_mappings: List of (id_field, name_field) tuples to update
    
    Returns:
        True if successful, False otherwise
    """
    if not os.path.exists(file_path):
        print(f"  File not found: {file_path}")
        return False
    
    try:
        # Load the file
        df = pd.read_csv(file_path)
        original_count = len(df)
        
        # Track updates
        total_updates = 0
        field_update_counts = {}
        
        # Process each field mapping
        for id_field, name_field in field_mappings:
            if id_field not in df.columns or name_field not in df.columns:
                print(f"  Warning: Missing columns {id_field} or {name_field}")
                continue
            
            update_count = 0
            
            # Update names based on ID mapping
            for idx, row in df.iterrows():
                author_id = row[id_field]
                
                # Check if we have a mapping for this ID
                if pd.notna(author_id) and author_id in name_mapping:
                    new_name = name_mapping[author_id]
                    current_name = row[name_field]
                    
                    # Only update if different
                    if str(current_name) != str(new_name):
                        df.at[idx, name_field] = new_name
                        update_count += 1
            
            field_update_counts[f"{id_field}->{name_field}"] = update_count
            total_updates += update_count
        
        # Save updated file
        base_name = os.path.splitext(file_path)[0]
        output_path = f"{base_name}_updated.csv"
        df.to_csv(output_path, index=False)
        
        # Report results
        print(f"  Records: {original_count}")
        for field_pair, count in field_update_counts.items():
            print(f"  Updated {field_pair}: {count}")
        print(f"  Total updates: {total_updates}")
        print(f"  Saved to: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"  Error updating file: {e}")
        return False


def main():
    """Main function to update all files"""
    print("=== Author Names Update Script ===\n")
    
    # 1. Load author name mapping
    name_mapping = load_author_name_mapping()
    if name_mapping is None:
        print("Failed to load author profiles, exiting")
        return
    
    # Show some examples
    print(f"\n=== Name Mapping Examples (first 5) ===")
    for i, (author_id, full_name) in enumerate(list(name_mapping.items())[:5]):
        print(f"  Author ID {author_id}: '{full_name}'")
    
    # 2. Define files and their field mappings
    files_config = [
        {
            'path': '/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/author_citation_metrics.csv',
            'mappings': [('author_id', 'author_name')]
        },
        {
            'path': '/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/author_coauthor_hindex.csv',
            'mappings': [('author_id', 'author_name')]
        },
        {
            'path': '/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/authorships.csv',
            'mappings': [('author_id', 'author_name')]
        },
        {
            'path': '/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/coauthors_by_author.csv',
            'mappings': [('researcher_id', 'author_name'), ('coauthor_id', 'coauthor_name')]
        },
        {
            'path': '/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/coauthors_by_paper.csv',
            'mappings': [('author_id', 'author_name')]
        },
        {
            'path': '/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/h_index_comparison.csv',
            'mappings': [('author_id', 'author_name')]
        }
    ]
    
    # 3. Update each file
    print(f"\n=== Updating Files ===")
    success_count = 0
    
    for config in files_config:
        file_path = config['path']
        field_mappings = config['mappings']
        filename = os.path.basename(file_path)
        
        print(f"\nUpdating {filename}...")
        
        if update_csv_file(file_path, name_mapping, field_mappings):
            success_count += 1
    
    # 4. Summary
    print(f"\n=== Update Complete ===")
    print(f"Successfully updated: {success_count}/{len(files_config)} files")
    print("All updated files have been saved with '_updated' suffix.")
    
    # Check for any special cases in coauthors_by_paper.csv
    coauthors_paper_path = '/Users/kele/实习/阿联酋/爬取/AI_Researcher_Network/data/coauthors_by_paper.csv'
    if os.path.exists(coauthors_paper_path):
        try:
            df_check = pd.read_csv(coauthors_paper_path)
            columns = df_check.columns.tolist()
            print(f"\nNote: coauthors_by_paper.csv columns: {columns}")
            if 'coauthor_id' in columns and 'coauthor_name' in columns:
                print("  This file also contains coauthor fields that could be updated.")
        except:
            pass


if __name__ == "__main__":
    main()
