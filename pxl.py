import json
import asyncio
import re
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        print("Launching browser with enhanced stealth...")
        # Use arguments to help bypass detection in headless mode
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        context = await browser.new_context(
            user_agent=ua,
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = await context.new_page()

        try:
            # 1. Go to the home page first
            print("Warming up on homepage...")
            await page.goto("https://pixelsport.tv/", wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5) 

            # 2. Go directly to the API URL
            print("Navigating to API URL...")
            response = await page.goto("https://pixelsport.tv/backend/livetv/events", wait_until="networkidle")
            
            # Get the raw text
            content = await page.content()
            
            # Use Regex to find the JSON in case it's wrapped in <pre> or <html> tags
            # This looks for anything starting with {"events" or [{"
            match = re.search(r'(\{.*\}|\[.*\])', await page.inner_text("body"))
            
            if match:
                raw_json = match.group(0)
                data = json.loads(raw_json)
            else:
                # Fallback to direct content if regex fails
                raw_json = await page.inner_text("body")
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
            
            print(f"Success! Saved {count} matches.")

        except Exception as e:
            # If it fails, let's see a bit of what it actually saw
            print(f"Scrape failed: {e}")
            try:
                body_peek = await page.inner_text("body")
                print(f"Page content (first 100 chars): {body_peek[:100]}")
            except:
                pass
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
