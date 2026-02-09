import json
import asyncio
import logging
import os
from datetime import datetime
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
# It's better to pull this from GitHub Secrets/Environment variables
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "YOUR_API_KEY_HERE") 
TARGET_URL = "https://pixelsport.tv/"
API_PATTERN = "/backend/livetv/events"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def run():
    async with async_playwright() as p:
        logging.info("🚀 Launching via ScraperAPI (Bypassing SSL checks)...")
        
        # We launch the browser normally
        browser = await p.chromium.launch(headless=True)
        
        # The magic happens here: ignore_https_errors=True fixes the 0209 error
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            ignore_https_errors=True, 
            proxy={
                "server": "http://proxy-server.scraperapi.com:8001",
                "username": f"scraperapi.render=true.antibot=true",
                "password": SCRAPERAPI_KEY
            }
        )
        
        page = await context.new_page()
        api_results = {"data": None}

        async def catch_json(response):
            if API_PATTERN in response.url and response.status == 200:
                try:
                    api_results["data"] = await response.json()
                    logging.info("🎯 API Data captured!")
                except:
                    pass

        page.on("response", catch_json)

        try:
            logging.info(f"Navigating to {TARGET_URL}...")
            # Using wait_until="load" is often faster/more reliable with ScraperAPI
            await page.goto(TARGET_URL, wait_until="load", timeout=120000)

            # Wait for the API call to trigger and be captured
            for i in range(30):
                if api_results["data"]:
                    break
                await asyncio.sleep(1)
                if i % 10 == 0:
                    logging.info("Still waiting for backend response...")

            if not api_results["data"]:
                raise Exception("Data capture timed out. ScraperAPI couldn't find the event list.")

            # --- PROCESS DATA ---
            data = api_results["data"]
            events = data.get("events", data) if isinstance(data, dict) else data

            filename = f"pixelsports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.m3u8"
            m3u_content = "#EXTM3U\n"
            count = 0

            for event in events:
                name = event.get('match_name', 'Unknown Match')
                channel = event.get('channel', {})
                url = channel.get('server1URL') or event.get('server1URL')

                if url and str(url).lower() != "null":
                    if "hd.bestlive.top:443" in url:
                        url = url.replace("hd.bestlive.top:443", "hd.pixelhd.online:443")
                    
                    category = channel.get('TVCategory', {}).get('name', 'Live Sports')
                    m3u_content += (
                        f'#EXTINF:-1 group-title="{category}",{name}\n'
                        f'#EXTVLCOPT:http-referrer=https://pixelsport.tv/\n'
                        f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36\n'
                        f'{url}\n'
                    )
                    count += 1

            with open(filename, "w", encoding="utf-8") as f:
                f.write(m3u_content)
                
            logging.info(f"✅ Success! Saved {count} matches to {filename}")

        except Exception as e:
            logging.error(f"❌ Scrape failed: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
