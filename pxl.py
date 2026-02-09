import json
import asyncio
import logging
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def run():
    async with async_playwright() as p:
        # Launching with args to further reduce bot detection
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        base_url = "https://pixelsport.tv/"
        api_pattern = "/backend/livetv/events"

        try:
            logging.info("Warming up and intercepting API data...")

            # Define a future to hold the JSON data
            api_data_future = asyncio.Future()

            # Listener to catch the specific API response
            async def handle_response(response):
                if api_pattern in response.url and response.status == 200:
                    try:
                        data = await response.json()
                        if not api_data_future.done():
                            api_data_future.set_result(data)
                    except Exception:
                        pass

            page.on("response", handle_response)

            # Navigate to the main page only
            await page.goto(base_url, wait_until="networkidle", timeout=60000)
            
            # Wait for the listener to catch the data (up to 15 seconds)
            try:
                events_data = await asyncio.wait_for(api_data_future, timeout=15)
                logging.info("Successfully intercepted API data.")
            except asyncio.TimeoutError:
                raise Exception("Timed out waiting for API response. The site might be blocking or the URL pattern changed.")

            events = events_data.get("events", events_data) if isinstance(events_data, dict) else events_data

            # --- M3U Generation ---
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

            logging.info(f"✅ Success! {count} matches saved to {filename}")

        except Exception as e:
            logging.error(f"❌ Scrape failed: {e}")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
