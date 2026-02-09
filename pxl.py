import json
import asyncio
import logging
import os
from datetime import datetime
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def run():
    async with async_playwright() as p:
        # Use a persistent data folder to save cookies/session
        user_data_dir = "./browser_session"
        
        # Launch with 'headless=False' to bypass the toughest checks
        # If running on a server without a screen, use 'xvfb-run'
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False, # Change to True ONLY after you verify it works once
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        page = await browser_context.new_page()
        base_url = "https://pixelsport.tv/"
        api_pattern = "/backend/livetv/events"

        try:
            logging.info("Opening site... please wait for Cloudflare to clear.")
            
            # Setup a container for our data
            api_results = {"data": None}

            async def catch_json(response):
                if api_pattern in response.url and response.status == 200:
                    try:
                        api_results["data"] = await response.json()
                        logging.info("🎯 API Data captured!")
                    except:
                        pass

            page.on("response", catch_json)

            # Go to home and wait a bit for scripts to run
            await page.goto(base_url, wait_until="load")
            
            # Sleep to allow 'Turnstile' or 'Challenge' to complete
            # If a checkbox appears, you might need to click it manually once
            for i in range(15):
                if api_results["data"]:
                    break
                await asyncio.sleep(1)
                if i % 5 == 0:
                    logging.info("Still waiting for data...")

            if not api_results["data"]:
                raise Exception("Failed to capture API. Is there a 'Verify you are human' box on screen?")

            # Processing Data
            events_data = api_results["data"]
            events = events_data.get("events", events_data) if isinstance(events_data, dict) else events_data

            filename = f"pixelsports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.m3u8"
            m3u_content = "#EXTM3U\n"
            count = 0

            for event in events:
                name = event.get('match_name', 'Unknown Match')
                channel = event.get('channel', {})
                url_s1 = channel.get('server1URL') or event.get('server1URL')

                if url_s1 and str(url_s1).lower() != "null":
                    if "hd.bestlive.top:443" in url_s1:
                        url_s1 = url_s1.replace("hd.bestlive.top:443", "hd.pixelhd.online:443")

                    category = channel.get('TVCategory', {}).get('name', 'Live Sports')
                    m3u_content += (
                        f'#EXTINF:-1 group-title="{category}",{name}\n'
                        f'#EXTVLCOPT:http-referrer=https://pixelsport.tv/\n'
                        f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36\n'
                        f'{url_s1}\n'
                    )
                    count += 1

            with open(filename, "w", encoding="utf-8") as f:
                f.write(m3u_content)

            logging.info(f"✅ Success! Saved {count} items to {filename}")

        except Exception as e:
            logging.error(f"❌ Error: {e}")
        finally:
            await browser_context.close()

if __name__ == "__main__":
    asyncio.run(run())
