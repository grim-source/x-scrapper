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

try:
    import config
except ImportError as e:
    print(f"Error: Could not import config.py: {e}")
    print("Make sure config.py exists and is valid Python syntax.")
    sys.exit(1)


def load_state():
    """Load the state for all accounts from state.json"""
    state_file = "state.json"
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                # Handle old format (single account) for backward compatibility
                if "last_post_id" in state:
                    # Old format, convert to new format
                    return {"accounts": {}}
                return state
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read state file: {e}")
            return {"accounts": {}}
    return {"accounts": {}}


def get_last_post_id(state, username):
    """Get the last seen post ID for a specific account"""
    return state.get("accounts", {}).get(username, {}).get("last_post_id", None)


def save_state_for_account(state, username, post_id):
    """Save the last seen post ID for a specific account to state.json"""
    state_file = "state.json"
    try:
        if "accounts" not in state:
            state["accounts"] = {}
        
        if username not in state["accounts"]:
            state["accounts"][username] = {}
        
        state["accounts"][username]["last_post_id"] = post_id
        state["accounts"][username]["last_updated"] = datetime.now().isoformat()
        state["last_updated"] = datetime.now().isoformat()
        
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
        return True
    except (IOError, OSError, PermissionError) as e:
        print(f"Error: Could not write state file: {e}")
        print("Warning: State not saved. The bot will continue, but may repost on next run.")
        return False
    except Exception as e:
        print(f"Error: Unexpected error saving state: {e}")
        return False


