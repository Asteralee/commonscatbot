import os
import re
import requests
import mwparserfromhell
import time

API_URL = "https://simple.wikipedia.org/w/api.php"

HEADERS = {
    'User-Agent': 'AsteraBot/1.0 (https://simple.wikipedia.org/wiki/User:AsteraBot)'
}

BLOCKING_TEMPLATES = [
    "Commonscat", "Commons cat", "Commonscat2", "Ccat", "Wikimedia commons cat",
    "Category commons", "C cat", "Commonscategory", "Commonsimages cat",
    "Container cat", "Commons Category", "Commons category", "commonscat",
    "commons cat", "commonscat2", "ccat", "wikimedia commons cat",
    "category commons", "c cat", "commonscategory", "commonsimages cat",
    "container cat", "commons category", "Commons category multi", "Commonscats",
    "Commons cat multi", "Commonscat multi", "commons category multi", "commonscats",
    "commons cat multi", "commonscat multi", "Commons", "Wikimedia Commons",
    "commons", "wikimedia commons", "Commons category-inline", "Commonscat-inline",
    "Commons cat-inline", "Commons category inline", "Commonscat inline",
    "Commonscatinline", "Commons-cat-inline", "commons category-inline",
    "commonscat-inline", "commons cat-inline", "commons category inline",
    "commonscat inline", "commonscatinline", "commons-cat-inline",
    "Commons and category", "Commons+cat", "commons and category", "commons+cat",
    "C18 year in topic"
]

STUB_TEMPLATES = [
    "Multistub", "Stub", "Acid-base disorders", "Actor-stub", "Asia-stub",
    "Biography-stub", "Biology-stub", "Canada-stub", "Chem-stub",
    "Consequences of external causes", "Disorders of the breast", "Europe-stub",
    "Expand list", "Food-stub", "France-geo-stub", "Geo-stub", "History-stub",
    "Infobox medical intervention", "Japan-sports-bio-stub", "Japan-stub",
    "Lit-stub", "Math-stub", "Med-stub", "Military-stub", "Movie-stub",
    "Music-stub", "North-America-stub", "Performing-arts-stub", "Physics-stub",
    "Politics-stub", "Religion-stub", "Sci-stub", "Shock types", "Sport-stub",
    "Sports-biography-stub", "Switzerland-stub", "Tech-stub", "Transport-stub",
    "Tv-stub", "UK-stub", "US-actor-stub", "US-biography-stub", "US-geo-stub",
    "US-sports-bio-stub", "US-stub", "Video-game-stub", "Weather-stub"
]

AUTHORITY_CONTROL_TEMPLATES = [
    "Authority control",
    "Authoritycontrol",
    "Authority Control",
    "Normdaten"
]

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

    r3 = session.get(API_URL, params={
        'action': 'query',
        'meta': 'userinfo',
        'format': 'json'
    })
    
    logged_in_user = r3.json()['query']['userinfo']['name']
    print(f"Logged in as {logged_in_user}")
    
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
        if name in [t.lower() for t in BLOCKING_TEMPLATES]:
            return True
        if name == "sister project links":
            if tmpl.has("commonscat") or tmpl.has("c"):
                return True
    return False

def has_authority_control(wikitext):
    code = mwparserfromhell.parse(wikitext)
    for tmpl in code.filter_templates():
        name = tmpl.name.strip_code().strip()
        if any(name.lower() == tmpl_name.lower() for tmpl_name in AUTHORITY_CONTROL_TEMPLATES):
            return True
    return False

def extract_template_name(line):
    match = re.match(r"^\{\{\s*([^\|\}]+)", line)
    if match:
        return match.group(1).strip()
    return None

def is_stub_template(line):
    tmpl_name = extract_template_name(line)
    return tmpl_name and tmpl_name.strip().lower().endswith("-stub")

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

    for idx, line in enumerate(lines):
        if re.match(r"^==+\s*(Other websites|External links)\s*==+", line, re.IGNORECASE):
            insert_index = idx + 1
            if insert_index < len(lines) and lines[insert_index].strip().startswith('{{'):
                lines[insert_index] = f"{commonscat_template} {lines[insert_index].strip()}"
            else:
                lines.insert(insert_index, commonscat_template)
            return '\n'.join(lines)

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
        print(f"Page '{title}' does not exist.")
        return

    wikitext = page['revisions'][0]['slots']['main']['content']
    if has_commonscat(wikitext):
        print(f"'{title}' already has a Commons-related template.")
        return

    if has_authority_control(wikitext):
        print(f"'{title}' has authority control template; skipping.")
        return

    commonscat_value = fetch_commons_category_from_wikidata(title, session)
    if not commonscat_value:
        print(f"No Commons category found for '{title}'.")
        return

    new_text = insert_commonscat(wikitext, commonscat_value, session)
    if new_text == wikitext:
        print(f"Nothing changed for '{title}'.")
        return

    token = get_csrf_token(session)
    r2 = session.post(API_URL, data={
        'action': 'edit',
        'title': title,
        'text': new_text,
        'token': token,
        'summary': 'Bot: Adding Commons category using P373 from Wikidata',
        'format': 'json',
        'assert': 'user',
        'bot': True
    })

    result = r2.json()
    if result.get('edit', {}).get('result') == 'Success':
        print(f"Successfully edited: '{title}'")
    else:
        print(f"Failed to edit '{title}': {result}")

def run_bot():
    username = os.getenv("BOT_USERNAME")
    password = os.getenv("BOT_PASSWORD")

    if not username or not password:
        print("Missing BOT_USERNAME or BOT_PASSWORD.")
        return

    session = login_and_get_session(username, password)

    for _ in range(10):
        try:
            title = fetch_random_article(session)
            print(f"\nProcessing: '{title}'")
            add_commonscat_to_page(title, session)
            time.sleep(3)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    run_bot()
