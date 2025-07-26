import requests
import random
import os

# API endpoints
API_URL = "https://simple.wikipedia.org/w/api.php"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"

# All redirects of {{Commons category}} on SimpleWiki
COMMONSCAT_REDIRECTS = [
    '{{Commons category}}',
    '{{Commonscat}}',
    '{{Commons cat}}',
    '{{Commonscat2}}',
    '{{Ccat}}',
    '{{Wikimedia commons cat}}',
    '{{Category commons}}',
    '{{C cat}}',
    '{{Commonscategory}}',
    '{{Commonsimages cat}}',
    '{{Container cat}}'
]

# Main function to run the bot
def run_bot():
    articles = get_random_articles()
    for article in articles:
        add_commonscat_to_page(article)

# Get a list of random non-redirect articles
def get_random_articles():
    params = {
        'action': 'query',
        'list': 'allpages',
        'aplimit': '500',
        'format': 'json',
        'apnamespace': 0
    }

    response = requests.get(API_URL, params=params)

    if response.status_code != 200 or 'application/json' not in response.headers.get('Content-Type', ''):
        print("Failed to fetch article list.")
        return []

    data = response.json()

    all_pages = data.get('query', {}).get('allpages', [])
    titles = [page['title'] for page in all_pages if 'redirect' not in page]

    # Pick 3 to 10 random articles
    return random.sample(titles, min(len(titles), random.randint(3, 10)))

# Add {{commonscat}} to a page
def add_commonscat_to_page(page_title):
    params = {
        'action': 'query',
        'titles': page_title,
        'prop': 'revisions|info',
        'rvprop': 'content',
        'inprop': 'url',
        'format': 'json'
    }

    response = requests.get(API_URL, params=params)

    if response.status_code != 200 or 'application/json' not in response.headers.get('Content-Type', ''):
        print(f"Failed to fetch page {page_title}.")
        return

    data = response.json()
    pages = data['query']['pages']
    page = next(iter(pages.values()))

    if 'redirect' in page:
        print(f"{page_title} is a redirect. Skipping.")
        return

    content = page.get('revisions', [{}])[0].get('*', '')

    if any(template.lower() in content.lower() for template in COMMONSCAT_REDIRECTS):
        print(f"Commonscat already exists on {page_title}. Skipping.")
        return

    commons_category = get_commons_category_from_wikidata(page_title)
    if not commons_category:
        print(f"No Commons category found for {page_title}. Skipping.")
        return

    # Insert template before categories if present
    if '[[Category:' in content:
        before_cat = content.split('[[Category:')[0]
        after_cat = '[[Category:' + content.split('[[Category:')[1]
        new_content = before_cat.rstrip() + '\n{{Commons category}}\n' + after_cat
    else:
        new_content = content.rstrip() + '\n{{Commons category}}'

    # Get CSRF token and session
    session, token = get_edit_token()
    if not token:
        print(f"Could not get CSRF token for {page_title}.")
        return

    edit_params = {
        'action': 'edit',
        'title': page_title,
        'text': new_content,
        'token': token,
        'summary': 'Bot: Added {{Commons category}} to article',
        'format': 'json'
    }

    edit_response = session.post(API_URL, data=edit_params)
    if edit_response.status_code != 200:
        print(f"Edit failed for {page_title}. HTTP error.")
        return

    result = edit_response.json()
    if 'error' in result:
        print(f"Error editing {page_title}: {result['error']['info']}")
    else:
        print(f"Successfully added {{Commons category}} to {page_title}.")

# Get Commons category (P373) from Wikidata
def get_commons_category_from_wikidata(page_title):
    search_params = {
        'action': 'wbsearchentities',
        'search': page_title,
        'language': 'en',
        'type': 'item',
        'format': 'json'
    }

    search_response = requests.get(WIKIDATA_API_URL, params=search_params)
    if search_response.status_code != 200:
        return None

    search_data = search_response.json()
    if 'search' not in search_data or not search_data['search']:
        return None

    wikidata_id = search_data['search'][0]['id']

    entity_params = {
        'action': 'wbgetentities',
        'ids': wikidata_id,
        'props': 'claims',
        'format': 'json'
    }

    entity_response = requests.get(WIKIDATA_API_URL, params=entity_params)
    if entity_response.status_code != 200:
        return None

    entity_data = entity_response.json()
    claims = entity_data.get('entities', {}).get(wikidata_id, {}).get('claims', {})
    p373 = claims.get('P373', [])
    if p373:
        return p373[0]['mainsnak']['datavalue']['value']

    return None

# Get CSRF token using a login session
def get_edit_token():
    session = requests.Session()

    # Step 1: Get login token
    token_params = {
        'action': 'query',
        'meta': 'tokens',
        'type': 'login',
        'format': 'json'
    }
    r1 = session.get(API_URL, params=token_params)
    login_token = r1.json()['query']['tokens']['logintoken']

    # Step 2: Log in
    login_params = {
        'action': 'login',
        'lgname': os.getenv('BOT_USERNAME'),
        'lgpassword': os.getenv('BOT_PASSWORD'),
        'lgtoken': login_token,
        'format': 'json'
    }
    r2 = session.post(API_URL, data=login_params)

    if r2.status_code != 200 or r2.json().get('login', {}).get('result') != 'Success':
        print("Login failed.")
        return session, None

    # Step 3: Get CSRF token
    token_request = {
        'action': 'query',
        'meta': 'tokens',
        'format': 'json'
    }
    r3 = session.get(API_URL, params=token_request)
    token = r3.json()['query']['tokens']['csrftoken']
    return session, token

# Run it!
if __name__ == "__main__":
    run_bot()
