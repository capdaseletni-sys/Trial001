import json
import asyncio
import logging
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def run():
    stealth = Stealth()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        await stealth.apply_stealth_async(page)

        base_url = "https://pixelsport.tv/"
        api_url = "https://pixelsport.tv/backend/livetv/events"

        try:
            logging.info("Warming up the session...")
            await page.goto(base_url, wait_until="networkidle")
            await asyncio.sleep(5)

            logging.info("Fetching event data from API...")
            response = await page.goto(api_url, wait_until="domcontentloaded")
            if not response or response.status != 200:
                raise Exception(f"Unexpected response status: {response.status if response else 'no response'}")

            try:
                raw_json = await page.locator("pre").inner_text(timeout=5000)
            except:
                raw_json = await page.locator("body").inner_text()

            if not raw_json.strip().startswith("{"):
                raise ValueError("Response doesn't look like JSON.")

            data = json.loads(raw_json)
            events = data.get("events", data) if isinstance(data, dict) else data

            filename = f"pixelsports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.m3u8"
            m3u_content = "#EXTM3U\n"
            count = 0

            for event in events:
                name = event.get('match_name', 'Unknown Match')
                channel = event.get('channel', {})
                url_s1 = (channel.get('server1URL') or event.get('server1URL')) or None

                if url_s1 and url_s1.lower() != "null":
                    if "hd.bestlive.top:443" in url_s1:
                        url_s1 = url_s1.replace("hd.bestlive.top:443", "hd.pixelhd.online:443")

                    category = channel.get('TVCategory', {}).get('name', 'Live Sports')
                    m3u_content += (
                        f'#EXTINF:-1 group-title="{category}",{name}\n'
                        f'#EXTVLCOPT:http-referrer=https://pixelsport.tv\n'
                        f'#EXTVLCOPT:http-origin=https://pixelsport.tv\n'
                        f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        f'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0\n'
                        f'{url_s1}\n'
                    )
                    count += 1

            with open(filename, "w", encoding="utf-8") as f:
                f.write(m3u_content)

            logging.info(f"✅ Success! {count} matches saved to {filename}")

        except Exception as e:
            logging.error(f"❌ Scrape failed: {e}", exc_info=True)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
