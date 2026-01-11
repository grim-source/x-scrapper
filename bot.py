#!/usr/bin/env python3
"""
X to Nostr Bot
Monitors an X (Twitter) account via Nitter and reposts to Nostr.
Designed to run via cron on Raspberry Pi 5.
"""

import json
import os
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

try:
    from nostr_sdk import Client, Keys, ClientSigner, Options, RelayOptions, EventBuilder
except ImportError:
    print("Error: nostr-sdk not installed. Run: pip3 install nostr-sdk")
    sys.exit(1)

import config


def load_state():
    """Load the last seen post ID from state.json"""
    state_file = "state.json"
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                return state.get("last_post_id", None)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read state file: {e}")
            return None
    return None


def save_state(post_id):
    """Save the last seen post ID to state.json"""
    state_file = "state.json"
    try:
        state = {
            "last_post_id": post_id,
            "last_updated": datetime.now().isoformat()
        }
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        print(f"Error: Could not write state file: {e}")
        sys.exit(1)


def scrape_nitter_post(username, nitter_url):
    """Scrape the latest post from Nitter for the given username"""
    try:
        # Construct Nitter URL
        profile_url = f"{nitter_url}/{username}"
        
        # Set headers to mimic a browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # Make request to Nitter
        response = requests.get(profile_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Try multiple selectors to find the first tweet
        # Different Nitter instances may use slightly different structures
        post_id = None
        post_text = None
        
        # Method 1: Try timeline-item with data-id attribute
        timeline_item = soup.find("div", class_="timeline-item")
        if timeline_item:
            post_id = timeline_item.get("data-id")
            tweet_content = timeline_item.find("div", class_="tweet-content")
            if tweet_content:
                # Remove unwanted elements
                for elem in tweet_content.find_all(["a", "span"], class_="tweet-link"):
                    elem.decompose()
                post_text = tweet_content.get_text(strip=True)
        
        # Method 2: Try finding first tweet in tweet-list
        if not post_id or not post_text:
            tweet_list = soup.find("div", class_="tweet-list") or soup.find("div", class_="timeline")
            if tweet_list:
                first_tweet = tweet_list.find("div", class_="tweet") or tweet_list.find("div", class_="timeline-item")
                if first_tweet:
                    if not post_id:
                        post_id = first_tweet.get("data-id") or first_tweet.get("data-item-id")
                    
                    if not post_text:
                        content_elem = first_tweet.find("div", class_="tweet-content") or first_tweet.find("div", class_="tweet-body")
                        if content_elem:
                            for elem in content_elem.find_all(["a", "span"], class_="tweet-link"):
                                elem.decompose()
                            post_text = content_elem.get_text(strip=True)
        
        # Method 3: Fallback - look for status link and extract ID
        if not post_id:
            status_links = soup.find_all("a", href=True)
            for link in status_links:
                href = link.get("href", "")
                if "/status/" in href:
                    # Extract post ID from URL like /username/status/1234567890
                    post_id = href.split("/status/")[-1].split("/")[0].split("?")[0]
                    if post_id and post_id.isdigit():
                        break
        
        # Method 4: Final fallback for text extraction
        if not post_text:
            # Try to find any tweet content div
            content_divs = soup.find_all("div", class_=lambda x: x and "tweet" in x.lower() and "content" in x.lower())
            if content_divs:
                content_elem = content_divs[0]
                for elem in content_elem.find_all(["a", "span"], class_="tweet-link"):
                    elem.decompose()
                post_text = content_elem.get_text(strip=True)
        
        if not post_id or not post_text:
            print("Error: Could not extract post ID or text from Nitter page")
            print(f"Debug: post_id={post_id}, post_text={'found' if post_text else 'not found'}")
            return None, None
        
        return post_id, post_text
    
    except requests.RequestException as e:
        print(f"Error: Failed to fetch from Nitter: {e}")
        return None, None
    except Exception as e:
        print(f"Error: Unexpected error scraping Nitter: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def format_nostr_note(username, post_text, post_id):
    """Format the post as a Nostr note"""
    x_url = f"https://x.com/{username}/status/{post_id}"
    
    note = f"""Quote from @{username} on X:

> {post_text}

Source:
{x_url}"""
    
    return note


def publish_to_nostr(note, private_key, relays):
    """Publish a note to Nostr"""
    try:
        # Create keys from private key
        keys = Keys.from_nsec(private_key)
        
        # Create client signer
        client_signer = ClientSigner.keys(keys)
        
        # Create client options
        opts = Options().wait_for_send(True)
        relay_opts = RelayOptions().ping(False)
        opts = opts.relay_options(relay_opts)
        
        # Initialize client
        client = Client.with_opts(client_signer, opts)
        
        # Add relays
        for relay_url in relays:
            try:
                client.add_relay(relay_url)
            except Exception as e:
                print(f"Warning: Could not add relay {relay_url}: {e}")
        
        # Connect to relays
        client.connect()
        
        # Build and send the event
        event_builder = EventBuilder.text_note(note, [])
        event_id = client.send_event_builder(event_builder)
        
        print(f"Published to Nostr: {event_id.to_hex()}")
        
        # Disconnect
        client.disconnect()
        
        return True
    
    except Exception as e:
        print(f"Error: Failed to publish to Nostr: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main bot function"""
    print(f"{datetime.now().isoformat()} - Starting bot check...")
    
    # Validate configuration
    if not config.X_USERNAME:
        print("Error: X_USERNAME not set in config.py")
        sys.exit(1)
    
    if config.NOSTR_PRIVATE_KEY.startswith("nsec..."):
        print("Error: Please set your Nostr private key in config.py")
        sys.exit(1)
    
    if not config.NOSTR_RELAYS:
        print("Error: No Nostr relays configured in config.py")
        sys.exit(1)
    
    # Load last seen post ID
    last_post_id = load_state()
    print(f"Last seen post ID: {last_post_id if last_post_id else 'None (first run)'}")
    
    # Scrape latest post from Nitter
    print(f"Scraping latest post from @{config.X_USERNAME} via {config.NITTER_BASE_URL}...")
    post_id, post_text = scrape_nitter_post(config.X_USERNAME, config.NITTER_BASE_URL)
    
    if not post_id or not post_text:
        print("Error: Failed to scrape post from Nitter")
        sys.exit(1)
    
    print(f"Found post ID: {post_id}")
    print(f"Post text preview: {post_text[:100]}...")
    
    # Check if this is a new post
    if last_post_id and post_id == last_post_id:
        print("No new post detected. Exiting.")
        sys.exit(0)
    
    # Format and publish to Nostr
    print("New post detected! Publishing to Nostr...")
    note = format_nostr_note(config.X_USERNAME, post_text, post_id)
    
    success = publish_to_nostr(note, config.NOSTR_PRIVATE_KEY, config.NOSTR_RELAYS)
    
    if success:
        # Save new post ID
        save_state(post_id)
        print("Successfully published and saved state.")
    else:
        print("Failed to publish to Nostr. State not updated.")
        sys.exit(1)
    
    print(f"{datetime.now().isoformat()} - Bot check completed.")


if __name__ == "__main__":
    main()
