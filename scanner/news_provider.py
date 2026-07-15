import os
import json
import time
import logging
import urllib.request
from datetime import datetime
import pytz
import scanner.config as config

logger = logging.getLogger(__name__)

# URL of the economic calendar JSON feed
CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
# Path to local cache file
CACHE_FILE = os.path.join(os.path.dirname(__file__), "news_cache.json")
# Cache duration in seconds (1 hour)
CACHE_DURATION = 3600

def fetch_and_cache_calendar() -> list:
    """
    Fetch the weekly economic calendar. Uses local cache if it is fresh (less than 1 hour old).
    If fetch fails, falls back to the cache if it exists.
    """
    # Check if cache is still valid
    if os.path.exists(CACHE_FILE):
        mtime = os.path.getmtime(CACHE_FILE)
        if time.time() - mtime < CACHE_DURATION:
            logger.info("Using cached economic calendar data.")
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading economic calendar cache: {e}")

    # Fetch fresh data
    logger.info("Fetching fresh economic calendar data from Faireconomy...")
    req = urllib.request.Request(
        CALENDAR_URL, 
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
            # Decode and validate JSON
            parsed_json = json.loads(data.decode("utf-8"))
            
            # Save to cache
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(parsed_json, f, indent=4)
                logger.info("Economic calendar cache updated successfully.")
            except Exception as cache_err:
                logger.error(f"Failed to write economic calendar cache: {cache_err}")
                
            return parsed_json
    except Exception as e:
        logger.error(f"Failed to fetch economic calendar from web: {e}")
        # Fallback to cache if available even if expired
        if os.path.exists(CACHE_FILE):
            logger.warning("Fetch failed. Falling back to expired economic calendar cache.")
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as read_err:
                logger.error(f"Failed to read expired cache: {read_err}")
        return []

def get_today_high_impact_news(currencies: list) -> list:
    """
    Filter today's high impact news for the specified currencies.
    Returns a list of dicts with: title, country, time_str, impact
    """
    events = fetch_and_cache_calendar()
    if not events:
        return []

    local_tz = pytz.timezone(config.TIMEZONE_STR)
    today = datetime.now(local_tz).date()
    currencies_upper = [c.upper() for c in currencies]

    today_high_impact_events = []

    for event in events:
        # Filter by impact
        impact = event.get("impact", "")
        if impact.lower() != "high":
            continue

        # Filter by country (currency)
        country = event.get("country", "")
        if country.upper() not in currencies_upper:
            continue

        # Parse date and convert to local timezone
        date_str = event.get("date", "")
        if not date_str:
            continue

        try:
            # Parse ISO format: e.g. "2026-07-12T18:30:00-04:00"
            dt_utc = datetime.fromisoformat(date_str)
            dt_local = dt_utc.astimezone(local_tz)
            
            if dt_local.date() == today:
                today_high_impact_events.append({
                    "title": event.get("title", "Economic Event"),
                    "country": country,
                    "time_str": dt_local.strftime("%H:%M"),
                    "impact": impact
                })
        except Exception as parse_err:
            logger.error(f"Error parsing event date '{date_str}': {parse_err}")

    # Sort events by time_str ascending
    today_high_impact_events.sort(key=lambda x: x["time_str"])
    return today_high_impact_events

if __name__ == "__main__":
    # Test script directly
    logging.basicConfig(level=logging.INFO)
    print("Testing scanner/news_provider.py...")
    # Fetch test
    test_events = get_today_high_impact_news(["USD", "EUR", "GBP"])
    print(f"\nDitemukan {len(test_events)} berita High Impact hari ini untuk USD/EUR/GBP:")
    for ev in test_events:
        print(f"• [{ev['time_str']} WIB] {ev['country']} - {ev['title']} ({ev['impact']})")
