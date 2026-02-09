import json
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

async def run():
    async with async_playwright() as p:
        # 1. Setup Browser
        browser = await p.chromium.launch(headless=True)
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        context = await browser.new_context(user_agent=ua)
        page = await context.new_page()
        await stealth_async(page)

        # 2. Preparation for Capture
        # We use a Future to "catch" the data from the background network request
        api_data_future = asyncio.Future()

        async def handle_response(response):
            # If the background request URL matches our API, grab the data
            if "backend/livetv/events" in response.url:
                try:
                    text = await response.text()
                    if text:
                        api_data_future.set_result(text)
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            print("Navigating to PixelSport...")
            # Navigate to the main page first to get cookies/session active
            await page.goto("https://pixelsport.tv/", wait_until="networkidle")
            
            # Sometimes we need to click "Live TV" or wait for the site to trigger the API
            print("Waiting for background API call...")
            
            # Wait up to 15 seconds for the API to trigger naturally
            try:
                raw_json = await asyncio.wait_for(api_data_future, timeout=15)
            except asyncio.TimeoutError:
                print("API didn't trigger automatically, forcing navigation...")
                await page.goto("https://pixelsport.tv/backend/livetv/events")
                raw_json = await api_data_future

            # 3. Process Data
            data = json.loads(raw_json)
            events = data.get("events", data) if isinstance(data, dict) else data

            m3u_content = "#EXTM3U\n"
            count = 0
            for event in events:
                name = event.get('match_name', 'Unknown Match')
                channel = event.get('channel', {})
                url_s1 = channel.get('server1URL') or event.get('server1URL')
                
                if url_s1 and url_s1 != "null":
                    if "hd.bestlive.top:443" in url_s1:
                        url_s1 = url_s1.replace("hd.bestlive.top:443", "hd.pixelhd.online:443")
                    
                    # Pipe syntax for best player compatibility
                    headers = f"|User-Agent={ua}&Referer=https://pixelsport.tv/&Origin=https://pixelsport.tv"
                    m3u_content += f'#EXTINF:-1 group-title="pixelsports",{name}\n'
                    m3u_content += f'#EXTVLCOPT:http-referrer=https://pixelsport.tv\n'
                    m3u_content += f'#EXTVLCOPT:http-user-agent={ua}\n'
                    m3u_content += f'{url_s1}{headers}\n'
                    count += 1

            with open("pixelsports.m3u8", "w", encoding="utf-8") as f:
                f.write(m3u_content)
            
            print(f"Done! Saved {count} matches.")

        except Exception as e:
            print(f"Scrape failed: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
