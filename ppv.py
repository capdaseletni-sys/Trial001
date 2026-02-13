import asyncio
import httpx
import logging
import random
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright, Browser
from playwright_stealth import stealth_async

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger("PPV_Scraper")

TAG = "PPV"
PLAYLIST_NAME = "ppv.m3u8"
CONCURRENT_TASKS = 2 
MIRRORS = [
    "https://old.ppv.to/api/streams",
    "https://api.ppvs.su/api/streams",
    "https://api.ppv.to/api/streams",
]

def clean_timestamp(ts):
    if not ts: return 0
    return ts / 1000 if ts > 100_000_000_000 else ts

async def get_api_events():
    now = datetime.now(timezone.utc)
    start_window = now - timedelta(hours=2)
    end_window = now + timedelta(hours=8)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for mirror in MIRRORS:
            try:
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
                            events.append({"sport": sport, "event": ev.get("name"), "link": ev.get("iframe"), "logo": ev.get("poster"), "timestamp": ts})
                if events: return events
            except Exception: continue
    return []

async def intercept_m3u8(browser: Browser, ev: dict, semaphore: asyncio.Semaphore, extracted_urls: dict):
    async with semaphore:
        key = f"[{ev['sport']}] {ev['event']} ({TAG})"
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Apply stealth patches
        await stealth_async(page)
        
        found_url = None

        async def handle_response(response):
            nonlocal found_url
            url = response.url
            if ".m3u8" in url and not found_url:
                if any(x in url for x in ["index", "master", "m3u8", "premium"]):
                    found_url = url

        page.on("response", handle_response)
        
        try:
            log.info(f"Processing: {ev['event']}")
            
            # Go to link and wait for the page to settle
            await page.goto(ev["link"], wait_until="load", timeout=60000)
            await asyncio.sleep(random.uniform(5, 8))

            # Click center with randomization to simulate human interaction
            await page.mouse.click(640 + random.randint(-20, 20), 360 + random.randint(-20, 20))
            
            # Try to click any iframe play buttons
            for frame in page.frames:
                try:
                    await frame.click("body", timeout=1000, force=True)
                except:
                    pass

            # Extended polling for the stream to initialize
            for _ in range(30): 
                if found_url: break
                await asyncio.sleep(1)
                
            if found_url:
                log.info(f"✅ Found: {ev['event']}")
                extracted_urls[key] = {"url": found_url, "logo": ev["logo"], "timestamp": ev["timestamp"]}
            else:
                log.warning(f"❌ No stream caught for: {ev['event']}")
        except Exception as e:
            log.debug(f"Error: {e}")
        finally:
            await context.close()

async def main():
    events = await get_api_events()
    if not events:
        log.error("No events found.")
        return

    extracted_data = {}
    semaphore = asyncio.Semaphore(CONCURRENT_TASKS)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        tasks = [intercept_m3u8(browser, ev, semaphore, extracted_data) for ev in events]
        await asyncio.gather(*tasks)
        await browser.close()

    if extracted_data:
        lines = ["#EXTM3U"]
        for k, v in extracted_data.items():
            lines.append(f'#EXTINF:-1 tvg-id="Live.Event.us" tvg-logo="{v["logo"]}", {k}\n{v["url"]}')
        with open(PLAYLIST_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        log.info(f"Saved {len(extracted_data)} streams.")
    else:
        log.error("Still 0 streams captured. The site likely requires an active display (non-headless) or a real residential IP.")

if __name__ == "__main__":
    asyncio.run(main())
