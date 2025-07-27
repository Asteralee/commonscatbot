import os
import requests
import mwparserfromhell
import random
import time

API_URL = "https://simple.wikipedia.org/w/api.php"
COMMONSCAT_ALIASES = [
    "Commonscat", "Commons cat", "Commonscat2", "Ccat", "Wikimedia commons cat",
    "Category commons", "C cat", "Commonscategory", "Commonsimages cat",
    "Container cat", "Commons Category"
]

HEADERS = {
    'User-Agent': 'CommonscatBot/1.0 (https://simple.wikipedia.org/wiki/User:Asteralee)'
}

def login_and_get_session(username, password):
    session = requests.Session()
    session.headers.update(HEADERS)

    # Get login token
    r1 = session.get(API_URL, params={
        'action': 'query',
        'meta': 'tokens',
        'type': 'login',
        'format': 'json'
    })
    login_token = r1.json()['query']['tokens']['logintoken']

    # Log in
    r2 = session.post(API_URL, data={
        'action': 'login',
        'lgname': username,
        'lgpassword': password,
        'lgtoken': login_token,
        'format': 'json'
    })
    print("Login response:", r2.json())

    return session

def get_csrf_token(session):
    r = session.get(API_URL, params={
        'action': 'query',
        'meta': 'tokens',
        'format': 'json'
    })
    return r.json()['query']['tokens']['csrftoken']

def is_redirect(session, title):
    response = session.get(API_URL, params={
        'action': 'query',
        'titles': title,
        'redirects': False,
        'format': 'json'
    })
    pages = response.json()['query']['pages']
    return any('redirect' in page for page in pages.values())

def fetch_random_article(session):
    while True:
        response = session.get(API_URL, params={
            'action': 'query',
            'list': 'random',
            'rnnamespace': 0,
            'rnlimit': 1,
            'format': 'json'
        })
        article = response.json()['query']['random'][0]['title']
        if not is_redirect(session, article):
            return article

def has_commonscat(wikitext):
    wikicode = mwparserfromhell.parse(wikitext)
    templates = wikicode.filter_templates()
    return any(template.name.strip() in COMMONSCAT_ALIASES for template in templates)

def fetch_commons_category_from_wikidata(title, session):
    r = session.get(API_URL, params={
        'action': 'query',
        'prop': 'pageprops',
        'titles': title,
        'format': 'json'
    })
    pages = r.json()['query']['pages']
    for page in pages.values():
        if 'pageprops' in page and 'wikibase_item' in page['pageprops']:
            qid = page['pageprops']['wikibase_item']
            wikidata_response = session.get(f"https://www.wikidata.org/w/api.php", params={
                'action': 'wbgetclaims',
                'entity': qid,
                'property': 'P373',
                'format': 'json'
            })
            claims = wikidata_response.json().get('claims', {})
            if 'P373' in claims:
                return claims['P373'][0]['mainsnak']['datavalue']['value']
    return None

def add_commonscat_to_page(title, session):
    # Get wikitext
    response = session.get(API_URL, params={
        'action': 'query',
        'prop': 'revisions',
        'titles': title,
        'rvslots': 'main',
        'rvprop': 'content',
        'formatversion': 2,
        'format': 'json'
    })
    try:
        page = response.json()['query']['pages'][0]
        if 'missing' in page:
            print(f"Page {title} does not exist.")
            return
        text = page['revisions'][0]['slots']['main']['content']
    except Exception as e:
        print(f"Failed to fetch {title}: {e}")
        return

    if has_commonscat(text):
        print(f"Page {title} already has a Commonscat template.")
        return

    commonscat_value = fetch_commons_category_from_wikidata(title, session)
    if not commonscat_value:
        print(f"No Commons category found for {title}. Skipping.")
        return

    new_text = text.strip() + f"\n\n{{{{Commonscat|{commonscat_value}}}}}"
    csrf_token = get_csrf_token(session)

    r = session.post(API_URL, data={
        'action': 'edit',
        'title': title,
        'text': new_text,
        'token': csrf_token,
        'format': 'json',
        'summary': 'Adding Commons category using P373 from Wikidata',
        'assert': 'user',
        'bot': True
    })

    result = r.json()
    print("Edit response:", result)
    if 'edit' in result and result['edit'].get('result') == 'Success':
        print(f"Successfully added {{commonscat}} to {title}.")
    else:
        print(f"Failed to edit {title}: {result}")

def run_bot():
    username = os.getenv('BOT_USERNAME')
    password = os.getenv('BOT_PASSWORD')

    if not username or not password:
        print("Username or password not set in environment variables.")
        return

    session = login_and_get_session(username, password)
    for _ in range(10):
        article = fetch_random_article(session)
        print(f"\nProcessing article: {article}")
        add_commonscat_to_page(article, session)
        time.sleep(2)

if __name__ == '__main__':
    run_bot()
