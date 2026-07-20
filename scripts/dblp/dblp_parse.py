import pandas as pd
from lxml import etree
from tqdm import tqdm
import os

def parse_and_filter_dblp(dblp_xml_path, venues_to_keep):
    """
    Parses the DBLP XML with a byte-based progress bar, extracting comprehensive
    paper details for a specific set of conference venues.
    
    Args:
        dblp_xml_path (str): The file path to the DBLP XML data dump.
        venues_to_keep (set): A set of venue acronyms to filter for (e.g., {'acl', 'emnlp'}).

    Returns:
        pandas.DataFrame: A DataFrame containing the filtered and parsed paper data.
    """
    print(f"🚀 Parsing DBLP XML for venues: {', '.join(venues_to_keep)}...")
    
    rows = []
    total_size = os.path.getsize(dblp_xml_path)

    # Use a context manager for the file and tqdm progress bar
    with open(dblp_xml_path, 'rb') as f, tqdm(
        total=total_size,
        unit='B',
        unit_scale=True,
        desc="Parsing DBLP"
    ) as pbar:
        # Create a memory-efficient iterator for 'inproceedings' tags
        context = etree.iterparse(f, 
                                  events=('end',), 
                                  tag='inproceedings', 
                                  dtd_validation=True, 
                                  load_dtd=True,
                                  resolve_entities=False,
                                  encoding='ISO-8859-1')

        for _, paper in context:
            try:
                # The venue is the second part of the key attribute
                key = paper.attrib['key']
                conf = key.split('/')[1]

                if conf in venues_to_keep:
                    # --- Comprehensive Data Extraction ---
                    
                    # Essential fields: title and authors must exist
                    title_element = paper.find("title")
                    authors = [author.text for author in paper.findall("author") if author.text]
                    
                    # Skip record if essential information is missing
                    if title_element is None or not authors:
                        continue

                    # Helper function to safely get text from an element
                    def get_text(element):
                        return element.text if element is not None else None

                    # Create a dictionary with all required fields
                    record = {
                        'key': key,
                        'title': get_text(title_element),
                        'authors': authors,
                        'year': get_text(paper.find("year")),
                        'pages': get_text(paper.find("pages")),
                        'ee': get_text(paper.find("ee")),
                        'venue': get_text(paper.find("booktitle"))
                    }
                    rows.append(record)

            except (AttributeError, IndexError):
                # Catch potential errors from malformed keys or elements
                continue
            finally:
                # Update progress bar and clear memory
                pbar.update(f.tell() - pbar.n)
                paper.clear()
                while paper.getprevious() is not None:
                    del paper.getparent()[0]

    del context
    
    if not rows:
        print("\n⚠️ No papers found for the specified venues.")
        return pd.DataFrame()

    print(f"\n✅ Finished parsing. Found {len(rows)} papers.")
    return pd.DataFrame(rows)

# --- Main execution block ---
if __name__ == "__main__":
    # --- Configuration ---
    DBLP_XML_PATH = 'dblp.xml'
    OUTPUT_CSV_PATH = 'revised_data/dblp_papers_master.csv'
    
    # Define the desired columns and their order
    DF_COLUMNS = ['key', 'title', 'authors', 'year', 'pages', 'ee', 'venue']
    
    # Define the conference venues to keep
    venues_to_keep = {'acl', 'naacl', 'emnlp'}

    # 1. Parse the XML to get the data
    papers_df = parse_and_filter_dblp(DBLP_XML_PATH, venues_to_keep)
    
    if not papers_df.empty:
        # 2. Keep authors as list of strings (no conversion to comma-separated string)
        # This ensures consistency with ACL dataset format
        
        # 3. Ensure the DataFrame columns are in the correct order
        papers_df = papers_df[DF_COLUMNS]

        # 4. Save the cleaned and formatted data to a CSV file
        papers_df.to_csv(OUTPUT_CSV_PATH, index=False)
        print(f"💾 Success! Data saved to {OUTPUT_CSV_PATH}")