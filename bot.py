import os
import re
import requests
import mwparserfromhell
import random
import time

API_URL = "https://simple.wikipedia.org/w/api.php"

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

    if r2.json()['login']['result'] != 'Success':
        raise Exception("Login failed!")

    print("Logged in as:", username)
    return session

def get_csrf_token(session):
    r = session.get(API_URL, params={
        'action': 'query',
        'meta': 'tokens',
        'format': 'json'
    })
    return r.json()['query']['tokens']['csrftoken']

def is_redirect(session, title):
    r = session.get(API_URL, params={
        'action': 'query',
        'titles': title,
        'redirects': False,
        'format': 'json'
    })
    return any('redirect' in p for p in r.json()['query']['pages'].values())

def fetch_random_article(session):
    for _ in range(5):
        r = session.get(API_URL, params={
            'action': 'query',
            'list': 'random',
            'rnnamespace': 0,
            'rnlimit': 1,
            'format': 'json'
        })
        title = r.json()['query']['random'][0]['title']
        if not is_redirect(session, title):
            return title
    raise Exception("Could not find non-redirect article")

def has_commonscat(wikitext):
    code = mwparserfromhell.parse(wikitext)
    for tmpl in code.filter_templates():
        name = tmpl.name.strip_code().strip().lower()
        if "commonscat" in name or name == "sister project links":
            if name != "sister project links" or tmpl.has("commonscat") or tmpl.has("c"):
                return True
    return False

def extract_template_name(line):
    match = re.match(r"^\{\{\s*([^\|\}]+)", line)
    if match:
        return match.group(1).strip()
    return None

def is_stub_template(line):
    tmpl_name = extract_template_name(line)
    return tmpl_name and tmpl_name.lower().endswith("-stub")

def is_navbox_template(session, template_name):
    title = f"Template:{template_name}"
    r = session.get(API_URL, params={
        'action': 'query',
        'prop': 'revisions',
        'titles': title,
        'rvslots': 'main',
        'rvprop': 'content',
        'formatversion': 2,
        'format': 'json'
    })
    pages = r.json()['query']['pages']
    for page in pages:
        content = page.get('revisions', [{}])[0].get('slots', {}).get('main', {}).get('content', '')
        if '{{navbox' in content.lower():
            return True
    return False

def insert_commonscat(text, commonscat_value, session):
    commonscat_template = f"{{{{Commonscat|{commonscat_value}}}}}"
    lines = text.splitlines()
    insert_index = len(lines)

    # If "Other websites" or "External links" section is found
    for idx, line in enumerate(lines):
        if re.match(r"^==+\s*(Other websites|External links)\s*==+", line, re.IGNORECASE):
            insert_index = idx + 1
            if insert_index < len(lines) and lines[insert_index].strip().startswith('{{'):
                lines[insert_index] = f"{commonscat_template} {lines[insert_index].strip()}"
            else:
                lines.insert(insert_index, commonscat_template)
            return '\n'.join(lines)

    # Search from bottom for stub or navbox templates
    for idx in reversed(range(len(lines))):
        line = lines[idx].strip()
        if not line:
            continue
        if is_stub_template(line):
            insert_index = idx
            break
        tmpl_name = extract_template_name(line)
        if tmpl_name and is_navbox_template(session, tmpl_name):
            insert_index = idx
            break

    lines.insert(insert_index, '')
    lines.insert(insert_index, commonscat_template)
    return '\n'.join(lines)

def fetch_commons_category_from_wikidata(title, session):
    r = session.get(API_URL, params={
        'action': 'query',
        'prop': 'pageprops',
        'titles': title,
        'format': 'json'
    })
    pages = r.json()['query']['pages']
    for page in pages.values():
        qid = page.get('pageprops', {}).get('wikibase_item')
        if qid:
            r2 = session.get("https://www.wikidata.org/w/api.php", params={
                'action': 'wbgetclaims',
                'entity': qid,
                'property': 'P373',
                'format': 'json'
            })
            claims = r2.json().get('claims', {})
            if 'P373' in claims:
                return claims['P373'][0]['mainsnak']['datavalue']['value']
    return None

def add_commonscat_to_page(title, session):
    r = session.get(API_URL, params={
        'action': 'query',
        'prop': 'revisions',
        'titles': title,
        'rvslots': 'main',
        'rvprop': 'content',
        'formatversion': 2,
        'format': 'json'
    })

    page = r.json()['query']['pages'][0]
    if 'missing' in page:
        print(f"{title} does not exist.")
        return

    wikitext = page['revisions'][0]['slots']['main']['content']
    if has_commonscat(wikitext):
        print(f"{title} already has Commonscat.")
        return

    commonscat_value = fetch_commons_category_from_wikidata(title, session)
    if not commonscat_value:
        print(f"No Commonscat in Wikidata for {title}.")
        return

    new_text = insert_commonscat(wikitext, commonscat_value, session)
    csrf_token = get_csrf_token(session)

    r2 = session.post(API_URL, data={
        'action': 'edit',
        'title': title,
        'text': new_text,
        'token': csrf_token,
        'format': 'json',
        'summary': 'Bot: Add Commonscat (using P373 from Wikidata)',
        'assert': 'user',
        'bot': True
    })
    print("Edit:", r2.json().get('edit', {}))

def run_bot():
    user = os.getenv('BOT_USERNAME')
    pw = os.getenv('BOT_PASSWORD')
    if not user or not pw:
        print("Missing credentials.")
        return
    session = login_and_get_session(user, pw)

    for _ in range(15):
        try:
            title = fetch_random_article(session)
            print(f"Now editing: {title}")
            add_commonscat_to_page(title, session)
            time.sleep(3)
        except Exception as e:
            print(f"Error occurred: {e}")
            time.sleep(2)

if __name__ == "__main__":
    run_bot()
