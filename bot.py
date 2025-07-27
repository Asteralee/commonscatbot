import os
import requests
import mwparserfromhell
import random
import time

API_URL = "https://simple.wikipedia.org/w/api.php"

# Full list of blocking templates (Commonscat and its siblings/redirects)
BLOCKING_TEMPLATES = [
    # Commonscat family
    "Commonscat", "Commons cat", "Commonscat2", "Ccat", "Wikimedia commons cat",
    "Category commons", "C cat", "Commonscategory", "Commonsimages cat",
    "Container cat", "Commons Category", "Commons category", "commonscat",
    "commons cat", "commonscat2", "ccat", "wikimedia commons cat",
    "category commons", "c cat", "commonscategory", "commonsimages cat",
    "container cat", "commons category", "commons category",

    # Commons category multi
    "Commons category multi", "Commonscats", "Commons cat multi", "Commonscat multi",
    "commons category multi", "commonscats", "commons cat multi", "commonscat multi",

    # Commons
    "Commons", "Wikimedia Commons", 
    "commons", "wikimedia commons",

    # Commons category-inline
    "Commons category-inline", "Commonscat-inline", "Commons cat-inline",
    "Commons category inline", "Commonscat inline", "Commonscatinline", "Commons-cat-inline",
    "commons category-inline", "commonscat-inline", "commons cat-inline",
    "commons category inline", "commonscat inline", "commonscatinline", "commons-cat-inline",

    # Commons and category
    "Commons and category", "Commons+cat",
    "commons and category", "commons+cat"
]

HEADERS = {
    'User-Agent': 'AsteraBot/1.0 (https://simple.wikipedia.org/wiki/User:AsteraBot)'
}

def login_and_get_session(username, password):
    session = requests.Session()
    session.headers.update(HEADERS)

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
    login_result = r2.json()
    if login_result['login']['result'] != 'Success':
        raise Exception(f"Login failed: {login_result}")

    r3 = session.get(API_URL, params={
        'action': 'query',
        'meta': 'userinfo',
        'format': 'json'
    })
    print("Logged in as:", r3.json()['query']['userinfo']['name'])

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
    for _ in range(5):
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
    raise Exception("Failed to get non-redirect article after 5 tries.")

def has_commonscat(wikitext):
    wikicode = mwparserfromhell.parse(wikitext)
    templates = wikicode.filter_templates()
    return any(template.name.strip_code().strip() in BLOCKING_TEMPLATES for template in templates)

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
            wikidata_response = session.get("https://www.wikidata.org/w/api.php", params={
                'action': 'wbgetclaims',
                'entity': qid,
                'property': 'P373',
                'format': 'json'
            })
            claims = wikidata_response.json().get('claims', {})
            if 'P373' in claims:
                return claims['P373'][0]['mainsnak']['datavalue']['value']
    return None

def commons_category_exists(category_name):
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": f"Category:{category_name}",
        "format": "json"
    }
    response = requests.get(url, params=params, headers=HEADERS)
    pages = response.json().get("query", {}).get("pages", {})
    return not any(page_id == "-1" for page_id in pages)

def insert_commonscat(text, commonscat_value):
    commonscat_template = f"\n{{{{Commonscat|{commonscat_value}}}}}"

    if "==Other websites==" in text:
        parts = text.split("==Other websites==", 1)
        before = parts[0]
        after = parts[1]

        after_lines = after.splitlines()
        i = 0
        while i < len(after_lines) and (after_lines[i].strip() == '' or after_lines[i].strip().startswith("*")):
            i += 1

        section_body = '\n'.join(after_lines[:i]).rstrip()
        remainder = '\n'.join(after_lines[i:]).lstrip()

        new_other_websites = section_body + commonscat_template
        return before + "==Other websites==\n" + new_other_websites + "\n" + remainder

    else:
        lines = text.strip().splitlines()
        insert_index = len(lines)

        for i, line in enumerate(reversed(lines)):
            if line.strip().startswith("[[Category:") or line.strip().lower().startswith("{{defaultsort:"):
                insert_index = len(lines) - i - 1
                break

        new_lines = lines[:insert_index] + [commonscat_template] + lines[insert_index:]
        return '\n'.join(new_lines)

def add_commonscat_to_page(title, session):
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
        print(f"{title} already has a Commons-related template. Skipping.")
        return

    commonscat_value = fetch_commons_category_from_wikidata(title, session)
    if not commonscat_value:
        print(f"No Commons category found for {title}. Skipping.")
        return

    if not commons_category_exists(commonscat_value):
        print(f"Commons category 'Category:{commonscat_value}' does not exist. Skipping.")
        return

    new_text = insert_commonscat(text, commonscat_value)
    csrf_token = get_csrf_token(session)

    r = session.post(API_URL, data={
        'action': 'edit',
        'title': title,
        'text': new_text,
        'token': csrf_token,
        'format': 'json',
        'summary': 'Bot: Adding Commons category using P373 from Wikidata',
        'assert': 'user',
        'bot': True
    })

    result = r.json()
    print("Edit response:", result)
    if result.get('edit', {}).get('result') == 'Success':
        print(f"Successfully added {{Commonscat}} to {title}")
    else:
        print(f"Failed to edit {title}: {result}")

def run_bot():
    username = os.getenv('BOT_USERNAME')
    password = os.getenv('BOT_PASSWORD')

    if not username or not password:
        print("Missing BOT_USERNAME or BOT_PASSWORD in environment.")
        return

    session = login_and_get_session(username, password)

    for _ in range(15):
        try:
            article = fetch