def scrape_nitter_post(username, nitter_url):
    """Scrape the latest post from Nitter for the given username"""
    try:
        # Validate inputs
        if not username or not username.strip():
            print("Error: Invalid username (empty)")
            return None, None
        
        if not nitter_url or not nitter_url.strip():
            print("Error: Invalid Nitter URL (empty)")
            return None, None
        
        # Clean username (remove @ if present, strip whitespace)
        username = username.strip().lstrip('@')
        
        # Construct Nitter URL
        profile_url = f"{nitter_url.rstrip('/')}/{username}"
        
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
    
    except requests.Timeout as e:
        print(f"Error: Timeout fetching from Nitter (URL: {profile_url}): {e}")
        return None, None
    except requests.ConnectionError as e:
        print(f"Error: Connection error fetching from Nitter (URL: {profile_url}): {e}")
        return None, None
    except requests.HTTPError as e:
        if e.response is not None:
            status_code = e.response.status_code
            if status_code == 404:
                print(f"Error: User @{username} not found on Nitter")
            elif status_code == 429:
                print(f"Error: Rate limited by Nitter (429 Too Many Requests)")
            elif status_code >= 500:
                print(f"Error: Nitter server error ({status_code})")
            else:
                print(f"Error: HTTP error {status_code} from Nitter: {e}")
        else:
            print(f"Error: HTTP error from Nitter: {e}")
        return None, None
    except requests.RequestException as e:
        print(f"Error: Request failed fetching from Nitter: {e}")
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
    client = None
    try:
        # Validate note length (Nostr has limits, typically ~32KB for text notes)
        if len(note) > 32000:
            print(f"Error: Note too long ({len(note)} chars). Maximum is ~32000 characters.")
            return False
        
        # Validate private key format
        if not private_key or not private_key.startswith("nsec1"):
            print("Error: Invalid Nostr private key format. Should start with 'nsec1'")
            return False
        
        # Validate relays list
        if not relays or len(relays) == 0:
            print("Error: No relays configured")
            return False
        
        # Create keys from private key
        try:
            keys = Keys.from_nsec(private_key)
        except Exception as e:
            print(f"Error: Invalid Nostr private key: {e}")
            return False
        
        # Create client signer
        client_signer = ClientSigner.keys(keys)
        
        # Create client options
        opts = Options().wait_for_send(True)
        relay_opts = RelayOptions().ping(False)
        opts = opts.relay_options(relay_opts)
        
        # Initialize client
        client = Client.with_opts(client_signer, opts)
        
        # Add relays
        added_relays = 0
        for relay_url in relays:
            if not relay_url or not relay_url.startswith(("ws://", "wss://")):
                print(f"Warning: Invalid relay URL format: {relay_url}")
                continue
            try:
                client.add_relay(relay_url)
                added_relays += 1
            except Exception as e:
                print(f"Warning: Could not add relay {relay_url}: {e}")
        
        if added_relays == 0:
            print("Error: No relays were successfully added")
            return False
        
        # Connect to relays
        try:
            client.connect()
        except Exception as e:
            print(f"Error: Failed to connect to relays: {e}")
            return False
        
        # Build and send the event
        try:
            event_builder = EventBuilder.text_note(note, [])
            event_id = client.send_event_builder(event_builder)
            print(f"Published to Nostr: {event_id.to_hex()}")
        except Exception as e:
            print(f"Error: Failed to build or send event: {e}")
            return False
        
        return True
    
    except Exception as e:
        print(f"Error: Failed to publish to Nostr: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Ensure client is disconnected even if an error occurred
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                pass  # Ignore errors during cleanup


def process_account(username, state, nitter_url, nostr_key, relays):
    """Process a single X account - check for new posts and publish if found"""
    print(f"\n{'='*60}")
    print(f"Processing account: @{username}")
    print(f"{'='*60}")
    
    # Get last seen post ID for this account
    last_post_id = get_last_post_id(state, username)
    print(f"Last seen post ID: {last_post_id if last_post_id else 'None (first run)'}")
    
    # Scrape latest post from Nitter
    print(f"Scraping latest post from @{username} via {nitter_url}...")
    post_id, post_text = scrape_nitter_post(username, nitter_url)
    
    if not post_id or not post_text:
        print(f"Error: Failed to scrape post from Nitter for @{username}")
        return False
    
    print(f"Found post ID: {post_id}")
    print(f"Post text preview: {post_text[:100]}...")
    
    # Check if this is a new post
    if last_post_id and post_id == last_post_id:
        print(f"No new post detected for @{username}.")
        return True
    
    # Format and publish to Nostr
    print(f"New post detected for @{username}! Publishing to Nostr...")
    note = format_nostr_note(username, post_text, post_id)
    
    success = publish_to_nostr(note, nostr_key, relays)
    
    if success:
        # Save new post ID for this account
        state_saved = save_state_for_account(state, username, post_id)
        if state_saved:
            print(f"Successfully published and saved state for @{username}.")
        else:
            print(f"Warning: Published to Nostr for @{username} but state save failed.")
        return True
    else:
        print(f"Failed to publish to Nostr for @{username}. State not updated.")
        return False


def main():
    """Main bot function"""
    print(f"{datetime.now().isoformat()} - Starting bot check...")
    
    # Validate configuration
    # Support both old X_USERNAME and new X_ACCOUNTS format for backward compatibility
    if hasattr(config, 'X_ACCOUNTS'):
        x_accounts = config.X_ACCOUNTS
    elif hasattr(config, 'X_USERNAME'):
        # Old format - convert single account to list
        x_accounts = [config.X_USERNAME]
    else:
        print("Error: X_ACCOUNTS or X_USERNAME not set in config.py")
        sys.exit(1)
    
    if not x_accounts or len(x_accounts) == 0:
        print("Error: No X accounts configured in config.py")
        sys.exit(1)
    
    if config.NOSTR_PRIVATE_KEY.startswith("nsec..."):
        print("Error: Please set your Nostr private key in config.py")
        sys.exit(1)
    
    if not config.NOSTR_RELAYS:
        print("Error: No Nostr relays configured in config.py")
        sys.exit(1)
    
    # Load state for all accounts
    state = load_state()
    
    # Process each account
    success_count = 0
    error_count = 0
    
    for username in x_accounts:
        username = username.strip()  # Remove any whitespace
        if not username:
            continue
        
        try:
            result = process_account(
                username,
                state,
                config.NITTER_BASE_URL,
                config.NOSTR_PRIVATE_KEY,
                config.NOSTR_RELAYS
            )
            if result:
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            print(f"Error processing @{username}: {e}")
            import traceback
            traceback.print_exc()
            error_count += 1
    
    print(f"\n{'='*60}")
    print(f"Bot check completed: {success_count} accounts processed successfully, {error_count} errors")
    print(f"{datetime.now().isoformat()} - Bot check completed.")
    
    # Exit with error code if any accounts failed
    if error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
