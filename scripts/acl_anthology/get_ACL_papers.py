"""
ACL Anthology Paper Information Extractor

This script extracts paper information from the ACL Anthology and saves it to a CSV file.
It processes papers from a specific collection, extracts metadata for each paper,
and also accumulates statistics about authors and papers.

The script uses the ACL Anthology API to access paper data and pandas for efficient
data manipulation and storage.

Usage:
    python paper_table.py

Requirements:
    - acl_anthology library
    - pandas
    - Python 3.6+
"""

from acl_anthology import Anthology
import pandas as pd
import os
import sys

def save_papers_to_csv(papers_df, csv_file):
    """
    Save a DataFrame of paper information to a CSV file.
    
    Args:
        papers_df (pd.DataFrame): DataFrame containing paper information.
        csv_file (str, optional): Path to the output CSV file. Defaults to 'papers_data.csv'.
        
    Returns:
        None
    """
    # Always overwrite the file to ensure outdated data is replaced
    papers_df.to_csv(csv_file, mode='w', header=True, index=False, encoding='utf-8')
    print(f"Data saved to {csv_file}")

def search_collection(anthology, collection_id=""):
    """
    Search through a collection in the ACL Anthology and extract paper information.
    
    Args:
        anthology (Anthology): Anthology instance to use for searching.
        collection_id (str, optional): ID of the collection to search. Defaults to "2024.acl".
        
    Returns:
        tuple: A tuple containing (papers_df, total_papers, all_unique_authors)
               where papers_df is a DataFrame of paper information,
               total_papers is the count of papers processed,
               and all_unique_authors is a set of unique author names.
    """
    # Get the collection
    collection = anthology.get(collection_id)
    total_papers = 0
    
    # Create a list to store all paper data
    papers_data = []
    
    for volume in collection.volumes():
        volume_papers = 0
        for paper in volume.papers():

            # Extract required attributes
            paper_id = paper.full_id
            tuple_id = paper.full_id_tuple
            parent = paper.parent
            bibkey = paper.bibkey
            title = paper.title
            paper_doi = paper.doi

            # Extract List Attributes
            attachments = paper.attachments
            authors = [author.name.as_full() for author in paper.authors]
            author_ids = [author.id for author in paper.authors]
            author_affils = [author.affiliation for author in paper.authors]
            author_variants = [author.variants for author in paper.authors]
            awards = paper.awards
            editors = [editor.name for editor in paper.editors]
            errata = paper.errata
            revisions = paper.revisions
            videos = paper.videos

            # Extract optional attributes
            abstract = paper.abstract
            deletion = paper.deletion
            ingest_date = paper.ingest_date
            issue = paper.issue
            journal = paper.journal
            language = paper.language
            note = paper.note
            pages = paper.pages
            paperswithcode = paper.paperswithcode
            pdf = paper.pdf

            # Extract other attributes
            venue = anthology.venues[paper.venue_ids[0]].acronym if paper.venue_ids else ''
            web_url = paper.web_url
            year = paper.year

            address = paper.address
            bibtype = paper.bibtype
            citeproc_dict = paper.citeproc_dict
            csltype = paper.csltype
            is_deleted = paper.is_deleted
            is_frontmatter = paper.is_frontmatter
            language_name = paper.language_name
            month = paper.month
            publisher = paper.publisher
            # root = paper.root
            

            papers_data.append({
                "paper_id": paper_id,
                "tuple_id": tuple_id,
                "doi": paper_doi,
                "parent": parent,
                "bibkey": bibkey,
                "title": title,
                "attachments": attachments,
                "authors": authors,
                "author_ids": author_ids,
                "author_affils": author_affils,
                "author_variants": author_variants,
                "awards": awards,
                "editors": editors,
                "errata": errata,
                "revisions": revisions,
                "videos": videos,
                "abstract": abstract,
                "deletion": deletion,
                "ingest_date": ingest_date,
                "issue": issue,
                "journal": journal,
                "language": language,
                "note": note,
                "pages": pages,
                "paperswithcode": paperswithcode,
                "pdf": pdf,
                "venue": venue,
                "url": web_url,
                "year": year,
                "address": address,
                "bibtype": bibtype,
                "citeproc_dict": citeproc_dict,
                "csltype": csltype,
                "is_deleted": is_deleted,
                "is_frontmatter": is_frontmatter,
                "language_name": language_name,
                "month": month,
                "publisher": publisher,
                # "root": root
            })


            # Count statistics
            volume_papers += 1
            total_papers += 1

    papers_df = pd.DataFrame(papers_data)
    print(f"Total {total_papers} papers across all volumes in collection {collection.id}:")

    return papers_df
    

if __name__ == "__main__":

    try:
        # Try to initialize anthology from local repo first
        anthology = Anthology.from_repo()
        print("Using local anthology repository.")
    except Exception as e:
        print(f"Error initializing anthology: {e}")
        print("Could not initialize anthology. Make sure the data is available.")
        sys.exit(1)

    # Read all collection IDs from acl_collections.txt
    with open("data/acl_collections.txt", "r") as file:
        collection_ids = [line.strip() for line in file]

    # Initialize an empty DataFrame to accumulate all paper data
    all_papers_df = pd.DataFrame()

    # Initialize counters for collections and papers
    total_collections = 0
    total_papers = 0

    for collection_id in collection_ids:
        print(f"Processing collection: {collection_id}")
        papers_df = search_collection(anthology, collection_id=collection_id)
        all_papers_df = pd.concat([all_papers_df, papers_df], ignore_index=True)
        total_collections += 1
        total_papers += len(papers_df)

    # Save the accumulated data to CSV
    if not all_papers_df.empty:
        save_papers_to_csv(all_papers_df, csv_file='acl_papers_master.csv')

    # Display total counts
    print(f"\nTotal collections processed: {total_collections}")
    print(f"Total papers collected: {total_papers}")

    print("Script completed successfully.")



