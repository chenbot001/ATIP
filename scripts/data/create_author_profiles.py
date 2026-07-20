#!/usr/bin/env python3
"""
Script to create author profiles with columns: acl_name, acl_id, dblp_name, affiliation
- Extracts unique (acl_name, acl_id, dblp_name) tuples from authorships_new.csv
- Looks up affiliations from csrankings.csv using dblp_name
- Outputs to author_profiles.csv in the data/ directory
"""

import pandas as pd
import os

def load_authorships(file_path):
    """Load authorships data and extract unique (acl_name, acl_id, dblp_name) tuples."""
    print(f"Loading authorships from {file_path}...")
    df = pd.read_csv(file_path)
    
    # Extract unique (acl_name, acl_id, dblp_name) tuples
    # Filter out rows where dblp_name is missing
    df_filtered = df[df['dblp_name'].notna() & (df['dblp_name'] != '')]
    
    # Fill missing acl_id values with empty string
    df_filtered = df_filtered.copy()
    df_filtered['acl_id'] = df_filtered['acl_id'].fillna('')
    
    unique_tuples = df_filtered[['acl_name', 'acl_id', 'dblp_name']].drop_duplicates()
    print(f"Found {len(unique_tuples)} unique (acl_name, acl_id, dblp_name) tuples")
    
    return unique_tuples

def load_csrankings(file_path):
    """Load csrankings data for affiliation lookup."""
    print(f"Loading csrankings from {file_path}...")
    df = pd.read_csv(file_path)
    
    # Create a mapping from name to affiliation
    # Handle potential duplicates by taking the first occurrence
    name_to_affiliation = df.set_index('name')['affiliation'].to_dict()
    print(f"Loaded {len(name_to_affiliation)} name-affiliation mappings")
    
    return name_to_affiliation

def create_author_profiles(unique_tuples, name_to_affiliation):
    """Create author profiles with affiliation lookup."""
    print("Creating author profiles...")
    
    # Initialize the profiles dataframe
    profiles = unique_tuples.copy()
    
    # Look up affiliations based on dblp_name
    profiles['affiliation'] = profiles['dblp_name'].map(name_to_affiliation).fillna('')
    
    # Count successful matches
    matched_count = (profiles['affiliation'] != '').sum()
    print(f"Successfully matched {matched_count} out of {len(profiles)} authors with affiliations")
    
    return profiles

def main():
    # File paths
    authorships_file = '/revised_data/authorships_new.csv'
    csrankings_file = '/csrankings.csv'
    output_file = '/revised_data/author_profiles_new.csv'
    
    # Check if input files exist
    if not os.path.exists(authorships_file):
        print(f"Error: {authorships_file} not found")
        return
    
    if not os.path.exists(csrankings_file):
        print(f"Error: {csrankings_file} not found")
        return
    
    try:
        # Load data
        unique_tuples = load_authorships(authorships_file)
        name_to_affiliation = load_csrankings(csrankings_file)
        
        # Create profiles
        profiles = create_author_profiles(unique_tuples, name_to_affiliation)
        
        # Ensure output directory exists
        os.makedirs('../revised_data', exist_ok=True)
        
        # Save results
        profiles.to_csv(output_file, index=False)
        print(f"Author profiles saved to {output_file}")
        
        # Print summary statistics
        print("\nSummary:")
        print(f"Total unique author tuples: {len(profiles)}")
        print(f"Authors with affiliations: {(profiles['affiliation'] != '').sum()}")
        print(f"Authors without affiliations: {(profiles['affiliation'] == '').sum()}")
        print(f"Authors with ACL IDs: {(profiles['acl_id'] != '').sum()}")
        print(f"Authors without ACL IDs: {(profiles['acl_id'] == '').sum()}")
        
        # Show a few examples
        print("\nFirst 10 profiles:")
        print(profiles.head(10).to_string(index=False))
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
