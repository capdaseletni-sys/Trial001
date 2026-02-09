import json
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def run():
    stealth = Stealth()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        await stealth.apply_stealth_async(context)
        page = await context.new_page()
        
        url = "https://pixelsport.tv/backend/livetv/events"
        
        try:
            print("Warming up...")
            await page.goto("https://pixelsport.tv/", wait_until="networkidle")
            await asyncio.sleep(5) 

            print(f"Fetching data from API...")
            await page.goto(url, wait_until="domcontentloaded")

            try:
                raw_json = await page.locator("pre").inner_text(timeout=5000)
            except:
                raw_json = await page.locator("body").inner_text()

            data = json.loads(raw_json)
            events = data.get("events", data) if isinstance(data, dict) else data

            m3u_content = "#EXTM3U\n"
            count = 0
            
            for event in events:
                name = event.get('match_name', 'Unknown Match')
                channel = event.get('channel', {})
                url_s1 = channel.get('server1URL') or event.get('server1URL')
                
                if url_s1 and url_s1 != "null":
                    # --- DOMAIN REPLACEMENT LOGIC ---
                    if "hd.bestlive.top:443" in url_s1:
                        url_s1 = url_s1.replace("hd.bestlive.top:443", "hd.pixelhd.online:443")
                    # --------------------------------
                    
                    # GROUP CHANGED TO "pixelsports"
                    m3u_content += f'#EXTINF:-1 group-title="pixelsports",{name}\n'
                    # --- VLC OPTIONS ---
                    m3u_content += f'#EXTVLCOPT:http-referrer=https://pixelsport.tv\n'
                    m3u_content += f'#EXTVLCOPT:http-origin=https://pixelsport.tv\n'
                    m3u_content += f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0\n'
                    # -------------------
                    m3u_content += f'{url_s1}\n'
                    count += 1

            with open("pixelsports.m3u8", "w", encoding="utf-8") as f:
                f.write(m3u_content)
            
            print(f"Success! {count} matches saved to pixelsports.m3u8 with domain updates.")

        except Exception as e:
            print(f"Scrape failed: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
