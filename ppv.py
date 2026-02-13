import asyncio
import httpx
import logging
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright, Browser

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger("PPV_Scraper")

TAG = "PPV"
PLAYLIST_NAME = "ppv.m3u8"
CONCURRENT_TASKS = 3  # Safe limit for GitHub Runners
MIRRORS = [
    "https://old.ppv.to/api/streams",
    "https://api.ppvs.su/api/streams",
    "https://api.ppv.to/api/streams",
]

# --- Utilities ---

def clean_timestamp(ts):
    """Handles both seconds and milliseconds timestamps."""
    if not ts: return 0
    return ts / 1000 if ts > 100_000_000_000 else ts

async def get_api_events():
    """Fetches and filters events from mirrors."""
    now = datetime.now(timezone.utc)
    # Window: Started up to 1 hour ago, or starting in next 6 hours
    start_window = now - timedelta(hours=1)
    end_window = now + timedelta(hours=6)
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for mirror in MIRRORS:
            try:
                log.info(f"Checking mirror: {mirror}")
                r = await client.get(mirror, timeout=15)
                if r.status_code != 200: continue
                
                events = []
                data = r.json()
                for group in data.get("streams", []):
                    sport = group.get("category")
                    if sport == "24/7 Streams": continue
                    
                    for ev in group.get("streams", []):
                        ts = clean_timestamp(ev.get("starts_at"))
                        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        
                        if start_window <= dt <= end_window:
                            events.append({
                                "sport": sport,
                                "event": ev.get("name"),
                                "link": ev.get("iframe"),
                                "logo": ev.get("poster"),
                                "timestamp": ts
                            })
                
                if events:
                    log.info(f"Found {len(events)} relevant events.")
                    return events
            except Exception as e:
                log.warning(f"Mirror {mirror} failed: {e}")
    return []

async def intercept_m3u8(browser: Browser, ev: dict, semaphore: asyncio.Semaphore, extracted_urls: dict):
    """Navigates to iframe, bypasses 'Click-to-Play', and catches .m3u8 URL."""
    async with semaphore:
        key = f"[{ev['sport']}] {ev['event']} ({TAG})"
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        page = await context.new_page()
        found_url = None

        # Network interceptor
        def handle_request(request):
            nonlocal found_url
            url = request.url
            if ".m3u8" in url and not found_url:
                # Target the actual stream index/master files
                if any(x in url for x in ["index", "master", "playlist", "m3u8"]):
                    found_url = url

        page.on("request", handle_request)
        
        try:
            log.info(f"Processing: {ev['event']}")
            await page.goto(ev["link"], wait_until="domcontentloaded", timeout=30000)
            
            # Mimic user interaction to trigger the player
            await asyncio.sleep(3)
            await page.mouse.click(640, 360) # Click center of video
            
            # Poll for the URL to appear in network traffic
            for _ in range(15): 
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
                log.warning(f"❌ No stream caught for: {ev['event']}")
        except Exception as e:
            log.debug(f"Error on {ev['event']}: {e}")
        finally:
            await context.close()

async def main():
    events = await get_api_events()
    if not events:
        log.error("No valid events found in the current time window.")
        return

    extracted_data = {}
    semaphore = asyncio.Semaphore(CONCURRENT_TASKS)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Build task list
        tasks = [intercept_m3u8(browser, ev, semaphore, extracted_data) for ev in events]
        
        # Run concurrently
        await asyncio.gather(*tasks)
        await browser.close()

    # Save Results
    if extracted_data:
        lines = ["#EXTM3U"]
        for k, v in extracted_data.items():
            lines.append(f'#EXTINF:-1 tvg-id="Live.Event.us" tvg-logo="{v["logo"]}", {k}')
            lines.append(v["url"])
        
        with open(PLAYLIST_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        log.info(f"Successfully saved {len(extracted_data)} streams to {PLAYLIST_NAME}")
    else:
        log.error("Extraction finished but 0 streams were captured.")

if __name__ == "__main__":
    asyncio.run(main())
