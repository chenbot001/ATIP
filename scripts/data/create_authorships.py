import pandas as pd
import ast
import os
import re
from thefuzz import fuzz
from unidecode import unidecode
from typing import List, Dict, Tuple, Optional

def normalize_name(name: str) -> str:
    """
    Comprehensive name normalization following the specified steps.
    
    Args:
        name: Raw author name string
        
    Returns:
        Normalized name string
    """
    # Handle None, empty strings, or non-string inputs
    if not name or not isinstance(name, str):
        return ""
    
    # Step 1: Handle "Last, First" format
    if ',' in name:
        parts = name.split(',', 1)
        if len(parts) == 2:
            name = f"{parts[1].strip()} {parts[0].strip()}"
    
    # Step 2: Transliterate special characters
    name = unidecode(name)
    
    # Step 3: Convert to lowercase
    name = name.lower()
    
    # Step 4: Remove common suffixes
    suffixes = ['jr', 'sr', 'phd', 'md', 'iii', 'ii', 'iv', 'esq', 'esquire']
    name_parts = name.split()
    filtered_parts = []
    for part in name_parts:
        if part not in suffixes:
            filtered_parts.append(part)
    name = ' '.join(filtered_parts)
    
    # Step 5: Standardize punctuation
    name = name.replace('-', ' ')  # Replace hyphens with spaces
    name = re.sub(r'[^\w\s]', '', name)  # Remove all punctuation except spaces
    
    # Step 6: Standardize whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name

def get_name_interpretations(normalized_name: str) -> List[Tuple[str, str]]:
    """
    Generate plausible (first_initial, last_name) interpretations for a normalized name.
    
    Args:
        normalized_name: Normalized name string
        
    Returns:
        List of (first_initial, last_name) tuples
    """
    parts = normalized_name.split()
    
    if len(parts) >= 3:
        # For 3+ part names, assume last part is last name, first part provides initial
        first_initial = parts[0][0] if parts[0] else ''
        last_name = parts[-1]
        return [(first_initial, last_name)]
    
    elif len(parts) == 2:
        # For 2-part names, generate two interpretations
        first_initial_1 = parts[0][0] if parts[0] else ''
        last_name_1 = parts[1]
        first_initial_2 = parts[1][0] if parts[1] else ''
        last_name_2 = parts[0]
        return [(first_initial_1, last_name_1), (first_initial_2, last_name_2)]
    
    elif len(parts) == 1:
        # For 1-part names, assume it's the last name
        return [('', parts[0])]
    
    else:
        return []

