import json
import asyncio
import logging
import requests
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_free_proxies():
    """Fetches a list of free HTTP proxies."""
    logging.info("Fetching fresh proxy list...")
    try:
        # Fetching from a public API (HTTP, SSL, 10s timeout)
        response = requests.get("https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all")
        if response.status_code == 200:
            proxies = response.text.strip().split("\r\n")
            logging.info(f"Retrieved {len(proxies)} proxies.")
            return proxies
    except Exception as e:
        logging.error(f"Failed to fetch proxies: {e}")
    return []

async def run():
    proxy_list = get_free_proxies()
    
    # We will try up to 5 different proxies
    for i in range(min(5, len(proxy_list))):
        proxy_addr = proxy_list[i]
        logging.info(f"Attempting with Proxy: {proxy_addr}")
        
        async with async_playwright() as p:
            try:
                # Format: http://ip:port
                proxy_config = {"server": f"http://{proxy_addr}"}
                
                browser = await p.chromium.launch(
                    headless=False, # Use xvfb-run in GitHub Actions
                    proxy=proxy_config,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
                )
                
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                
                page = await context.new_page()
                await Stealth().apply_stealth_async(page)
                
                api_results = {"data": None}
                page.on("response", lambda res: handle_response(res, api_results))

                # Attempt to load the page
                # Lowering timeout for individual proxies so we don't wait forever on dead ones
                await page.goto("https://pixelsport.tv/", wait_until="domcontentloaded", timeout=30000)
                
                # Wait to see if data is captured
                for _ in range(15):
                    if api_results["data"]:
                        break
                    await asyncio.sleep(1)

                if api_results["data"]:
                    await process_data(api_results["data"])
                    await browser.close()
                    return # Exit the entire script on success

                logging.warning(f"Proxy {proxy_addr} failed to load data. Trying next...")
                await browser.close()

            except Exception as e:
                logging.warning(f"Proxy {proxy_addr} error: {e}")
                continue

    logging.error("❌ All proxy attempts failed.")

async def handle_response(response, storage):
    if "/backend/livetv/events" in response.url and response.status == 200:
        try:
            storage["data"] = await response.json()
        except:
            pass

async def process_data(data):
    events = data.get("events", data) if isinstance(data, dict) else data
    filename = f"pixelsports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.m3u8"
    # ... (Your existing M3U generation logic here)
    logging.info(f"✅ Success! Data saved to {filename}")

if __name__ == "__main__":
    asyncio.run(run())
