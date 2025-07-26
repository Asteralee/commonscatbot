import requests
import random
import os

# API endpoints
API_URL = "https://simple.wikipedia.org/w/api.php"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"

# Custom headers
HEADERS = {
    'User-Agent': 'commonscatbot/1.0 (https://github.com/Asteralee/commonscatbot; bot for adding {{commonscat}} to SimpleWiki)'
}

# List of all known Commons category template names (including redirects)
COMMONS_CAT_REDIRECTS = [
    'Commonscat',
    'Commons cat',
    'Commonscat2',
    'Ccat',
    'Wikimedia commons cat',
    'Category commons',
    'C cat',
    'Commonscategory',
    'Commonsimages cat',
    'Container cat',
    'Commons Category'
]

def add_commonscat_to_page(page_title):
    params = {
        'action': 'query',
        'titles': page_title,
        'prop': 'revisions|info',
        'rvprop': 'content',
        'inprop': 'url',
        'format': 'json',
    }

    response = requests.get(API_URL, params=params, headers=HEADERS)
    data = response.json()

    pages = data['query']['pages']
    page = next(iter(pages.values()))

    if 'redirect' in page:
        print(f"{page_title} is a redirect. Skipping.")
        return

    content = page.get('revisions', [{}])[0].get('*', '')

    # Check if any commonscat variant exists
    if any(f"{{{{{template.lower()}" in content.lower() for template in COMMONS_CAT_REDIRECTS):
        print(f"A Commons category template already exists on {page_title}. Skipping.")
        return

    commons_category = get_commons_category_from_wikidata(page_title)
    if commons_category:
        if '[[Category:' in content:
            parts = content.split('[[Category:', 1)
            content = parts[0].rstrip() + '\n{{commonscat}}\n[[Category:' + parts[1]
        else:
            content = content.rstrip() + '\n{{commonscat}}'

        token = get_edit_token()
        if not token:
            print("Failed to get edit token. Skipping.")
            return

        edit_params = {
            'action': 'edit',
            'title': page_title,
            'text': content,
            'token': token,
            'summary': 'Bot: Added {{commonscat}} to article',
            'format': 'json'
        }

        session = requests.Session()
        edit_response = session.post(API_URL, data=edit_params, headers=HEADERS)
        edit_data = edit_response.json()

        if 'error' in edit_data:
            print(f"Error editing {page_title}: {edit_data['error']['info']}")
        else:
            print(f"Successfully added {{commonscat}} to {page_title}.")
    else:
        print(f"No Commons category found for {page_title}. Skipping.")

def get_commons_category_from_wikidata(page_title):
    search_params = {
        'action': 'wbsearchentities',
        'search': page_title,
        'language': 'en',
        'type': 'item',
        'format': 'json'
    }
    search_response = requests.get(WIKIDATA_API_URL, params=search_params, headers=HEADERS)
    search_data = search_response.json()

    if 'search' in search_data and len(search_data['search']) > 0:
        wikidata_id = search_data['search'][0]['id']
        entity_params = {
            'action': 'wbgetentities',
            'ids': wikidata_id,
            'props': 'claims',
            'format': 'json'
        }
        entity_response = requests.get(WIKIDATA_API_URL, params=entity_params, headers=HEADERS)
        entity_data = entity_response.json()

        claims = entity_data['entities'][wikidata_id].get('claims', {})
        commonscat_claims = claims.get('P373', [])
        if commonscat_claims:
            return commonscat_claims[0]['mainsnak']['datavalue']['value']

    return None

def get_edit_token():
    session = requests.Session()

    login_params = {
        'action': 'login',
        'lgname': os.getenv('BOT_USERNAME'),
        'lgpassword': os.getenv('BOT_PASSWORD'),
        'format': 'json'
    }
    login_response = session.post(API_URL, data=login_params, headers=HEADERS)
    login_data = login_response.json()

    if 'error' in login_data:
        print(f"Login failed: {login_data['error']['info']}")
        return None

    token_params = {
        'action': 'query',
        'meta': 'tokens',
        'format': 'json'
    }
    token_response = session.get(API_URL, params=token_params, headers=HEADERS)
    token_data = token_response.json()
    return token_data['query']['tokens']['csrftoken']

def get_random_articles():
    params = {
        'action': 'query',
        'list': 'allpages',
        'aplimit': '500',
        'format': 'json'
    }
    response = requests.get(API_URL, params=params, headers=HEADERS)
    data = response.json()
    articles = [item['title'] for item in data['query']['allpages']]
    return random.sample(articles, random.randint(3, 10))

def run_bot():
    articles = get_random_articles()
    for article in articles:
        add_commonscat_to_page(article)

run_bot()
