import asyncio
import json
import logging
import httpx  # Standard for async requests
from datetime import datetime, timedelta, timezone
from functools import partial
from playwright.async_api import async_playwright, Browser

# Setup basic logging since get_logger is gone
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

urls: dict[str, dict] = {}
TAG = "PPV"
PLAYLIST_NAME = "ppv.m3u8"

MIRRORS = [
    "https://old.ppv.to/api/streams",
    "https://api.ppvs.su/api/streams",
    "https://api.ppv.to/api/streams",
]

async def save_to_m3u(data: dict):
    """Generates the M3U file from the scraped URLs."""
    lines = ["#EXTM3U"]
    for key, info in data.items():
        group = key.split("]")[0][1:] if "]" in key else "Sports"
        line = (
            f'#EXTINF:-1 tvg-id="{info.get("id", "Live.Event.us")}" '
            f'tvg-logo="{info.get("logo", "")}" '
            f'group-title="{group}", {key}\n'
            f'{info["url"]}'
        )
        lines.append(line)
    
    with open(PLAYLIST_NAME, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info(f"Playlist saved to {PLAYLIST_NAME}")

async def get_events():
    now = datetime.now(timezone.utc)
    start_window = now - timedelta(minutes=30)
    end_window = now + timedelta(minutes=30)
    
    async with httpx.AsyncClient() as client:
        for mirror in MIRRORS:
            try:
                log.info(f"Checking mirror: {mirror}")
                r = await client.get(mirror, timeout=10)
                if r.status_code == 200:
                    api_data = r.json()
                    events = []
                    for group in api_data.get("streams", []):
                        sport = group.get("category")
                        if sport == "24/7 Streams": continue
                        
                        for ev in group.get("streams", []):
                            ts = ev.get("starts_at")
                            if not ts: continue
                            
                            event_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                            if start_window <= event_dt <= end_window:
                                events.append({
                                    "sport": sport,
                                    "event": ev.get("name"),
                                    "link": ev.get("iframe"),
                                    "logo": ev.get("poster"),
                                    "timestamp": ts
                                })
                    return events
            except Exception as e:
                log.warning(f"Mirror {mirror} failed: {e}")
    return []

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Your scraping logic would go here
        events = await get_events()
        
        # After processing events and filling the 'urls' dict:
        await save_to_m3u(urls)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
