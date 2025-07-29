# commonscatbot

This Python bot automatically adds the "Commonscat" template to articles on Simple Wikipedia, based on information sourced from Wikidata.

## Features

- **Random Article Fetching**: The bot fetches 15 random articles from Simple Wikipedia.
- **Commons Category Lookup**: It checks Wikidata (P373) for the relevant Commons category associated with the article.
- **Template Insertion**: Automatically adds the "Commonscat" template to the article if it's missing.
- **Redirection Check**: Ensures the bot only edits non-redirect pages.
- **Error Handling**: The bot includes retries and error handling for potential failures during execution.

## How It Works

1. **Login and Session Handling**: The bot logs into Simple Wikipedia using the provided bot username and password and keeps an active session for API interactions.
2. **Article Selection**: The bot fetches a random article from Simple Wikipedia and ensures it isn't a redirect page.
3. **Commons Category Lookup**: The bot checks the article's Wikidata entry to find the Commons category (P373).
4. **Template Addition**: If a Commons category is found, the bot adds the `Commonscat` template to the article, either under the "Other websites" section or near the metadata.
5. **Repeat**: The bot continues this process 15 times.
