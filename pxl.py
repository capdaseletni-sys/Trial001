import json
import asyncio
import sys
from playwright.async_api import async_playwright

# Attempt to import stealth, fallback to a no-op if it fails
try:
    from playwright_stealth import stealth_async
except ImportError:
    # If the package isn't installed or import fails, we create a dummy function
    async def stealth_async(page):
        pass

async def run():
    async with async_playwright() as p:
        print("Launching browser...")
        # Basic browser setup
        browser = await p.chromium.launch(headless=True)
        
        # Consistent User-Agent is critical for stream playback later
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        
        context = await browser.new_context(
            user_agent=ua,
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = await context.new_page()
        
        # Apply stealth to hide headless nature
        await stealth_async(page)

        # Container for the API response
        api_data_future = asyncio.Future()

        async def handle_response(response):
            # We look for the specific backend endpoint
            if "backend/livetv/events" in response.url:
                try:
                    text = await response.text()
                    if text and not api_data_future.done():
                        api_data_future.set_result(text)
                except Exception:
                    pass

        # Listen for all network responses
        page.on("response", handle_response)

        try:
            print("Warming up on homepage...")
            # Navigate to the home page to get session cookies
            await page.goto("https://pixelsport.tv/", wait_until="networkidle", timeout=60000)
            
            print("Waiting for API data to trigger...")
            try:
                # Wait for the site to naturally call its own API
                raw_json = await asyncio.wait_for(api_data_future, timeout=20)
            except asyncio.TimeoutError:
                print("API didn't trigger automatically, forcing direct navigation...")
                await page.goto("https://pixelsport.tv/backend/livetv/events", wait_until="domcontentloaded")
                # If it still hasn't triggered, try grabbing the body text
                if not api_data_future.done():
                    content = await page.locator("body").inner_text()
                    raw_json = content
                else:
                    raw_json = await api_data_future

            # Parsing logic
            data = json.loads(raw_json)
            events = data.get("events", data) if isinstance(data, dict) else data

            m3u_content = "#EXTM3U\n"
            count = 0
            
            for event in events:
                name = event.get('match_name', 'Unknown Match')
                channel = event.get('channel', {})
                # Try to find the URL in multiple possible JSON locations
                url_s1 = channel.get('server1URL') or event.get('server1URL')
                
                if url_s1 and str(url_s1).lower() != "null":
                    # --- DOMAIN REPLACEMENT ---
                    if "hd.bestlive.top:443" in url_s1:
                        url_s1 = url_s1.replace("hd.bestlive.top:443", "hd.pixelhd.online:443")
                    
                    # --- IPTV PLAYER COMPATIBILITY ---
                    # Adding headers to the URL itself (Pipe syntax) works for more players
                    headers = f"|User-Agent={ua}&Referer=https://pixelsport.tv/&Origin=https://pixelsport.tv"
                    
                    m3u_content += f'#EXTINF:-1 group-title="pixelsports",{name}\n'
                    # VLC Specific Options
                    m3u_content += f'#EXTVLCOPT:http-referrer=https://pixelsport.tv\n'
                    m3u_content += f'#EXTVLCOPT:http-user-agent={ua}\n'
                    # Final Stream URL
                    m3u_content += f'{url_s1}{headers}\n'
                    count += 1

            # Save the file
            with open("pixelsports.m3u8", "w", encoding="utf-8") as f:
                f.write(m3u_content)
            
            print(f"Success! Generated pixelsports.m3u8 with {count} channels.")

        except Exception as e:
            print(f"Scrape failed: {str(e)}")
            # Optional: Print page content on failure to debug
            # print(await page.content())
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
