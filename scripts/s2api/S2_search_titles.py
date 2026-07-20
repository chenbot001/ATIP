import requests
import csv

API_KEY = "39B73CXWua7xhzGlxFrNJ5wY6uIjXCna9sLxWL2w"  # Replace with your Semantic Scholar API key
INPUT_CSV = "paper_ids_new.csv"
OUTPUT_CSV = "paper_ids_new_filled.csv"

def search_by_title(api_key, title):
    url = 'https://api.semanticscholar.org/graph/v1/paper/search'
    headers = {'x-api-key': api_key}
    params = {
        'query': title,
        'limit': 1,
        'fields': 'paperId,corpusId,externalIds,title'
    }
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 200:
        data = r.json()
        if data.get('data'):
            paper = data['data'][0]
            s2_id = paper.get('paperId', '')
            corpus_id = paper.get('corpusId', '')
            doi = paper.get('externalIds', {}).get('DOI', '')
            return s2_id, corpus_id, doi
    return '', '', ''

def main():
    with open(INPUT_CSV, newline='', encoding='utf-8') as infile, \
         open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            if not row['s2_id']:
                s2_id, corpus_id, doi = search_by_title(API_KEY, row['title'])
                row['s2_id'] = s2_id
                row['corpus_id'] = corpus_id
                if not row['DOI']:
                    row['DOI'] = doi
            writer.writerow(row)

if __name__ == "__main__":
    main()