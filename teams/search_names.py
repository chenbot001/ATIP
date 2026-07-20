import pandas as pd
import os

def search_author_in_profiles():
    """
    Search for names from nlp_team.txt in author_profiles.csv and append results.
    If duplicate names are found, use the author ID with the highest citations.
    """
    
    # File paths
    team_file = "cmu_team.txt"
    author_profiles_file = "data/author_profiles.csv"
    citation_metrics_file = "data/author_citation_metrics.csv"
    
    print("Loading author profiles...")
    # Load the author profiles dataset
    try:
        author_profiles = pd.read_csv(author_profiles_file)
        print(f"Loaded {len(author_profiles)} author profiles")
    except Exception as e:
        print(f"Error loading author profiles: {e}")
        return
    
    print("Loading citation metrics...")
    # Load citation metrics to resolve duplicates
    try:
        citation_metrics = pd.read_csv(citation_metrics_file, usecols=['author_id', 'total_citations'])
        print(f"Loaded {len(citation_metrics)} citation records")
    except Exception as e:
        print(f"Error loading citation metrics: {e}")
        # Try alternative citation file
        try:
            citation_metrics = pd.read_csv("data/derived_metrics/citation_acceleration.csv", usecols=['author_id', 'total_citations'])
            print(f"Loaded {len(citation_metrics)} citation records from alternative source")
        except Exception as e2:
            print(f"Error loading alternative citation data: {e2}")
            print("Proceeding without citation data - will use first match for duplicates")
            citation_metrics = pd.DataFrame(columns=['author_id', 'total_citations'])
    
    # Merge author profiles with citation data
    author_profiles = author_profiles.merge(citation_metrics, on='author_id', how='left')
    author_profiles['total_citations'] = author_profiles['total_citations'].fillna(0)
    
    # Create a combined name field for easier searching
    author_profiles['full_name'] = (author_profiles['first_name'].fillna('') + ' ' + 
                                   author_profiles['last_name'].fillna('')).str.strip()
    
    print("Reading team list...")
    # Read the team names
    try:
        with open(team_file, 'r', encoding='utf-8') as f:
            names = [line.strip() for line in f.readlines() if line.strip()]
        print(f"Found {len(names)} names to search")
    except Exception as e:
        print(f"Error reading meta team file: {e}")
        return
    
    print("Searching for matches...")
    # Process each name and find matches
    results = []
    found_count = 0
    
    for name in names:
        print(f"Searching for: {name}")
        
        # Try exact match first
        exact_match = author_profiles[author_profiles['full_name'].str.lower() == name.lower()]
        
        if not exact_match.empty:
            if len(exact_match) > 1:
                # Multiple exact matches - select the one with highest citations
                best_match = exact_match.loc[exact_match['total_citations'].idxmax()]
                author_id = best_match['author_id']
                citations = best_match['total_citations']
                results.append(f"{name} | {author_id}")
                found_count += 1
                print(f"  Found {len(exact_match)} exact matches, selected highest citations: {author_id} ({citations} citations)")
            else:
                author_id = exact_match.iloc[0]['author_id']
                citations = exact_match.iloc[0]['total_citations']
                results.append(f"{name} | {author_id}")
                found_count += 1
                print(f"  Found exact match: {author_id} ({citations} citations)")
        else:
            # Try partial matches (in case of different name formats)
            name_parts = name.lower().split()
            
            # Look for matches where both first and last name appear
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = name_parts[-1]
                
                partial_match = author_profiles[
                    (author_profiles['first_name'].str.lower().str.contains(first_name, na=False)) &
                    (author_profiles['last_name'].str.lower().str.contains(last_name, na=False))
                ]
                
                if not partial_match.empty:
                    if len(partial_match) > 1:
                        # Multiple partial matches - select the one with highest citations
                        best_match = partial_match.loc[partial_match['total_citations'].idxmax()]
                        author_id = best_match['author_id']
                        citations = best_match['total_citations']
                        results.append(f"{name} | {author_id}")
                        found_count += 1
                        print(f"  Found {len(partial_match)} partial matches, selected highest citations: {author_id} ({citations} citations)")
                    else:
                        author_id = partial_match.iloc[0]['author_id']
                        citations = partial_match.iloc[0]['total_citations']
                        results.append(f"{name} | {author_id}")
                        found_count += 1
                        print(f"  Found partial match: {author_id} ({citations} citations)")
                else:
                    results.append(f"{name} | not found")
                    print(f"  Not found")
            else:
                results.append(f"{name} | not found")
                print(f"  Not found")
    
    print(f"\nProcessing complete. Found {found_count} out of {len(names)} names.")
    
    # Write results back to the original file
    try:
        with open(team_file, 'w', encoding='utf-8') as f:
            for result in results:
                f.write(result + '\n')
        print(f"Results saved to {team_file}")
    except Exception as e:
        print(f"Error writing results: {e}")
        return
    
    # Print summary
    print(f"\nSummary:")
    print(f"Total names processed: {len(names)}")
    print(f"Found in database: {found_count}")
    print(f"Not found: {len(names) - found_count}")

if __name__ == "__main__":
    search_author_in_profiles()
