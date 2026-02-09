import json
import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        context = await browser.new_context(user_agent=ua)
        page = await context.new_page()
        
        # Optional: apply stealth if the package exists
        try:
            from playwright_stealth import stealth_async
            await stealth_async(page)
        except:
            pass

        try:
            print("Warming up on homepage to get cookies...")
            await page.goto("https://pixelsport.tv/", wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5) # Give it a moment to settle

            print("Fetching API data directly...")
            # We use page.evaluate to fetch the data from INSIDE the browser 
            # This uses the browser's existing cookies and session automatically.
            api_url = "https://pixelsport.tv/backend/livetv/events"
            
            raw_json = await page.evaluate(f"""
                fetch("{api_url}")
                .then(res => res.text())
                .catch(err => "ERROR")
            """)

            if not raw_json or raw_json == "ERROR" or raw_json.strip() == "":
                print("Internal fetch failed, trying direct navigation...")
                await page.goto(api_url, wait_until="networkidle")
                raw_json = await page.locator("body").inner_text()

            # Clean up the string in case there's HTML wrapper stuff
            raw_json = raw_json.strip()
            
            data = json.loads(raw_json)
            events = data.get("events", data) if isinstance(data, dict) else data

            m3u_content = "#EXTM3U\n"
            count = 0
            
            for event in events:
                name = event.get('match_name', 'Unknown Match')
                channel = event.get('channel', {})
                url_s1 = channel.get('server1URL') or event.get('server1URL')
                
                if url_s1 and str(url_s1).lower() != "null":
                    if "hd.bestlive.top:443" in url_s1:
                        url_s1 = url_s1.replace("hd.bestlive.top:443", "hd.pixelhd.online:443")
                    
                    headers = f"|User-Agent={ua}&Referer=https://pixelsport.tv/&Origin=https://pixelsport.tv"
                    m3u_content += f'#EXTINF:-1 group-title="pixelsports",{name}\n'
                    m3u_content += f'#EXTVLCOPT:http-referrer=https://pixelsport.tv\n'
                    m3u_content += f'#EXTVLCOPT:http-user-agent={ua}\n'
                    m3u_content += f'{url_s1}{headers}\n'
                    count += 1

            with open("pixelsports.m3u8", "w", encoding="utf-8") as f:
                f.write(m3u_content)
            
            print(f"Success! Saved {count} matches to pixelsports.m3u8.")

        except Exception as e:
            print(f"Scrape failed: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
