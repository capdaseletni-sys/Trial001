import asyncio
import httpx
import logging
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright, Browser

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
log = logging.getLogger("PPV_Scraper")

TAG = "PPV"
PLAYLIST_NAME = "ppv.m3u8"
MIRRORS = [
    "https://old.ppv.to/api/streams",
    "https://api.ppvs.su/api/streams",
    "https://api.ppv.to/api/streams",
]

async def save_to_m3u(data: dict):
    """Formats and saves the dictionary to an M3U8 playlist."""
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
    print("\n--- M3U CONTENT PREVIEW ---")
    print("\n".join(lines[:10])) # Show first few lines in logs
    print("---------------------------\n")

async def get_api_events():
    """Checks mirrors and returns events within the time window."""
    now = datetime.now(timezone.utc)
    start_window = now - timedelta(minutes=45)
    end_window = now + timedelta(minutes=45)
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
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
                    log.info(f"Found {len(events)} valid events on {mirror}")
                    return events
            except Exception as e:
                log.warning(f"Mirror {mirror} failed: {e}")
    return []

async def intercept_m3u8(browser: Browser, iframe_url: str):
    """Loads the iframe and listens for the .m3u8 network request."""
    context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    page = await context.new_page()
    found_url = None

    def handle_request(request):
        nonlocal found_url
        # Catch requests ending in .m3u8 or containing index.m3u8
        if ".m3u8" in request.url and not found_url:
            found_url = request.url

    page.on("request", handle_request)

    try:
        log.info(f"Extracting: {iframe_url}")
        await page.goto(iframe_url, wait_until="networkidle", timeout=20000)
        # Wait a bit for the player to initialize and make the stream request
        await asyncio.sleep(5) 
    except Exception as e:
        log.error(f"Error loading {iframe_url}: {e}")
    finally:
        await context.close()
    
    return found_url

async def main():
    events = await get_api_events()
    if not events:
        log.error("No events found to process.")
        return

    extracted_urls = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        for ev in events:
            key = f"[{ev['sport']}] {ev['event']} ({TAG})"
            live_link = await intercept_m3u8(browser, ev["link"])
            
            if live_link:
                log.info(f"SUCCESS: {key}")
                extracted_urls[key] = {
                    "url": live_link,
                    "logo": ev["logo"],
                    "id": "Live.Event.us",
                    "timestamp": ev["timestamp"]
                }
            else:
                log.warning(f"FAILED to find stream for: {key}")
        
        await browser.close()

    if extracted_urls:
        await save_to_m3u(extracted_urls)
    else:
        log.error("No live streams were successfully extracted.")

if __name__ == "__main__":
    asyncio.run(main())
