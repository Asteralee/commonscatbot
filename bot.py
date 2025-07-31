import os
import re
import requests
import mwparserfromhell
import random
import time

API_URL = "https://simple.wikipedia.org/w/api.php"

BLOCKING_TEMPLATES = [
    "Commonscat", "Commons cat", "Commonscat2", "Ccat", "Wikimedia commons cat",
    "Category commons", "C cat", "Commonscategory", "Commonsimages cat",
    "Container cat", "Commons Category", "Commons category", "commonscat",
    "commons cat", "commonscat2", "ccat", "wikimedia commons cat",
    "category commons", "c cat", "commonscategory", "commonsimages cat",
    "container cat", "commons category", "commons category",
    "Commons category multi", "Commonscats", "Commons cat multi", "Commonscat multi",
    "commons category multi", "commonscats", "commons cat multi", "commonscat multi",
    "Commons", "Wikimedia Commons",
    "commons", "wikimedia commons",
    "Commons category-inline", "Commonscat-inline", "Commons cat-inline",
    "Commons category inline", "Commonscat inline", "Commonscatinline", "Commons-cat-inline",
    "commons category-inline", "commonscat-inline", "commons cat-inline",
    "commons category inline", "commonscat inline", "commonscatinline", "commons-cat-inline",
    "Commons and category", "Commons+cat",
    "commons and category", "commons+cat",
    "C18 year in topic", 
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
    "US-sports-bio-stub", "US-stub", "Video-game-stub", "Weather-stub",
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
    for template in templates:
        name = template.name.strip_code().strip().lower()
        if name in [t.lower() for t in BLOCKING_TEMPLATES]:
            return True
        if name == "sister project links":
            if template.has("commonscat") or template.has("c"):
                return True
    return False

def modify_sister_project_links(wikitext, commonscat_value):
    wikicode = mwparserfromhell.parse(wikitext)
    modified = False

    for template in wikicode.filter_templates():
        name = template.name.strip_code().strip().lower()
        if name == "sister project links":
            if not template.has("commonscat"):
                template.add("commonscat", "yes")
                modified = True
            if not template.has("c"):
                template.add("c", commonscat_value)
                modified = True
            break

    return str(wikicode) if modified else None

def extract_template_name(line):
    """Extract the template name from a line like {{Foo|bar}} or {{Foo}}."""
    match = re.match(r"^\{\{\s*([^\|\}]+)", line)
    if match:
        return match.group(1).strip()
    return None

def is_navbox_template(session, template_name):
    """Check if a given template is a navbox by fetching its wikitext and looking for '{{Navbox'."""
    title = f"Template:{template_name}"

    response = session.get(API_URL, params={
        'action': 'query',
        'prop': 'revisions',
        'titles': title,
        'rvslots': 'main',
        'rvprop': 'content',
        'formatversion': 2,
        'format': 'json'
    })

    pages = response.json().get('query', {}).get('pages', [])
    if not pages or 'revisions' not in pages[0]:
        return False

    content = pages[0]['revisions'][0]['slots']['main']['content'].lower()
    return ('{{navbox' in content or
            '{{navbox with columns' in content or
            '{{navbox subgroup' in content)

def insert_commonscat(text, commonscat_value, session):
    commonscat_template = f"{{{{Commonscat|{commonscat_value}}}}}"

    lines = text.splitlines()

    # Check for 'Other websites' or 'External links' section, insert Commonscat after the header line without extra blank line
    for idx, line in enumerate(lines):
        if re.match(r"^==+\s*(Other websites|External links)\s*==+", line, re.IGNORECASE):
            insert_index = idx + 1
            # If next line is a template, prepend commonscat to it (no empty line)
            if insert_index < len(lines) and lines[insert_index].strip().startswith('{{'):
                lines[insert_index] = f"{commonscat_template} {lines[insert_index].strip()}"
            else:
                lines.insert(insert_index, commonscat_template)
            return '\n'.join(lines)

    # No 'Other websites' or 'External links' section found
    # Insert above stub templates or navboxes with an empty line before Commonscat for separation
    insert_index = len(lines)

    for idx in reversed(range(len(lines))):
        line = lines[idx].strip()
        if not line:
            continue

        # Check if line is a stub template
        for stub in STUB_TEMPLATES:
            if line.startswith("{{" + stub):
                insert_index = idx
                break

        # Check if line is a navbox template
        if line.startswith("{{") and "}}" in line:
            tmpl_name = extract_template_name(line)
            if tmpl_name and is_navbox_template(session, tmpl_name):
                insert_index = idx
                break

        if insert_index < len(lines):
            break

    # Insert empty line before commonscat template for spacing
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
    page_data = r.json()['query']['pages']
    for page in page_data.values():
        page_props = page.get('pageprops', {})
        qid = page_props.get('wikibase_item')
        if qid:
            w = session.get("https://www.wikidata.org/w/api.php", params={
                'action': 'wbgetclaims',
                'entity': qid,
                'property': 'P373',
                'format': 'json'
            })
            claims = w.json().get('claims', {})
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
        print(f"{title} doesn’t exist.")
        return

    wikitext = page['revisions'][0]['slots']['main']['content']
    if has_commonscat(wikitext):
        print(f"{title} already has Commonscat.")
        return

    commonscat_value = fetch_commons_category_from_wikidata(title, session)
    if not commonscat_value:
        print(f"No Commonscat in Wikidata for {title}.")
        return

    new_wikitext = insert_commonscat(wikitext, commonscat_value, session)

    csrf_token = get_csrf_token(session)

    r2 = session.post(API_URL, data={
        'action': 'edit',
        'title': title,
        'text': new_wikitext,
        'token': csrf_token,
        'format': 'json',
        'summary': 'Bot: Adding Commons category using P373 from Wikidata',
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
