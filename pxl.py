import json
import asyncio
from playwright.async_api import async_playwright
import playwright_stealth

async def run():
    # Centralized User-Agent
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    
    async with async_playwright() as p:
        # Launching browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        
        # Use the module-level function call to avoid 'ImportError' or 'not callable'
        await playwright_stealth.stealth(page)
        
        url = "https://pixelsport.tv/backend/livetv/events"
        
        try:
            print("Warming up...")
            # Navigate to home first to set cookies/session
            await page.goto("https://pixelsport.tv/", wait_until="domcontentloaded")
            await asyncio.sleep(3) 

            print(f"Fetching data from API...")
            response = await page.goto(url)
            
            if response.status != 200:
                print(f"Failed to fetch data. Status: {response.status}")
                return

            data = await response.json()
            events = data.get("events", data) if isinstance(data, dict) else data

            m3u_content = "#EXTM3U\n"
            count = 0
            
            if isinstance(events, list):
                for event in events:
                    name = event.get('match_name', 'Unknown Match')
                    channel = event.get('channel', {})
                    
                    # Check both channel and top-level event object for URLs
                    servers = [
                        {"label": "S1", "url": channel.get('server1URL') or event.get('server1URL')},
                        {"label": "S2", "url": channel.get('server2URL') or event.get('server2URL')}
                    ]
                    
                    for server in servers:
                        srv_url = server["url"]
                        srv_label = server["label"]
                        
                        if srv_url and str(srv_url).lower() != "null" and str(srv_url).strip() != "":
                            # Domain Replacement Logic
                            if "hd.bestlive.top:443" in srv_url:
                                srv_url = srv_url.replace("hd.bestlive.top:443", "hd.pixelhd.online:443")
                            
                            # Construct M3U entry
                            m3u_content += f'#EXTINF:-1 group-title="pixelsports",{name} [{srv_label}]\n'
                            m3u_content += f'#EXTVLCOPT:http-referrer=https://pixelsport.tv/\n'
                            m3u_content += f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n'
                            m3u_content += f'{srv_url}\n'
                            count += 1

            # Save the generated playlist
            with open("pixelsports.m3u8", "w", encoding="utf-8") as f:
                f.write(m3u_content)
            
            print(f"Success! Saved {count} stream links to pixelsports.m3u8.")

        except Exception as e:
            print(f"Scrape failed: {e}")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
