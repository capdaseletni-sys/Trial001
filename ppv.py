import asyncio
import httpx
import logging
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright, Browser

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
log = logging.getLogger("PPV_Scraper")

TAG = "PPV"
PLAYLIST_NAME = "ppv.m3u8"
CONCURRENT_TASKS = 3  # How many browsers to run at once
MIRRORS = [
    "https://old.ppv.to/api/streams",
    "https://api.ppvs.su/api/streams",
    "https://api.ppv.to/api/streams",
]

def clean_timestamp(ts):
    return ts / 1000 if ts > 100_000_000_000 else ts

async def intercept_m3u8(browser: Browser, ev: dict, semaphore: asyncio.Semaphore, extracted_urls: dict):
    """Processes a single event with a concurrency limit."""
    async with semaphore:
        key = f"[{ev['sport']}] {ev['event']} ({TAG})"
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        found_url = None

        def handle_request(request):
            nonlocal found_url
            # Catch the m3u8 but ignore common noise like ads or tracking
            if ".m3u8" in request.url and not found_url:
                if any(x in request.url for x in ["index", "master", "playlist", "chunk"]):
                    found_url = request.url

        page.on("request", handle_request)
        
        try:
            log.info(f"Processing: {ev['event']}")
            # Use 'commit' to get in fast, then wait for network
            await page.goto(ev["link"], wait_until="domcontentloaded", timeout=20000)
            
            # Polling for the URL instead of a hard sleep
            for _ in range(10): 
                if found_url: break
                await asyncio.sleep(1)
                
            if found_url:
                log.info(f"✅ Found: {ev['event']}")
                extracted_urls[key] = {
                    "url": found_url,
                    "logo": ev["logo"],
                    "timestamp": ev["timestamp"]
                }
            else:
                log.warning(f"❌ No stream for: {ev['event']}")
        except Exception:
            log.error(f"⚠️ Timeout/Error on: {ev['event']}")
        finally:
            await context.close()

async def get_api_events():
    now = datetime.now(timezone.utc)
    start_window = now - timedelta(hours=1)
    end_window = now + timedelta(hours=6)
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for mirror in MIRRORS:
            try:
                r = await client.get(mirror, timeout=15)
                if r.status_code != 200: continue
                
                events = []
                for group in r.json().get("streams", []):
                    sport = group.get("category")
                    if sport == "24/7 Streams": continue
                    for ev in group.get("streams", []):
                        ts = clean_timestamp(ev.get("starts_at", 0))
                        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        if start_window <= dt <= end_window:
                            events.append({"sport": sport, "event": ev.get("name"), "link": ev.get("iframe"), "logo": ev.get("poster"), "timestamp": ts})
                return events
            except Exception: continue
    return []

async def main():
    events = await get_api_events()
    if not events:
        log.error("No events found in time window.")
        return

    log.info(f"Starting extraction for {len(events)} events...")
    extracted_data = {}
    semaphore = asyncio.Semaphore(CONCURRENT_TASKS)

    async with async_playwright() as p:
        # Launch once
        browser = await p.chromium.launch(headless=True)
        
        # Create a list of tasks for all events
        tasks = [intercept_m3u8(browser, ev, semaphore, extracted_data) for ev in events]
        
        # Run them concurrently
        await asyncio.gather(*tasks)
        await browser.close()

    if extracted_data:
        lines = ["#EXTM3U"]
        for k, v in extracted_data.items():
            lines.append(f'#EXTINF:-1 tvg-id="Live.Event.us" tvg-logo="{v["logo"]}", {k}\n{v["url"]}')
        
        with open(PLAYLIST_NAME, "w") as f:
            f.write("\n".join(lines))
        log.info(f"Done! Saved {len(extracted_data)} streams to {PLAYLIST_NAME}")

if __name__ == "__main__":
    asyncio.run(main())