def match_authors(dblp_authors: List[str], s2_authors: List[Dict]) -> Tuple[Dict, List]:
    """
    Matches a list of DBLP author names to a list of Semantic Scholar author objects.
    
    Args:
        dblp_authors: A list of author name strings from DBLP.
        s2_authors: A list of dictionaries from Semantic Scholar, where each
                    dictionary has the format {'authorId': str, 'name': str}.
    
    Returns:
        A tuple containing:
        - A dictionary mapping each successfully matched DBLP name to its
          corresponding Semantic Scholar author dictionary.
        - A list of DBLP author names that could not be matched.
    """
    if not dblp_authors or not s2_authors:
        return {}, dblp_authors
    
    # Filter out S2 authors with empty names
    valid_s2_authors = []
    for author in s2_authors:
        if author['name'] and author['name'].strip():
            valid_s2_authors.append(author)
    
    if not valid_s2_authors:
        return {}, dblp_authors
    
    # Normalize all names
    dblp_normalized = {normalize_name(name): name for name in dblp_authors}
    s2_normalized = {normalize_name(author['name']): author for author in valid_s2_authors}
    
    # Initialize tracking variables
    matched = {}
    remaining_dblp = set(dblp_normalized.keys())
    remaining_s2 = set(s2_normalized.keys())
    
    # Pass 1: Exact Full Name Match
    exact_matches = remaining_dblp.intersection(remaining_s2)
    for norm_name in exact_matches:
        matched[dblp_normalized[norm_name]] = s2_normalized[norm_name]
        remaining_dblp.remove(norm_name)
        remaining_s2.remove(norm_name)
    
    # Pass 2: Canonical Initialism Match
    for dblp_norm in list(remaining_dblp):
        dblp_parts = dblp_norm.split()
        if len(dblp_parts) >= 2:
            # Generate initials from DBLP name
            dblp_initials = ''.join(part[0] for part in dblp_parts[:-1]) + ' ' + dblp_parts[-1]
            
            for s2_norm in list(remaining_s2):
                s2_parts = s2_norm.split()
                if len(s2_parts) >= 2:
                    # Generate initials from S2 name
                    s2_initials = ''.join(part[0] for part in s2_parts[:-1]) + ' ' + s2_parts[-1]
                    
                    if dblp_initials == s2_initials:
                        matched[dblp_normalized[dblp_norm]] = s2_normalized[s2_norm]
                        remaining_dblp.remove(dblp_norm)
                        remaining_s2.remove(s2_norm)
                        break
    
    # Pass 3: Hypothesis-Based Structural Match
    for dblp_norm in list(remaining_dblp):
        dblp_interpretations = get_name_interpretations(dblp_norm)
        
        for s2_norm in list(remaining_s2):
            s2_interpretations = get_name_interpretations(s2_norm)
            
            # Check if any interpretations match
            for dblp_interp in dblp_interpretations:
                for s2_interp in s2_interpretations:
                    if dblp_interp == s2_interp:
                        matched[dblp_normalized[dblp_norm]] = s2_normalized[s2_norm]
                        remaining_dblp.remove(dblp_norm)
                        remaining_s2.remove(s2_norm)
                        break
                if dblp_norm not in remaining_dblp:
                    break
            if dblp_norm not in remaining_dblp:
                break
    
    # Pass 4: Fuzzy Full Name Match
    for dblp_norm in list(remaining_dblp):
        best_match = None
        best_score = 0
        
        for s2_norm in list(remaining_s2):
            score = fuzz.token_sort_ratio(dblp_norm, s2_norm)
            if score > 90 and score > best_score:
                best_score = score
                best_match = s2_norm
        
        if best_match:
            matched[dblp_normalized[dblp_norm]] = s2_normalized[best_match]
            remaining_dblp.remove(dblp_norm)
            remaining_s2.remove(best_match)
    
    # Pass 5: Unique Initial-Only Match
    for dblp_norm in list(remaining_dblp):
        dblp_parts = dblp_norm.split()
        if len(dblp_parts) == 1 and len(dblp_parts[0]) == 1:
            # Single letter name
            initial = dblp_parts[0]
            matching_s2 = []
            
            for s2_norm in remaining_s2:
                s2_parts = s2_norm.split()
                if s2_parts and s2_parts[0].startswith(initial):
                    matching_s2.append(s2_norm)
            
            if len(matching_s2) == 1:
                matched[dblp_normalized[dblp_norm]] = s2_normalized[matching_s2[0]]
                remaining_dblp.remove(dblp_norm)
                remaining_s2.remove(matching_s2[0])
    
    # Pass 6: Final Positional Heuristic
    if len(remaining_dblp) == 1 and len(remaining_s2) == 1:
        dblp_norm = list(remaining_dblp)[0]
        s2_norm = list(remaining_s2)[0]
        matched[dblp_normalized[dblp_norm]] = s2_normalized[s2_norm]
        remaining_dblp.clear()
        remaining_s2.clear()
    
    # Return unmatched DBLP names
    unmatched = [dblp_normalized[norm] for norm in remaining_dblp]
    
    return matched, unmatched

