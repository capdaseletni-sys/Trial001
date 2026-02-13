import asyncio
import httpx
import logging
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright, Browser

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
log = logging.getLogger("PPV_Scraper")

TAG = "PPV"
PLAYLIST_NAME = "ppv.m3u8"
MIRRORS = [
    "https://old.ppv.to/api/streams",
    "https://api.ppvs.su/api/streams",
    "https://api.ppv.to/api/streams",
]

def clean_timestamp(ts):
    """Detects and converts milliseconds to seconds if necessary."""
    if ts > 100_000_000_000:  # If 13 digits, it's milliseconds
        return ts / 1000
    return ts

async def save_to_m3u(data: dict):
    lines = ["#EXTM3U"]
    for key, info in data.items():
        group = key.split("]")[0][1:] if "]" in key else "Sports"
        lines.append(f'#EXTINF:-1 tvg-id="{info.get("id", "Live.Event.us")}" tvg-logo="{info.get("logo", "")}" group-title="{group}", {key}')
        lines.append(info["url"])
    
    with open(PLAYLIST_NAME, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info(f"Playlist saved: {len(data)} streams found.")

async def get_api_events():
    now = datetime.now(timezone.utc)
    # Wider window: 2 hours ago to 24 hours ahead
    start_window = now - timedelta(hours=2)
    end_window = now + timedelta(hours=24)
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for mirror in MIRRORS:
            try:
                log.info(f"Checking mirror: {mirror}")
                r = await client.get(mirror, timeout=15)
                if r.status_code != 200: continue
                
                api_data = r.json()
                events = []
                for group in api_data.get("streams", []):
                    sport = group.get("category")
                    if sport == "24/7 Streams": continue
                    
                    for ev in group.get("streams", []):
                        raw_ts = ev.get("starts_at")
                        if not raw_ts: continue
                        
                        ts = clean_timestamp(raw_ts)
                        event_dt = datetime.fromtimestamp(ts, tz=timezone.utc)

                        if start_window <= event_dt <= end_window:
                            events.append({
                                "sport": sport,
                                "event": ev.get("name"),
                                "link": ev.get("iframe"),
                                "logo": ev.get("poster"),
                                "timestamp": ts
                            })
                
                if events:
                    log.info(f"Found {len(events)} events on {mirror}")
                    return events
            except Exception as e:
                log.warning(f"Mirror failed: {e}")
    return []

async def intercept_m3u8(browser: Browser, iframe_url: str):
    context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    page = await context.new_page()
    found_url = None

    def handle_request(request):
        nonlocal found_url
        if ".m3u8" in request.url and not found_url:
            # Avoid segments like .ts or key files, look for the playlist
            if "index" in request.url or "master" in request.url or request.url.endswith(".m3u8"):
                found_url = request.url

    page.on("request", handle_request)
    try:
        await page.goto(iframe_url, wait_until="load", timeout=30000)
        await asyncio.sleep(8) # Wait for player to trigger network requests
    except Exception:
        pass
    finally:
        await context.close()
    return found_url

async def main():
    events = await get_api_events()
    if not events:
        log.error("No events found. Check if matches are scheduled today.")
        return

    extracted_urls = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Limit to first 5 events for testing to avoid getting blocked
        for ev in events[:5]:
            key = f"[{ev['sport']}] {ev['event']} ({TAG})"
            log.info(f"Attempting: {ev['event']}")
            live_link = await intercept_m3u8(browser, ev["link"])
            
            if live_link:
                log.info(f"Found: {live_link}")
                extracted_urls[key] = {"url": live_link, "logo": ev["logo"], "timestamp": ev["timestamp"]}
        await browser.close()

    if extracted_urls:
        await save_to_m3u(extracted_urls)

if __name__ == "__main__":
    asyncio.run(main())
