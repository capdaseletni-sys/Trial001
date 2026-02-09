import json
import asyncio
import logging
import os
from datetime import datetime
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "YOUR_API_KEY") 
TARGET_URL = "https://pixelsport.tv/"
API_PATTERN = "/backend/livetv/events"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def run():
    async with async_playwright() as p:
        logging.info("🚀 Starting Active Bypass via ScraperAPI...")
        
        browser = await p.chromium.launch(headless=True)
        
        # We add 'antibot=true' specifically to the username as ScraperAPI requires
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            proxy={
                "server": "http://proxy-server.scraperapi.com:8001",
                "username": "scraperapi.render=true.antibot=true",
                "password": SCRAPERAPI_KEY
            }
        )
        
        page = await context.new_page()
        api_results = {"data": None}

        # Global listener for the API response
        async def handle_response(response):
            if API_PATTERN in response.url and response.status == 200:
                try:
                    api_results["data"] = await response.json()
                    logging.info("🎯 TARGET REACHED: API data captured!")
                except:
                    pass

        page.on("response", handle_response)

        try:
            logging.info(f"Navigating to {TARGET_URL}...")
            # We use 'domcontentloaded' to start our "human" actions as soon as possible
            await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=120000)

            # --- HUMAN SIMULATION LOOP ---
            # We scroll and wait for up to 45 seconds
            for i in range(45):
                if api_results["data"]:
                    break
                
                # Perform a "human" scroll every 2 seconds
                if i % 2 == 0:
                    await page.mouse.wheel(0, 400)
                    await asyncio.sleep(0.5)
                    await page.mouse.wheel(0, -200) # Slight scroll back up
                
                await asyncio.sleep(1)
                if i % 10 == 0:
                    logging.info(f"Searching for data... (Trial {i}s)")

            if not api_results["data"]:
                # Save a screenshot to see what's blocking us
                await page.screenshot(path="debug_timeout.png")
                raise Exception("Capture Timed Out. Site might be in a verification loop.")

            # --- M3U DATA GENERATION ---
            events = api_results["data"]
            if isinstance(events, dict) and "events" in events:
                events = events["events"]

            filename = f"pixelsport_live.m3u8"
            m3u_content = "#EXTM3U\n"
            count = 0

            for event in events:
                name = event.get('match_name', 'Match')
                channel = event.get('channel', {})
                url = channel.get('server1URL') or event.get('server1URL')

                if url and str(url).lower() != "null":
                    # Fix common server URL issues
                    if "hd.bestlive.top:443" in url:
                        url = url.replace("hd.bestlive.top:443", "hd.pixelhd.online:443")
                    
                    category = channel.get('TVCategory', {}).get('name', 'Sports')
                    m3u_content += f'#EXTINF:-1 group-title="{category}",{name}\n{url}\n'
                    count += 1

            with open(filename, "w", encoding="utf-8") as f:
                f.write(m3u_content)
                
            logging.info(f"✅ Success! Generated {filename} with {count} streams.")

        except Exception as e:
            logging.error(f"❌ Scrape failed: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
