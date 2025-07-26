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
        'prop': 'revisions',
        'rvprop': 'content',
        'format': 'json',
    }

    response = requests.get(API_URL, params=params)
    data = response.json()

    pages = data['query']['pages']
    page = next(iter(pages.values()))
    content = page.get('revisions', [{}])[0].get('*', '')

    # Check if {{commonscat}} is already in the article
    if '{{commonscat}}' in content:
        print(f"Commonscat already exists on {page_title}. Skipping.")
        return

    # Add {{commonscat}} at the end of the page (before categories if present)
    if '[[Category:' in content:
        content = content.split('[[Category:')[0] + '\n{{commonscat}}' + '\n[[Category:' + content.split('[[Category:')[1]
    else:
        content = content + '\n{{commonscat}}'

    # Edit the page to add {{commonscat}} at the end.
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

# Function to get the edit token for authentication
def get_edit_token():
    # Step 1: Login to get a token 
    login_params = {
        'action': 'login',
        'lgname': os.getenv('BOT_USERNAME'),  
        'lgpassword': os.getenv('BOT_PASSWORD'),  
        'format': 'json'
    }
    login_response = requests.post(API_URL, data=login_params)
    login_data = login_response.json()

    # Check if login was successful
    if 'error' in login_data:
        print(f"Login failed: {login_data['error']['info']}")
        return None

    # Step 2: Retrieve the CSRF token
    token_params = {
        'action': 'tokens',
        'format': 'json'
    }
    token_response = requests.get(API_URL, params=token_params)
    token_data = token_response.json()

    # Debug: Print token response to verify
    print(f"Token Response: {token_data}")

    # Check if 'tokens' key exists in the response
    if 'tokens' not in token_data:
        print("Error: No token found in the response")
        return None

    return token_data['tokens']['csrftoken']

# Function to get a list of articles from Special:AllPages
def get_random_articles():
    params = {
        'action': 'query',
        'list': 'allpages',
        'aplimit': '500',  # Size of the list
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
