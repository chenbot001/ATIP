"""
Script to compare similarity between ACL names and DBLP names from author profiles.

This script loads the author profiles dataframe and compares the similarity between
ACL names and DBLP names (with 4-digit identifiers removed). It uses the same
hybrid approach as the dataframe creation script, checking for initial/abbreviation
matches before proceeding with similarity checks. It logs any pairs with under 30% 
similarity that are NOT valid initial/abbreviation matches.
"""

import pandas as pd
import re
from difflib import SequenceMatcher
from datetime import datetime
from typing import Tuple

def remove_dblp_identifiers(name: str) -> str:
    """
    Remove 4-digit DBLP identifiers from author names.
    
    Args:
        name: DBLP author name that may contain identifiers like ' 0001'
        
    Returns:
        Name with DBLP identifiers removed
    """
    # Remove patterns like ' 0001', ' 0012', etc. at the end of names
    pattern = r'\s+\d{4}$'
    cleaned_name = re.sub(pattern, '', name)
    return cleaned_name.strip()

def extract_initials(name: str) -> str:
    """Extract initials from a full name."""
    # Remove DBLP identifiers first
    name_clean = remove_dblp_identifiers(name.strip())
    # Split by spaces and get first letter of each part
    parts = name_clean.split()
    initials = ''.join([part[0].upper() for part in parts if part and part[0].isalpha()])
    return initials

def is_initial_match(acl_name: str, dblp_name: str) -> bool:
    """
    Check if DBLP name could be an abbreviation/initial of ACL name.
    
    Returns True if:
    1. DBLP name is a single letter and matches first initial of ACL name
    2. DBLP name matches the initials of ACL name
    3. DBLP name is a partial abbreviation that matches the beginning of ACL name
    4. DBLP name is the first few characters of the first name in ACL name
    """
    acl_clean = acl_name.strip()
    dblp_clean = remove_dblp_identifiers(dblp_name.strip())
    
    # Case 1: Single letter match
    if len(dblp_clean) == 1 and len(acl_clean) > 0:
        return dblp_clean.upper() == acl_clean[0].upper()
    
    # Case 2: Full initials match
    acl_initials = extract_initials(acl_clean)
    if len(dblp_clean) > 1 and dblp_clean.upper() == acl_initials:
        return True
    
    # Case 3: Partial name match (like "Juan Antonio P" matching "Juan Antonio Pérez-Ortiz")
    dblp_parts = dblp_clean.split()
    acl_parts = acl_clean.split()
    
    if len(dblp_parts) > 1 and len(acl_parts) >= len(dblp_parts):
        # Check if each DBLP part matches or is an abbreviation of corresponding ACL part
        for i, dblp_part in enumerate(dblp_parts):
            if i >= len(acl_parts):
                return False
            acl_part = acl_parts[i]
            
            # Exact match or DBLP part is abbreviation of ACL part
            if (dblp_part.lower() != acl_part.lower() and 
                not acl_part.lower().startswith(dblp_part.lower()) and
                dblp_part.upper() != acl_part[0].upper()):
                return False
        return True
    
    # Case 4: DBLP name is the first few characters of the first name in ACL name
    # Handle cases like "Fr" matching "Frédérique Laforest" or "Gon" matching "Goncalo Emanuel"
    if len(dblp_clean) > 1 and len(acl_parts) > 0:
        first_acl_name = acl_parts[0]
        # Check if DBLP name is a prefix of the first ACL name (minimum 2 characters to avoid false positives)
        if len(dblp_clean) >= 2 and first_acl_name.lower().startswith(dblp_clean.lower()):
            return True
    
    return False

