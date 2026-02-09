import json
import asyncio
import logging
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def run():
    async with async_playwright() as p:
        user_data_dir = "/tmp/playwright_session"
        
        # Use a real-looking window size
        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--window-size=1920,1080"
            ]
        )
        
        page = await context.new_page()
        # Apply stealth to this specific page
        await Stealth().apply_stealth_async(page)

        base_url = "https://pixelsport.tv/"
        api_pattern = "/backend/livetv/events"
        api_results = {"data": None}

        async def catch_json(response):
            if api_pattern in response.url and response.status == 200:
                try:
                    api_results["data"] = await response.json()
                except:
                    pass

        page.on("response", catch_json)

        try:
            logging.info("🚀 Navigating to site...")
            await page.goto(base_url, wait_until="domcontentloaded")

            # --- CLOUDFLARE BYPASS ATTEMPT ---
            # 1. Wait a few seconds to see if the challenge appears
            await asyncio.sleep(5) 
            
            # 2. Try to find the Turnstile/Challenge checkbox and click it
            # This looks for the typical Cloudflare challenge containers
            try:
                # Move mouse randomly to look 'human'
                await page.mouse.move(100, 100)
                await asyncio.sleep(1)
                await page.mouse.move(400, 300)

                # Find the Cloudflare iframe if it exists
                frames = page.frames
                for frame in frames:
                    if "cloudflare" in frame.url or "turnstile" in frame.url:
                        logging.info("Found Cloudflare challenge. Attempting to click...")
                        # Click the center of the screen where the box usually is
                        await page.mouse.click(200, 400) 
            except Exception as e:
                logging.info(f"Challenge click skip: {e}")

            # 3. Wait up to 30 seconds for the API to trigger
            for i in range(30):
                if api_results["data"]:
                    logging.info("🎯 API Data captured successfully!")
                    break
                
                # Scroll down slightly to trigger lazy-loaded scripts
                await page.mouse.wheel(0, 500)
                await asyncio.sleep(1)
                
                if i % 5 == 0:
                    logging.info(f"Waiting... ({i}s)")

            if not api_results["data"]:
                # Take a screenshot to see what's happening (check your GitHub artifacts later)
                await page.screenshot(path="blocked.png")
                raise Exception("Blocked by Cloudflare. Check 'blocked.png' in artifacts.")

            # --- SUCCESS: DATA PROCESSING ---
            events = api_results["data"]
            if isinstance(events, dict) and "events" in events:
                events = events["events"]

            filename = f"pixelsports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.m3u8"
            m3u_content = "#EXTM3U\n"
            count = 0

            for event in events:
                name = event.get('match_name', 'Unknown')
                channel = event.get('channel', {})
                url = channel.get('server1URL') or event.get('server1URL')

                if url and str(url).lower() != "null":
                    if "hd.bestlive.top:443" in url:
                        url = url.replace("hd.bestlive.top:443", "hd.pixelhd.online:443")
                    
                    category = channel.get('TVCategory', {}).get('name', 'Sports')
                    m3u_content += f'#EXTINF:-1 group-title="{category}",{name}\n{url}\n'
                    count += 1

            with open(filename, "w", encoding="utf-8") as f:
                f.write(m3u_content)
            logging.info(f"✅ Success! Saved {count} items.")

        finally:
            await context.close()

if __name__ == "__main__":
    asyncio.run(run())
