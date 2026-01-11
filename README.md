# X to Nostr Bot

A free, self-hosted Python bot that monitors an X (Twitter) account using Nitter and reposts new posts to Nostr. Designed to run on a Raspberry Pi 5 using cron.

## Features

- ✅ Monitors X accounts via Nitter (no API keys required)
- ✅ Automatically detects new posts
- ✅ Publishes formatted notes to Nostr
- ✅ Stores state to prevent duplicate posts
- ✅ Clean exit for cron scheduling
- ✅ Uses only free, open-source libraries

## Prerequisites

- Raspberry Pi 5 with Raspberry Pi OS installed
- Internet connection
- Python 3.7 or higher
- A Nostr account with a private key (nsec format)

## Setup Instructions

### 1. Set Up Raspberry Pi 5 from Scratch

If you're starting with a fresh Raspberry Pi 5:

1. **Download Raspberry Pi OS**
   - Visit [raspberrypi.com/software](https://www.raspberrypi.com/software/)
   - Download Raspberry Pi Imager
   - Flash Raspberry Pi OS (64-bit recommended) to a microSD card (16GB or larger)

2. **Initial Setup**
   - Insert the microSD card into your Raspberry Pi 5
   - Connect keyboard, mouse, monitor, and power supply
   - Boot the Raspberry Pi and complete the initial setup wizard
   - Connect to Wi-Fi or Ethernet
   - Update the system:
     ```bash
     sudo apt update
     sudo apt upgrade -y
     ```

3. **Enable SSH (Optional, for remote access)**
   ```bash
     sudo systemctl enable ssh
     sudo systemctl start ssh
   ```

### 2. Install Python and Dependencies

1. **Install Python 3 and pip** (if not already installed):
   ```bash
   sudo apt install python3 python3-pip -y
   ```

2. **Install system dependencies** (required for some Python packages):
   ```bash
   sudo apt install python3-dev build-essential -y
   ```

3. **Navigate to the bot directory**:
   ```bash
   cd ~/x-scrapper
   ```

4. **Install Python dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

   **Note:** If you encounter permission errors, you can install for the current user only (recommended):
   ```bash
   pip3 install --user -r requirements.txt
   ```

### 3. Configure the Bot

1. **Edit `config.py`** using a text editor:
   ```bash
   nano config.py
   ```

2. **Update the following settings:**

   - **X_USERNAME**: The X (Twitter) username to monitor (without the @ symbol)
     ```python
     X_USERNAME = "elonmusk"  # Example
     ```

   - **NITTER_BASE_URL**: The Nitter instance to use
     ```python
     NITTER_BASE_URL = "https://nitter.net"
     ```

   - **NOSTR_PRIVATE_KEY**: Your Nostr private key in nsec format
     ```python
     NOSTR_PRIVATE_KEY = "nsec1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
     ```
     **How to get your Nostr private key:**
     - If using a Nostr client like Damus, Amethyst, or Snort, you can export your private key
     - It should start with `nsec1`
     - **Keep this key secure and private!**

   - **NOSTR_RELAYS**: List of Nostr relays to publish to
     ```python
     NOSTR_RELAYS = [
         "wss://relay.damus.io",
         "wss://nos.lol",
         "wss://relay.snort.social",
     ]
     ```

3. **Save and exit** (in nano: press `Ctrl+X`, then `Y`, then `Enter`)

### 4. Test the Bot

Before setting up cron, test the bot manually:

```bash
python3 bot.py
```

**Expected output:**
- If it's the first run, it will scrape the latest post and publish it to Nostr
- On subsequent runs, it will only publish if a new post is found
- Check your Nostr client to verify the post was published

**Common issues:**
- **"Error: nostr-sdk not installed"**: Run `pip3 install --user nostr-sdk`
- **"Error: Failed to fetch from Nitter"**: Try a different Nitter instance (see "Rotate Nitter Mirrors" section)
- **"Error: Failed to publish to Nostr"**: Check your private key and relay URLs

### 5. Set Up Cron

1. **Open the crontab editor**:
   ```bash
   crontab -e
   ```

2. **If prompted, choose your preferred editor** (nano is easiest for beginners)

3. **Add a cron entry at the end of the file**. Examples:

   **Run every hour:**
   ```bash
   0 * * * * cd /home/pi/x-scrapper && /usr/bin/python3 bot.py >> /home/pi/x-scrapper/bot.log 2>&1
   ```

   **Run every 30 minutes:**
   ```bash
   */30 * * * * cd /home/pi/x-scrapper && /usr/bin/python3 bot.py >> /home/pi/x-scrapper/bot.log 2>&1
   ```

   **Run every 15 minutes:**
   ```bash
   */15 * * * * cd /home/pi/x-scrapper && /usr/bin/python3 bot.py >> /home/pi/x-scrapper/bot.log 2>&1
   ```

   **Important:** Replace `/home/pi/x-scrapper` with the actual path to your bot directory.

4. **Save and exit** (in nano: `Ctrl+X`, then `Y`, then `Enter`)

5. **Verify the cron job was added**:
   ```bash
   crontab -l
   ```

## How to Change the Monitored X Account

1. **Edit `config.py`**:
   ```bash
   nano config.py
   ```

2. **Change the `X_USERNAME` variable**:
   ```python
   X_USERNAME = "new_username"  # Change this to the X username you want to monitor
   ```

3. **Save and exit**

4. **Optional: Reset state** (if you want to repost the latest post from the new account):
   ```bash
   echo '{"last_post_id": null, "last_updated": null}' > state.json
   ```

## How to Rotate Nitter Mirrors

Nitter instances can go down or become unavailable. If the bot fails with "Failed to fetch from Nitter", follow these steps:

1. **Find an available Nitter instance**. You can check:
   - [Nitter Instances List](https://github.com/zedeus/nitter/wiki/Instances)
   - [Status pages for various instances](https://status.d420.de/)

2. **Edit `config.py`**:
   ```bash
   nano config.py
   ```

3. **Update the `NITTER_BASE_URL` variable**:
   ```python
   NITTER_BASE_URL = "https://nitter.poast.org"  # Example alternative instance
   ```

4. **Test the new instance**:
   ```bash
   python3 bot.py
   ```

**Popular Nitter instances you can try:**
- `https://nitter.net`
- `https://nitter.poast.org`
- `https://nitter.privacyredirect.com`
- `https://nitter.1d4.us`
- `https://nitter.fdn.fr`
- `https://nitter.it`

**Note:** Some instances may have rate limits or be temporarily unavailable. If one doesn't work, try another.

## How to Run and Debug the Bot

### Manual Execution

Run the bot manually to test or debug:

```bash
cd ~/x-scrapper
python3 bot.py
```

### View Logs

If you set up logging in cron (as shown in the cron examples above), view logs:

```bash
cat ~/x-scrapper/bot.log
```

Or follow logs in real-time:

```bash
tail -f ~/x-scrapper/bot.log
```

### Check Cron Logs

View system logs for cron execution:

```bash
grep CRON /var/log/syslog | tail -20
```

### Common Debugging Steps

1. **Check if Python can import all modules**:
   ```bash
   python3 -c "import requests; import bs4; import nostr_sdk; print('All modules OK')"
   ```

2. **Test Nitter access manually**:
   ```bash
   curl -I https://nitter.net/example_user
   ```
   (Replace `example_user` with an actual X username)

3. **Verify config.py syntax**:
   ```bash
   python3 -c "import config; print('Config OK')"
   ```

4. **Check state.json**:
   ```bash
   cat state.json
   ```

5. **Test Nostr connection** (this requires modifying the script temporarily or using a Nostr client)

### Troubleshooting

**Problem:** Bot runs but doesn't detect new posts
- **Solution:** Check `state.json` - the `last_post_id` might be the same as the current post. You can manually reset it or wait for a new post.

**Problem:** "Module not found" errors
- **Solution:** Ensure you're using `pip3` and `python3`. Install dependencies with `pip3 install --user -r requirements.txt`

**Problem:** Permission denied errors
- **Solution:** Ensure the bot directory and files are readable/writable by your user. Use `chmod` if needed:
  ```bash
  chmod 755 bot.py
  chmod 644 config.py
  chmod 644 state.json
  ```

**Problem:** Nitter returns 429 (Too Many Requests)
- **Solution:** The Nitter instance is rate-limiting you. Wait a bit or switch to a different Nitter instance.

**Problem:** Nostr publish fails
- **Solution:** 
  - Verify your private key is correct (starts with `nsec1`)
  - Check relay URLs are valid (should start with `wss://`)
  - Try testing with a different relay
  - Check your internet connection

## File Structure

```
x-scrapper/
├── bot.py              # Main bot script
├── config.py           # Configuration file (edit this!)
├── state.json          # State file (stores last seen post ID)
├── requirements.txt    # Python dependencies
├── README.md          # This file
└── bot.log            # Log file (created by cron)
```

## Running Multiple Bot Instances

If you want to monitor multiple X accounts and post to different Nostr accounts, you can run multiple instances of the bot. Each instance needs its own directory with its own `config.py` and `state.json`.

### Setting Up Multiple Instances

1. **Create separate directories** for each bot instance:

   ```bash
   cd ~
   cp -r x-scrapper x-scrapper-account2
   cp -r x-scrapper x-scrapper-account3
   # etc.
   ```

2. **Configure each instance separately**:

   ```bash
   # Configure first instance
   cd ~/x-scrapper
   nano config.py
   # Set X_USERNAME and NOSTR_PRIVATE_KEY for first account
   
   # Configure second instance
   cd ~/x-scrapper-account2
   nano config.py
   # Set X_USERNAME and NOSTR_PRIVATE_KEY for second account
   ```

3. **Set up separate cron entries** for each instance:

   ```bash
   crontab -e
   ```

   Add one line per instance:

   ```bash
   # First account - runs every hour
   0 * * * * cd /home/pi/x-scrapper && /usr/bin/python3 bot.py >> /home/pi/x-scrapper/bot.log 2>&1
   
   # Second account - runs every hour (staggered by 30 minutes)
   30 * * * * cd /home/pi/x-scrapper-account2 && /usr/bin/python3 bot.py >> /home/pi/x-scrapper-account2/bot.log 2>&1
   
   # Third account - runs every hour (staggered by 20 minutes)
   40 * * * * cd /home/pi/x-scrapper-account3 && /usr/bin/python3 bot.py >> /home/pi/x-scrapper-account3/bot.log 2>&1
   ```

   **Tip:** Stagger the cron times (e.g., :00, :30, :20) to avoid all bots running simultaneously and reduce load on Nitter instances.

4. **Secure each config.py file**:

   ```bash
   chmod 600 ~/x-scrapper/config.py
   chmod 600 ~/x-scrapper-account2/config.py
   chmod 600 ~/x-scrapper-account3/config.py
   ```

### Directory Structure for Multiple Instances

```
~/
├── x-scrapper/              # First bot instance
│   ├── bot.py
│   ├── config.py           # Config for account 1
│   ├── state.json          # State for account 1
│   ├── bot.log
│   └── requirements.txt
├── x-scrapper-account2/     # Second bot instance
│   ├── bot.py
│   ├── config.py           # Config for account 2
│   ├── state.json          # State for account 2
│   ├── bot.log
│   └── requirements.txt
└── x-scrapper-account3/     # Third bot instance
    ├── bot.py
    ├── config.py           # Config for account 3
    ├── state.json          # State for account 3
    ├── bot.log
    └── requirements.txt
```

**Note:** You only need to install Python dependencies once (they're shared system-wide). Each instance needs its own directory to keep `config.py` and `state.json` separate.

## Security Notes

- **Never share your Nostr private key (`nsec`)**
- Keep `config.py` private (it contains your private key)
- Consider using file permissions to restrict access:
  ```bash
  chmod 600 config.py
  ```
- Regularly update your system and Python packages:
  ```bash
  sudo apt update && sudo apt upgrade
  pip3 install --upgrade requests beautifulsoup4 nostr-sdk
  ```

## License

This bot is free and open-source. Use at your own risk.

## Support

For issues or questions:
- Check the troubleshooting section above
- Verify your configuration in `config.py`
- Test the bot manually before relying on cron
- Check Nitter instance availability if scraping fails

## Example Cron Entry

Here's a complete example cron entry that runs every hour and logs output:

```bash
0 * * * * cd /home/pi/x-scrapper && /usr/bin/python3 /home/pi/x-scrapper/bot.py >> /home/pi/x-scrapper/bot.log 2>&1
```

Breakdown:
- `0 * * * *` - Run at minute 0 of every hour
- `cd /home/pi/x-scrapper` - Change to bot directory
- `/usr/bin/python3 /home/pi/x-scrapper/bot.py` - Run the bot
- `>> /home/pi/x-scrapper/bot.log 2>&1` - Append output to log file
