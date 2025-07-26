import requests
import random
import os

# Set the API endpoint for SimpleWiki
API_URL = "https://simple.wikipedia.org/w/api.php"

# Function to add {{commonscat}} to a page if not already added
def add_commonscat_to_page(page_title):
    params = {
        'action': 'query',
        'titles': page_title,
        'prop': 'revisions|info',
        'rvprop': 'content',
        'inprop': 'url',  # Get the redirect URL if it's a redirect
        'format': 'json',
    }

    response = requests.get(API_URL, params=params)
    data = response.json()

    pages = data['query']['pages']
    page = next(iter(pages.values()))

    # Check if the page is a redirect
    if 'redirect' in page:
        print(f"{page_title} is a redirect. Skipping.")
        return

    content = page.get('revisions', [{}])[0].get('*', '')

    # Debug: Print the content of the article
    print(f"Content of {page_title}:\n{content[:500]}")  # Print first 500 chars for inspection

    # Check if {{commonscat}} is already in the article
    if '{{commonscat}}' in content:
        print(f"Commonscat already exists on {page_title}. Skipping.")
        return

    # Check if there is a Commons category (either {{commonscat}} or [[Category:Commons category]])
    commons_category_found = False

    # Look for {{commonscat}} template
    if '{{commonscat}}' in content:
        commons_category_found = True
    # Look for [[Category:Commons category]] links
    elif '[[Category:' in content and 'Commons category' in content:
        commons_category_found = True

    if commons_category_found:
        # Add {{commonscat}} at the end of the page (before categories if present)
        if '[[Category:' in content:
            content = content.split('[[Category:')[0] + '\n{{commonscat}}' + '\n[[Category:' + content.split('[[Category:')[1]
        else:
            content = content + '\n{{commonscat}}'
        # Proceed to edit the page with commonscat template
        edit_params = {
            'action': 'edit',
            'title': page_title,
            'text': content,
            'token': get_edit_token(),
            'summary': 'Bot: Added {{commonscat}} to article',  # Add the edit summary
            'format': 'json'
        }

        edit_response = requests.post(API_URL, data=edit_params)
        edit_data = edit_response.json()

        if 'error' in edit_data:
            print(f"Error editing {page_title}: {edit_data['error']['info']}")
        else:
            print(f"Successfully added {{commonscat}} to {page_title}.")
    else:
        print(f"No Commons category found for {page_title}. Skipping.")

# Function to get the edit token for authentication
def get_edit_token():
    session = requests.Session()

    # Step 1: Login to get a session (and the edit token)
    login_params = {
        'action': 'login',
        'lgname': os.getenv('BOT_USERNAME'),  # Bot username from GitHub secrets
        'lgpassword': os.getenv('BOT_PASSWORD'),  # Bot password from GitHub secrets
        'format': 'json'
    }

    # Perform the login
    login_response = session.post(API_URL, data=login_params)

    # Try to parse the JSON response
    login_data = login_response.json()

    # Check if login was successful
    if 'error' in login_data:
        print(f"Login failed: {login_data['error']['info']}")
        return None

    # Step 2: Get the CSRF token by making a request with the session
    token_params = {
        'action': 'query',
        'meta': 'tokens',
        'format': 'json'
    }
    token_response = session.get(API_URL, params=token_params)
    token_data = token_response.json()

    return token_data['query']['tokens']['csrftoken']

# Function to get a list of articles from Special:AllPages
def get_random_articles():
    params = {
        'action': 'query',
        'list': 'allpages',
        'aplimit': '500',  # You can adjust this number for the size of the list
        'format': 'json'
    }

    response = requests.get(API_URL, params=params)
    data = response.json()

    # Extract all article titles
    articles = [item['title'] for item in data['query']['allpages']]

    # Randomly select 3 to 10 articles from the list
    selected_articles = random.sample(articles, random.randint(3, 10))
    return selected_articles

# Main function to run the bot
def run_bot():
    articles = get_random_articles()
    for article in articles:
        add_commonscat_to_page(article)

# Run the bot
run_bot()
