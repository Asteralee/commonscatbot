import requests
import json
import random
import os

API_URL = "https://simple.wikipedia.org/w/api.php"
WIKIDATA_URL = "https://www.wikidata.org/w/api.php"

# Template names that redirect to {{Commons category}}
COMMONSCAT_REDIRECTS = [
    "Commons category", "Commonscat", "Commons cat", "Commonscat2", "Ccat",
    "Wikimedia commons cat", "Category commons", "C cat", "Commonscategory",
    "Commonsimages cat", "Container cat"
]

username = os.environ['BOT_USERNAME']
password = os.environ['BOT_PASSWORD']


def get_random_articles():
    params = {
        'action': 'query',
        'list': 'random',
        'rnnamespace': 0,
        'rnlimit': 15,
        'format': 'json'
    }
    response = requests.get(API_URL, params=params)
    if response.status_code != 200 or 'application/json' not in response.headers.get('Content-Type', ''):
        print("Failed to fetch random articles.")
        return []

    data = response.json()
    titles = [item['title'] for item in data['query']['random']]

    check_params = {
        'action': 'query',
        'titles': '|'.join(titles),
        'prop': 'info',
        'format': 'json'
    }
    check_response = requests.get(API_URL, params=check_params)
    if check_response.status_code != 200 or 'application/json' not in check_response.headers.get('Content-Type', ''):
        print("Failed to filter redirects.")
        return []

    check_data = check_response.json()
    non_redirects = [page['title'] for page in check_data['query']['pages'].values() if 'redirect' not in page]
    return random.sample(non_redirects, min(len(non_redirects), random.randint(3, 10)))


def page_has_commonscat(wikitext):
    for template in COMMONSCAT_REDIRECTS:
        if f"{{{{{template}" in wikitext:
            return True
    return False


def get_commons_category_from_wikidata(title):
    # Step 1: Get Wikidata entity ID
    site_params = {
        'action': 'query',
        'titles': title,
        'prop': 'pageprops',
        'format': 'json'
    }
    site_response = requests.get(API_URL, params=site_params)
    if site_response.status_code != 200 or 'application/json' not in site_response.headers.get('Content-Type', ''):
        print(f"Failed to fetch Wikidata entity for {title}")
        return None
    site_data = site_response.json()
    pages = site_data['query']['pages']
    entity_id = next(iter(pages.values())).get('pageprops', {}).get('wikibase_item')
    if not entity_id:
        return None

    # Step 2: Get P373 from Wikidata
    wd_params = {
        'action': 'wbgetclaims',
        'entity': entity_id,
        'property': 'P373',
        'format': 'json'
    }
    wd_response = requests.get(WIKIDATA_URL, params=wd_params)
    if wd_response.status_code != 200 or 'application/json' not in wd_response.headers.get('Content-Type', ''):
        print(f"Failed to fetch P373 for {title}")
        return None
    wd_data = wd_response.json()
    try:
        return wd_data['claims']['P373'][0]['mainsnak']['datavalue']['value']
    except (KeyError, IndexError):
        return None


def login(session):
    r1 = session.get(API_URL, params={
        'action': 'query',
        'meta': 'tokens',
        'type': 'login',
        'format': 'json'
    })
    login_token = r1.json()['query']['tokens']['logintoken']

    r2 = session.post(API_URL, data={
        'action': 'login',
        'lgname': username,
        'lgpassword': password,
        'lgtoken': login_token,
        'format': 'json'
    })
    print("Logged in as", username)


def get_csrf_token(session):
    r = session.get(API_URL, params={
        'action': 'query',
        'meta': 'tokens',
        'format': 'json'
    })
    return r.json()['query']['tokens']['csrftoken']


def add_commonscat_to_page(title):
    session = requests.Session()
    login(session)
    token = get_csrf_token(session)

    r = session.get(API_URL, params={
        'action': 'query',
        'prop': 'revisions',
        'titles': title,
        'rvslots': 'main',
        'rvprop': 'content',
        'format': 'json'
    })
    if r.status_code != 200 or 'application/json' not in r.headers.get('Content-Type', ''):
        print(f"Failed to get content of {title}")
        return

    pages = r.json()['query']['pages']
    pageid, page = next(iter(pages.items()))
    if 'revisions' not in page:
        print(f"No content found for {title}")
        return

    wikitext = page['revisions'][0]['slots']['main']['*']
    if page_has_commonscat(wikitext):
        print(f"{title} already has a commons category template. Skipping.")
        return

    commonscat_value = get_commons_category_from_wikidata(title)
    if not commonscat_value:
        print(f"No Commons category found for {title}. Skipping.")
        return

    new_text = wikitext + f"\n\n{{{{Commons category|{commonscat_value}}}}}"

    edit_response = session.post(API_URL, data={
        'action': 'edit',
        'title': title,
        'text': new_text,
        'token': token,
        'format': 'json',
        'summary': 'Adding Commons category from Wikidata (P373)'
    })

    if edit_response.status_code == 200:
        print(f"Successfully added {{commonscat}} to {title}.")
    else:
        print(f"Failed to edit {title}.")


def run_bot():
    articles = get_random_articles()
    for article in articles:
        add_commonscat_to_page(article)


if __name__ == '__main__':
    run_bot()
