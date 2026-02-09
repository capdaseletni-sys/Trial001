import json
import asyncio
import logging
from datetime import datetime
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
SCRAPERAPI_KEY = "dfbecf5ba79c271d0aad841372ad12d3" # Put your key here
TARGET_URL = "https://pixelsport.tv/"
API_PATTERN = "/backend/livetv/events"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def run():
    async with async_playwright() as p:
        # Instead of a normal proxy, we use ScraperAPI's proxy endpoint
        # This routes all browser traffic through their 'human' residential IPs
        proxy_url = f"http://scraperapi:render=true&antibot=true@{proxy_server()}"
        
        logging.info("🚀 Launching browser via ScraperAPI...")
        
        browser = await p.chromium.launch(
            headless=True,
            proxy={
                "server": "http://proxy-server.scraperapi.com:8001",
                "username": f"scraperapi.render=true.antibot=true",
                "password": SCRAPERAPI_KEY
            }
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        api_results = {"data": None}

        # Catch the data as the page loads
        async def catch_json(response):
            if API_PATTERN in response.url and response.status == 200:
                try:
                    api_results["data"] = await response.json()
                    logging.info("🎯 Found the API data!")
                except:
                    pass

        page.on("response", catch_json)

        try:
            logging.info(f"Navigating to {TARGET_URL}...")
            # Increased timeout because ScraperAPI can take a few seconds to find a clean IP
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=90000)

            # Wait up to 20 seconds for the backend call to complete
            for _ in range(20):
                if api_results["data"]:
                    break
                await asyncio.sleep(1)

            if not api_results["data"]:
                raise Exception("Failed to capture data. Cloudflare might have still blocked the IP.")

            # --- PROCESS M3U ---
            events = api_results["data"]
            if isinstance(events, dict) and "events" in events:
                events = events["events"]

            filename = f"pixelsports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.m3u8"
            m3u_content = "#EXTM3U\n"
            count = 0

            for event in events:
                name = event.get('match_name', 'Unknown')
                channel = event.get('channel', {})
                url = channel.get('server1URL') or event.get('server1URL')

                if url and str(url).lower() != "null":
                    if "hd.bestlive.top:443" in url:
                        url = url.replace("hd.bestlive.top:443", "hd.pixelhd.online:443")
                    
                    category = channel.get('TVCategory', {}).get('name', 'Sports')
                    m3u_content += f'#EXTINF:-1 group-title="{category}",{name}\n{url}\n'
                    count += 1

            with open(filename, "w", encoding="utf-8") as f:
                f.write(m3u_content)
            logging.info(f"✅ Success! Saved {count} items.")

        except Exception as e:
            logging.error(f"❌ Scrape failed: {e}")
        finally:
            await browser.close()

def proxy_server():
    return "proxy-server.scraperapi.com:8001"

if __name__ == "__main__":
    asyncio.run(run())
