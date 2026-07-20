import requests
import json

def batch_request(api_key, id_list):
    """
    Make a batch request to Semantic Scholar API for multiple paper IDs
    
    Args:
        api_key (str): Semantic Scholar API key
        id_list (list): List of paper IDs to fetch
    
    Returns:
        dict: JSON response from the API
    """
    r = requests.post(
        'https://api.semanticscholar.org/graph/v1/paper/batch',
        params={'fields': 'paperId,corpusId,externalIds,title,authors'},
        headers={'x-api-key': api_key},
        json={"ids": id_list}
    )
    return r.json()

def search_by_title(api_key, title):
    """
    Search for a paper by title using Semantic Scholar API
    
    Args:
        api_key (str): Semantic Scholar API key
        title (str): Paper title to search for
    
    Returns:
        str: Paper ID if found, None otherwise
    """
    r = requests.get(
        'https://api.semanticscholar.org/graph/v1/paper/search',
        headers={'x-api-key': api_key},
        params={
            'query': title,
            'limit': 1,
            'fields': 'paperId,externalIds,title,authors'
        }
    )
    
    response = r.json()
    return response

def get_author_name(api_key, author_id):
    """
    Get the full name of a researcher using their Semantic Scholar author ID
    
    Args:
        api_key (str): Semantic Scholar API key
        author_id (str): Semantic Scholar author ID
    
    Returns:
        str: Full name of the researcher if found, None otherwise
    """
    r = requests.get(
        f'https://api.semanticscholar.org/graph/v1/author/{author_id}',
        headers={'x-api-key': api_key},
        params={
            'fields': 'name,affiliations,papers'
        }
    )
    
    if r.status_code == 200:
        response = r.json()
        return response
    else:
        print(f"Error: {r.status_code} - {r.text}")
        return None

if __name__ == "__main__":
    # Add your Semantic Scholar API key here
    API_KEY = "39B73CXWua7xhzGlxFrNJ5wY6uIjXCna9sLxWL2w"  
    id_list = ["DOI:10.18653/v1/2023.findings-emnlp.856"]
    test_author_id = "1398834003"
    title = "Mixtures of In-Context Learners."
    
    response = batch_request(API_KEY, id_list)
    print(json.dumps(response, indent=2, ensure_ascii=False))

    
    # author_name = get_author_name(API_KEY, test_author_id)
    # print(json.dumps(author_name, indent=2, ensure_ascii=False))

    # response = search_by_title(API_KEY, title)
    # print(json.dumps(response, indent=2, ensure_ascii=False))