def calculate_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two names using SequenceMatcher.
    
    Args:
        name1: First name to compare
        name2: Second name to compare
        
    Returns:
        Similarity ratio between 0 and 1
    """
    # Normalize names: lowercase and remove extra spaces
    name1_norm = ' '.join(name1.lower().split())
    name2_norm = ' '.join(name2.lower().split())
    
    # Calculate similarity
    similarity = SequenceMatcher(None, name1_norm, name2_norm).ratio()
    return similarity

def find_dissimilar_names(csv_file_path: str, similarity_threshold: float = 0.3) -> list:
    """
    Find ACL-DBLP name pairs with similarity below threshold that are NOT valid initial/abbreviation matches.
    
    Args:
        csv_file_path: Path to the author profiles CSV
        similarity_threshold: Minimum similarity threshold (default 0.3 = 30%)
        
    Returns:
        List of tuples with dissimilar name information
    """
    # Load the dataframe
    print("Loading author profiles...")
    df = pd.read_csv(csv_file_path)
    print(f"Loaded {len(df)} author profile records")
    
    dissimilar_pairs = []
    initial_matches_found = 0
    total_comparisons = len(df)
    
    print(f"Comparing names with similarity threshold: {similarity_threshold:.1%}")
    print("Using hybrid approach: checking initial/abbreviation matches first")
    
    for record_idx, (idx, row) in enumerate(df.iterrows()):
        if record_idx % 5000 == 0:
            print(f"Processing record {record_idx + 1}/{total_comparisons}")
            
        acl_name = str(row['acl_name'])
        dblp_name = str(row['dblp_name'])
        
        # Clean DBLP name by removing identifiers
        dblp_name_clean = remove_dblp_identifiers(dblp_name)
        
        # First check if this is a valid initial/abbreviation match
        if is_initial_match(acl_name, dblp_name):
            initial_matches_found += 1
            continue  # Skip this pair - it's a valid initial match
        
        # Calculate similarity for non-initial matches
        similarity = calculate_similarity(acl_name, dblp_name_clean)
        
        # If similarity is below threshold, record it (these are genuine mismatches)
        if similarity < similarity_threshold:
            dissimilar_pairs.append({
                'row_number': record_idx + 1,  # 1-based row numbering
                'acl_name': acl_name,
                'dblp_name': dblp_name,
                'dblp_name_clean': dblp_name_clean,
                'similarity': similarity,
                'acl_id': row.get('acl_id', 'None') if 'acl_id' in df.columns and pd.notna(row.get('acl_id')) else 'None',
                'match_type': 'similarity_mismatch'
            })
    
    print(f"\nFound {initial_matches_found} valid initial/abbreviation matches (excluded from report)")
    print(f"Found {len(dissimilar_pairs)} genuine similarity mismatches below {similarity_threshold:.1%}")
    return dissimilar_pairs

def save_dissimilar_names_report(dissimilar_pairs: list, output_file: str):
    """
    Save dissimilar name pairs to a formatted text file.
    
    Args:
        dissimilar_pairs: List of dissimilar name pair dictionaries
        output_file: Path to output text file
    """
    print(f"Saving report to: {output_file}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Write header
        f.write("=" * 80 + "\n")
        f.write("ACL-DBLP NAME SIMILARITY ANALYSIS REPORT (HYBRID APPROACH)\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total genuine mismatches found: {len(dissimilar_pairs)}\n")
        f.write(f"Similarity threshold: < 30%\n")
        f.write("Note: Valid initial/abbreviation matches are excluded\n")
        f.write("=" * 80 + "\n\n")
        
        # Sort by similarity (lowest first)
        sorted_pairs = sorted(dissimilar_pairs, key=lambda x: x['similarity'])
        
        for i, pair in enumerate(sorted_pairs, 1):
            f.write(f"PAIR {i:4d} | Similarity: {pair['similarity']:.1%} | Row: {pair['row_number']}\n")
            f.write("-" * 60 + "\n")
            f.write(f"ACL Name:        {pair['acl_name']}\n")
            f.write(f"DBLP Name:       {pair['dblp_name']}\n")
            f.write(f"DBLP Cleaned:    {pair['dblp_name_clean']}\n")
            f.write(f"ACL ID:          {pair['acl_id']}\n")
            f.write(f"Row Number:      {pair['row_number']}\n")
            f.write("\n")
        
        # Write summary statistics
        f.write("=" * 80 + "\n")
        f.write("SUMMARY STATISTICS\n")
        f.write("=" * 80 + "\n")
        
        if dissimilar_pairs:
            similarities = [p['similarity'] for p in dissimilar_pairs]
            f.write(f"Lowest similarity:  {min(similarities):.1%}\n")
            f.write(f"Highest similarity: {max(similarities):.1%}\n")
            f.write(f"Average similarity: {sum(similarities)/len(similarities):.1%}\n")
            
            # Count by similarity ranges
            very_low = sum(1 for s in similarities if s < 0.1)
            low = sum(1 for s in similarities if 0.1 <= s < 0.2)
            medium = sum(1 for s in similarities if 0.2 <= s < 0.3)
            
            f.write(f"\nSimilarity distribution:\n")
            f.write(f"  < 10%:     {very_low:4d} pairs\n")
            f.write(f"  10-20%:    {low:4d} pairs\n")
            f.write(f"  20-30%:    {medium:4d} pairs\n")

def main():
    """Main function to analyze name similarities."""
    # Input and output files
    csv_file_path = "revised_data/author_profiles_new.csv"
    output_file = "logs/name_similarity_analysis.txt"
    
    # Find dissimilar names
    dissimilar_pairs = find_dissimilar_names(csv_file_path, similarity_threshold=0.3)
    
    # Save report
    save_dissimilar_names_report(dissimilar_pairs, output_file)
    
    # Print summary
    print(f"\nAnalysis complete!")
    print(f"Report saved to: {output_file}")
    
    if dissimilar_pairs:
        print(f"\nTop 5 most dissimilar pairs (genuine mismatches):")
        sorted_pairs = sorted(dissimilar_pairs, key=lambda x: x['similarity'])
        for i, pair in enumerate(sorted_pairs[:5], 1):
            print(f"{i}. Row {pair['row_number']} | {pair['similarity']:.1%} - '{pair['acl_name']}' vs '{pair['dblp_name_clean']}'")
    else:
        print("No genuine mismatches found! All low similarity pairs are valid initial/abbreviation matches.")

if __name__ == "__main__":
    main()