def create_authorships_table(input_filepath, output_filepath):
    """
    Create an authorships table from the paper_authors dataset using enhanced name matching.
    
    Args:
        input_filepath (str): Path to the paper_authors.csv file
        output_filepath (str): Path to save the authorships.csv file
    """
    print("Loading paper authors dataset...")
    df = pd.read_csv(input_filepath)
    print(f"Loaded {len(df)} papers")
    
    # List to store all authorship records
    authorships = []
    total_papers = 0
    matched_papers = 0
    total_authors = 0
    matched_authors = 0
    
    # Process each paper
    for idx, row in df.iterrows():
        try:
            # Parse author lists
            dblp_authors = ast.literal_eval(row['dblp_authors'])
            s2_authors = ast.literal_eval(row['s2_authors'])
            s2_author_ids = ast.literal_eval(row['s2_author_ids'])
            
            total_papers += 1
            total_authors += len(dblp_authors)
            
            # Convert S2 data to the expected format for matching
            s2_author_objects = []
            empty_s2_names = 0
            for i, (name, author_id) in enumerate(zip(s2_authors, s2_author_ids)):
                # Skip entries with empty or None names
                if name and str(name).strip():
                    s2_author_objects.append({
                        'authorId': author_id,
                        'name': str(name).strip()
                    })
                else:
                    empty_s2_names += 1
            
            # Log if there are empty S2 names
            if empty_s2_names > 0:
                print(f"Paper {row['s2_id']}: Skipped {empty_s2_names} S2 authors with empty names")
            
            # Use enhanced matching strategy
            matched_authors_dict, unmatched_dblp = match_authors(dblp_authors, s2_author_objects)
            
            if matched_authors_dict:
                matched_papers += 1
                s2_id = row['s2_id']
                title = row['title']
                
                # Create authorship records for matched authors
                authorship_order = 1
                for dblp_name, s2_author in matched_authors_dict.items():
                    authorship_record = {
                        's2_id': s2_id,
                        'title': title,
                        'dblp_name': dblp_name,
                        's2_name': s2_author['name'],
                        's2_author_id': s2_author['authorId'],
                        'authorship_order': authorship_order,
                        'match_confidence': 'high' if dblp_name in s2_authors else 'matched'
                    }
                    authorships.append(authorship_record)
                    authorship_order += 1
                    matched_authors += 1
                
                # Add unmatched authors with null S2 data
                for dblp_name in unmatched_dblp:
                    authorship_record = {
                        's2_id': s2_id,
                        'title': title,
                        'dblp_name': dblp_name,
                        's2_name': None,
                        's2_author_id': None,
                        'authorship_order': authorship_order,
                        'match_confidence': 'unmatched'
                    }
                    authorships.append(authorship_record)
                    authorship_order += 1
                
                if unmatched_dblp:
                    print(f"Paper {s2_id}: {len(matched_authors_dict)} matched, {len(unmatched_dblp)} unmatched authors")
            else:
                print(f"Paper {row['s2_id']}: No authors matched")
                
        except Exception as e:
            print(f"Error processing paper {row['s2_id']}: {e}")
            continue
    
    # Create DataFrame from authorship records
    authorships_df = pd.DataFrame(authorships)
    
    # Save to CSV
    print(f"Creating authorships table with {len(authorships_df)} records...")
    authorships_df.to_csv(output_filepath, index=False)
    print(f"Authorships table saved to: {output_filepath}")
    
    # Print summary statistics
    print("\nAUTHORSHIPS TABLE SUMMARY")
    print("=" * 50)
    print(f"Total papers processed: {total_papers}")
    print(f"Papers with matched authors: {matched_papers} ({matched_papers/total_papers*100:.1f}%)")
    print(f"Total authorship records: {len(authorships_df)}")
    print(f"Total authors processed: {total_authors}")
    print(f"Successfully matched authors: {matched_authors} ({matched_authors/total_authors*100:.1f}%)")
    print(f"Unique papers: {authorships_df['s2_id'].nunique()}")
    print(f"Unique authors (by S2 ID): {authorships_df['s2_author_id'].nunique()}")
    
    # Match confidence breakdown
    if 'match_confidence' in authorships_df.columns:
        confidence_counts = authorships_df['match_confidence'].value_counts()
        print(f"\nMatch confidence breakdown:")
        for confidence, count in confidence_counts.items():
            print(f"  {confidence}: {count} ({count/len(authorships_df)*100:.1f}%)")
    
    # Show sample of the data
    print("\nSample records:")
    print(authorships_df.head(10).to_string(index=False))
    
    return authorships_df

def main():
    input_file = "revised_data/dblp_paper_authors.csv"
    output_file = "revised_data/authorships.csv"
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' does not exist.")
        return
    
    # Create authorships table
    authorships_df = create_authorships_table(input_file, output_file)
    
    print(f"\nAuthorships table creation completed successfully!")
    print(f"Output file: {output_file}")

if __name__ == "__main__":
    main() 