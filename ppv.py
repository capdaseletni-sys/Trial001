import asyncio
import httpx
import logging
import random
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright, Browser
from playwright_stealth import stealth_async  # Ensure 'pip install playwright-stealth' was run

# ... (rest of the config and get_api_events remains the same)

async def intercept_m3u8(browser: Browser, ev: dict, semaphore: asyncio.Semaphore, extracted_urls: dict):
    async with semaphore:
        key = f"[{ev['sport']}] {ev['event']} ({TAG})"
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Apply stealth patches to the page
        await stealth_async(page)
        
        found_url = None

        def handle_request(request):
            nonlocal found_url
            u = request.url
            if ".m3u8" in u and not found_url:
                if any(x in u for x in ["index", "master", "m3u8", "premium"]):
                    found_url = u

        page.on("request", handle_request)
        
        try:
            log.info(f"Processing: {ev['event']}")
            
            # Go to link and wait for the page to settle
            await page.goto(ev["link"], wait_until="networkidle", timeout=60000)
            await asyncio.sleep(random.uniform(5, 8))

            # Move mouse to center and click (human-like)
            await page.mouse.move(640 + random.randint(-10, 10), 360 + random.randint(-10, 10))
            await page.mouse.down()
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.mouse.up()
            
            # Deep search through frames
            for frame in page.frames:
                try:
                    # Try to find a play button or common video player IDs
                    await frame.click("video", timeout=1000, force=True)
                except:
                    try:
                        await frame.click("body", timeout=500, force=True)
                    except:
                        continue

            # Extended polling
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
