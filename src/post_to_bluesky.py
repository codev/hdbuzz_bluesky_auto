import os
import feedparser
import time
from atproto import Client
from datetime import datetime, timezone
import json
import hashlib
import google.generativeai as genai
import re

def setup_gemini():
    genai.configure(api_key=os.environ['GEMINI_API_KEY'])
    model = genai.GenerativeModel('gemini-pro')
    return model

def load_posted_entries():
    try:
        with open('posted_entries.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_posted_entries(posted):
    with open('posted_entries.json', 'w') as f:
        json.dump(posted, f)

def generate_hashtags_with_gemini(model, title, description):
    prompt = f"""
    Generate 5 relevant hashtags for a social media post with the following content:
    Title: {title}
    Description: {description}

    Rules for hashtags:
    1. No spaces in hashtags
    2. Use camelCase for multiple words
    3. Keep them relevant to the content
    4. No special characters except numbers
    5. Return only the hashtags, one per line, starting with #
    """

    try:
        response = model.generate_content(prompt)
        hashtags = response.text.strip().split('\n')

        # Clean and validate hashtags
        cleaned_hashtags = []
        for tag in hashtags:
            # Remove any extra # symbols and spaces
            tag = tag.strip().replace(' ', '')
            if not tag.startswith('#'):
                tag = f"#{tag}"
            # Validate hashtag format
            if re.match(r'^#[a-zA-Z0-9]+$', tag):
                cleaned_hashtags.append(tag)

        # Ensure we have at least some hashtags, even if AI fails
        if not cleaned_hashtags:
            # Fallback to basic hashtag generation
            words = title.split()[:3]
            cleaned_hashtags = [f"#{word.lower()}" for word in words if word.isalnum()]

        return cleaned_hashtags[:5]  # Return maximum 5 hashtags
    except Exception as e:
        print(f"Error generating hashtags with Gemini: {str(e)}")
        # Fallback to basic hashtag generation
        words = title.split()[:3]
        return [f"#{word.lower()}" for word in words if word.isalnum()]

def create_bluesky_post(entry, hashtags):
    title = entry.get('title', '')
    link = entry.get('link', '')

    # Create post content with title, link, and hashtags
    content = f"{title}\n\n{link}\n\n{' '.join(hashtags)}"

    # Ensure content doesn't exceed Bluesky's character limit (300)
    if len(content) > 300:
        # Truncate title if necessary
        available_space = 300 - len(link) - len(' '.join(hashtags)) - 4  # 4 for newlines
        title = title[:available_space] + '...'
        content = f"{title}\n\n{link}\n\n{' '.join(hashtags)}"

    return content

def main():
    try:
        # Initialize Gemini
        #model = setup_gemini()

        # Initialize Bluesky client
        client = Client()
        client.login(os.environ['BLUESKY_HANDLE'], os.environ['BLUESKY_PASSWORD'])

        # RSS feed URL - replace with your desired RSS feed
        rss_url = "https://en.hdbuzz.net/feed"

        # Load previously posted entries
        posted_entries = load_posted_entries()

        # Parse RSS feed
        feed = feedparser.parse(rss_url)

        for entry in feed.entries:
            # Create unique identifier for entry
            entry_id = hashlib.md5(entry.link.encode()).hexdigest()

            # Skip if already posted
            if entry_id in posted_entries:
                continue

            # Generate hashtags using Gemini
            hashtags = ''

            # Create post content
            content = create_bluesky_post(entry, hashtags)

            try:
                # Post to Bluesky
                client.send_post(text=content)

                # Save entry as posted
                posted_entries[entry_id] = {
                    'title': entry.title,
                    'date_posted': datetime.now(timezone.utc).isoformat(),
                    'hashtags': hashtags
                }

                print(f"Successfully posted: {entry.title}")
                print(f"Generated hashtags: {' '.join(hashtags)}")

                # Wait between posts to avoid rate limiting
                time.sleep(2)

            except Exception as e:
                print(f"Error posting {entry.title}: {str(e)}")

        # Save updated posted entries
        save_posted_entries(posted_entries)

    except Exception as e:
        print(f"Fatal error: {str(e)}")
        raise

if __name__ == "__main__":
    main()

# Created/Modified files during execution:
print("posted_entries.json")
