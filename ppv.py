import asyncio
import os
import random
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
IMDB_ID = "tt16500624" 
TARGET_URL = f"https://vidsrc.me/embed/movie?imdb={IMDB_ID}"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def scrape_vidsrc_final(url):
    async with async_playwright() as p:
        # Check if we are in a GitHub Runner or similar environment
        is_ci = os.environ.get("GITHUB_ACTIONS") == "true"
        
        # If in CI, we MUST use headless=True. Locally, you can change to False.
        browser = await p.chromium.launch(headless=True if is_ci else False) 
        
        # Create a context with a realistic viewport
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1280, 'height': 720}
        )
        
        # Stealth: Remove the "automated" flag
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = await context.new_page()
        captured_link = None

        # Network Sniffer
        async def handle_request(request):
            nonlocal captured_link
            u = request.url
            # Catching the neonhorizon or any m3u8 master manifest
            if ("neonhorizonworkshops.com" in u or "master.m3u8" in u) and not captured_link:
                if not u.endswith(".ts"):
                    captured_link = u

        page.on("request", handle_request)

        try:
            print(f"🚀 Initializing on {'CI Server' if is_ci else 'Local Machine'}")
            print(f"🔗 Target: {url}")
            
            # Navigate with a generous timeout
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            # 1. Human-like interaction (crucial for headless success)
            print("Performing stealth movements...")
            await page.mouse.move(100, 100)
            await asyncio.sleep(1)
            await page.mouse.move(400, 300)

            # 2. Click the player to start the handshake
            print("Triggering player...")
            # We click multiple times in case of overlays
            await page.mouse.click(640, 360) 
            await asyncio.sleep(2)
            await page.mouse.click(640, 360) 

            # 3. Wait for the sniffer
            print("Sniffing background traffic...")
            for i in range(30):
                if captured_link: break
                await asyncio.sleep(1)
                if i % 10 == 0: print(f"Polling... {i}s")

            if captured_link:
                print(f"\n✅ CAPTURED: {captured_link}")
                
                # Save to M3U file
                filename = "playlist.m3u"
                with open(filename, "w") as f:
                    f.write(f"#EXTM3U\n#EXTVLCOPT:http-referrer=https://vidsrc.me/\n#EXTINF:-1, Movie\n{captured_link}")
                print(f"📁 File saved: {filename}")
            else:
                print("\n❌ Failed: No manifest found. VidSrc may have blocked the headless session.")

        except Exception as e:
            print(f"⚠️ Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_vidsrc_final(TARGET_URL))
