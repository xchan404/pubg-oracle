import json
import logging

from config import DATA_DIR, DEFAULT_CHANNELS

logger = logging.getLogger("pubg_scraper")

CHANNELS_FILE = DATA_DIR / "channels.json"

def get_active_channels():
    """
    Returns a list of active channels to scrape.
    Currently reads from a JSON file, and falls back to DEFAULT_CHANNELS.
    """
    if CHANNELS_FILE.exists():
        try:
            with open(CHANNELS_FILE, encoding="utf-8") as f:
                data = json.load(f)
                return data.get("active_channels", DEFAULT_CHANNELS)
        except Exception as e:
            logger.error(f"Error reading channels.json: {e}")
            return DEFAULT_CHANNELS
    else:
        # Create default file
        try:
            CHANNELS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
                json.dump({"active_channels": DEFAULT_CHANNELS}, f, indent=4)
        except Exception as e:
            logger.error(f"Error creating channels.json: {e}")
        return DEFAULT_CHANNELS

def add_channel(channel_url):
    """
    Adds a channel to the active channels list.
    """
    channels = get_active_channels()
    if channel_url not in channels:
        channels.append(channel_url)
        try:
            with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
                json.dump({"active_channels": channels}, f, indent=4)
            logger.info(f"Added channel: {channel_url}")
            return True
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            return False
    return False

def remove_channel(channel_url):
    """
    Removes a channel from the active channels list.
    """
    channels = get_active_channels()
    if channel_url in channels:
        channels.remove(channel_url)
        try:
            with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
                json.dump({"active_channels": channels}, f, indent=4)
            logger.info(f"Removed channel: {channel_url}")
            return True
        except Exception as e:
            logger.error(f"Error removing channel: {e}")
            return False
    return False
