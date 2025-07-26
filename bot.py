import requests
import random
import os

# API endpoints
API_URL = "https://simple.wikipedia.org/w/api.php"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"

# Required User-Agent (Wikimedia policy)
HEADERS = {
    'User-Agent': 'commonscatbot/1.0 (https://github.com/Asteralee/commonscatbot; bot for adding {{commonscat}} to SimpleWiki)'
}

# Add {{commonscat}} to a page if appropriate
def add_commonscat_to_page(page_title):
    params = {
        'action': 'query',
        'titles': page_title,
        'prop': 'revisions|info',
        'rvprop': 'content',
        'inprop': 'url',
        'format': 'json',
    }

    try:
        response = requests.get(API_URL, params=params, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error loading page '{page_title}': {e}")
        return

    pages = data['query']['pages']
    page = next(iter(pages.values()))

    if 'redirect' in page:
        print(f"{page_title} is a redirect. Skipping.")
        return

    content = page.get('revisions', [{}])[0].get('*', '')
    print(f"Content of {page_title}:\n{content[:500]}")

    if '{{commonscat' in content:
        print(f"Commonscat already exists on {page_title}. Skipping.")
        return

    commons_category = get_commons_category_from_wikidata(page_title)
    if commons_category:
        if '[[Category:' in content:
            before, after = content.split('[[Category:', 1)
            content = before.rstrip() + '\n{{commonscat}}\n[[Category:' + after
        else:
            content = content.rstrip() + '\n{{commonscat}}'

        edit_token = get_edit_token()
        if not edit_token:
            print("Could not obtain edit token.")
            return

        edit_params = {
            'action': 'edit',
            'title': page_title,
            'text': content,
            'token': edit_token,
            'summary': 'Bot: Added {{commonscat}} using data from Wikidata',
            'format': 'json'
        }

        try:
            edit_response = requests.post(API_URL, data=edit_params, headers=HEADERS)
            edit_data = edit_response.json()

            if 'error' in edit_data:
                print(f"Error editing {page_title}: {edit_data['error']['info']}")
            else:
                print(f"✅ Successfully added {{commonscat}} to {page_title}.")
        except Exception as e:
            print(f"Edit request failed for {page_title}: {e}")
    else:
        print(f"No Commons category found for {page_title}. Skipping.")


# Get Commons category (P373) from Wikidata
def get_commons_category_from_wikidata(page_title):
    search_params = {
        'action': 'wbsearchentities',
        'search': page_title,
        'language': 'en',
        'type': 'item',
        'format': 'json'
    }

    try:
        search_response = requests.get(WIKIDATA_API_URL, params=search_params, headers=HEADERS)
        search_response.raise_for_status()
        search_data = search_response.json()
    except Exception as e:
        print(f"Error fetching Wikidata entity for '{page_title}': {e}")
        return None

    if 'search' in search_data and len(search_data['search']) > 0:
        wikidata_id = search_data['search'][0]['id']
        entity_params = {
            'action': 'wbgetentities',
            'ids': wikidata_id,
            'props': 'claims',
            'format': 'json'
        }

        try:
            entity_response = requests.get(WIKIDATA_API_URL, params=entity_params, headers=HEADERS)
            entity_response.raise_for_status()
            entity_data = entity_response.json()
        except Exception as e:
            print(f"Error fetching Wikidata claims for '{wikidata_id}': {e}")
            return None

        claims = entity_data['entities'].get(wikidata_id, {}).get('claims', {})
        commonscat_claims = claims.get('P373', [])

        if commonscat_claims:
            return commonscat_claims[0]['mainsnak']['datavalue']['value']

    return None


# Get edit token using bot credentials
def get_edit_token():
    session = requests.Session()

    login_params = {
        'action': 'login',
        'lgname': os.getenv('BOT_USERNAME'),
        'lgpassword': os.getenv('BOT_PASSWORD'),
        'format': 'json'
    }

    try:
        login_response = session.post(API_URL, data=login_params, headers=HEADERS)
        login_data = login_response.json()
        if 'error' in login_data:
            print(f"Login failed: {login_data['error']['info']}")
            return None
    except Exception as e:
        print(f"Login request failed: {e}")
        return None

    token_params = {
        'action': 'query',
        'meta': 'tokens',
        'format': 'json'
    }

    try:
        token_response = session.get(API_URL, params=token_params, headers=HEADERS)
        token_data = token_response.json()
        return token_data['query']['tokens']['csrftoken']
    except Exception as e:
        print(f"Token request failed: {e}")
        return None


# Grab random article titles from Special:AllPages
def get_random_articles():
    params = {
        'action': 'query',
        'list': 'allpages',
        'aplimit': '500',
        'format': 'json'
    }

    try:
        response = requests.get(API_URL, params=params, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Failed to get articles: {e}")
        return []

    articles = [item['title'] for item in data['query']['allpages']]
    return random.sample(articles, random.randint(5, 20))


# Main loop
def run_bot():
    articles = get_random_articles()
    for article in articles:
        add_commonscat_to_page(article)


# Entry point
if __name__ == '__main__':
    run_bot()
