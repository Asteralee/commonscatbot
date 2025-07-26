import requests
import random
import os

# Set the API endpoint for SimpleWiki and Wikidata
API_URL = "https://simple.wikipedia.org/w/api.php"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"

# All commonscat template variants to check for
COMMONSCAT_VARIANTS = [
    '{{Commonscat}}',
    '{{Commons cat}}',
    '{{Commonscat2}}',
    '{{Ccat}}',
    '{{Wikimedia commons cat}}',
    '{{Category commons}}',
    '{{C cat}}',
    '{{Commonscategory}}',
    '{{Commonsimages cat}}',
    '{{Container cat}}',
    '{{Commons Category}}'
]

# Function to add {{commonscat}} to a page if not already added
def add_commonscat_to_page(page_title):
    params = {
        'action': 'query',
        'titles': page_title,
        'prop': 'revisions|info',
        'rvprop': 'content',
        'inprop': 'url',
        'format': 'json',
    }

    response = requests.get(API_URL, params=params)
    data = response.json()
    pages = data['query']['pages']
    page = next(iter(pages.values()))

    if 'redirect' in page:
        print(f"{page_title} is a redirect. Skipping.")
        return

    content = page.get('revisions', [{}])[0].get('*', '')

    if any(template.lower() in content.lower() for template in COMMONSCAT_VARIANTS):
        print(f"Commonscat already exists on {page_title}. Skipping.")
        return

    commons_category = get_commons_category_from_wikidata(page_title)
    if commons_category:
        if '[[Category:' in content:
            content = content.split('[[Category:')[0].rstrip() + '\n{{Commonscat}}\n[[Category:' + content.split('[[Category:')[1]
        else:
            content += '\n{{Commonscat}}'

        edit_token = get_edit_token()
        if not edit_token:
            print("Could not get edit token. Skipping.")
            return

        edit_params = {
            'action': 'edit',
            'title': page_title,
            'text': content,
            'token': edit_token,
            'summary': 'Bot: Added {{commonscat}} to article',
            'format': 'json'
        }

        session = requests.Session()
        edit_response = session.post(API_URL, data=edit_params)
        edit_data = edit_response.json()

        if 'error' in edit_data:
            print(f"Error editing {page_title}: {edit_data['error']['info']}")
        else:
            print(f"Successfully added {{commonscat}} to {page_title}.")
    else:
        print(f"No Commons category found for {page_title}. Skipping.")

# Function to get the Commons category (P373) from Wikidata
def get_commons_category_from_wikidata(page_title):
    search_params = {
        'action': 'wbsearchentities',
        'search': page_title,
        'language': 'en',
        'type': 'item',
        'format': 'json'
    }

    search_response = requests.get(WIKIDATA_API_URL, params=search_params)
    search_data = search_response.json()

    if 'search' in search_data and search_data['search']:
        wikidata_id = search_data['search'][0]['id']
        entity_params = {
            'action': 'wbgetentities',
            'ids': wikidata_id,
            'props': 'claims',
            'format': 'json'
        }

        entity_response = requests.get(WIKIDATA_API_URL, params=entity_params)
        entity_data = entity_response.json()

        if 'entities' in entity_data and wikidata_id in entity_data['entities']:
            claims = entity_data['entities'][wikidata_id].get('claims', {})
            commonscat_claims = claims.get('P373', [])

            if commonscat_claims:
                return commonscat_claims[0]['mainsnak']['datavalue']['value']

    return None

# Function to get the edit token for authentication
def get_edit_token():
    session = requests.Session()

    login_params = {
        'action': 'login',
        'lgname': os.getenv('BOT_USERNAME'),
        'lgpassword': os.getenv('BOT_PASSWORD'),
        'format': 'json'
    }

    login_response = session.post(API_URL, data=login_params)
    login_data = login_response.json()

    if 'error' in login_data:
        print(f"Login failed: {login_data['error']['info']}")
        return None

    token_params = {
        'action': 'query',
        'meta': 'tokens',
        'format': 'json'
    }
    token_response = session.get(API_URL, params=token_params)
    token_data = token_response.json()

    return token_data['query']['tokens']['csrftoken']

# Get random articles (not redirects)
def get_random_articles():
    params = {
        'action': 'query',
        'list': 'random',
        'rnnamespace': 0,
        'rnlimit': 15,
        'format': 'json'
    }

    response = requests.get(API_URL, params=params)
    data = response.json()
    random_titles = [item['title'] for item in data['query']['random']]

    titles_string = '|'.join(random_titles)
    check_params = {
        'action': 'query',
        'titles': titles_string,
        'prop': 'info',
        'format': 'json'
    }

    check_response = requests.get(API_URL, params=check_params)
    check_data = check_response.json()

    non_redirect_articles = []
    for page in check_data['query']['pages'].values():
        if 'redirect' not in page:
            non_redirect_articles.append(page['title'])

    selected = random.sample(non_redirect_articles, min(len(non_redirect_articles), random.randint(3, 10)))
    return selected

# Main function to run the bot
def run_bot():
    articles = get_random_articles()
    for article in articles:
        add_commonscat_to_page(article)

# Run the bot
run_bot()
