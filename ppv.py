import asyncio
from playwright.async_api import async_playwright

async def capture_p2p_advanced(url):
    async with async_playwright() as p:
        # Switch to headless=False to see if a CAPTCHA appears!
        browser = await p.chromium.launch(headless=True) 
        context = await browser.new_context()
        page = await context.new_page()
        
        found_url = None

        async def handle_response(response):
            nonlocal found_url
            # Broaden search: look for 'm3u', 'playlist', or 'chunklist' 
            # and content-type 'application/vnd.apple.mpegurl' or 'video/mp2t'
            u = response.url
            headers = response.headers
            content_type = headers.get("content-type", "")

            if (".m3u8" in u or "playlist" in u) and "application/vnd.apple.mpegurl" in content_type:
                if not u.endswith(".ts") and not found_url:
                    found_url = u
            
        page.on("response", handle_response)

        try:
            print(f"Opening Movie: {url}")
            await page.goto(url, wait_until="networkidle")
            
            # Click P2P - using a more robust selector
            print("Selecting P2P Server...")
            await page.get_by_text("P2P", exact=True).click()
            await asyncio.sleep(8) # P2P needs time to 'bootstrap' peers

            # Brute force 'Play' click on all frames
            for frame in page.frames:
                try:
                    await frame.click("video", timeout=500, force=True)
                    await frame.click(".vjs-big-play-button", timeout=500, force=True)
                except: pass

            print("Waiting for P2P handshake and manifest...")
            for i in range(40): # Wait up to 40s
                if found_url: break
                await asyncio.sleep(1)
                
            if found_url:
                print(f"\n✅ CAPTURED P2P MANIFEST: {found_url}")
            else:
                print("\n❌ Failed. The P2P server might be using Blob/WebRTC which can't be put in an M3U.")

        finally:
            await browser.close()

# Run it
# asyncio.run(capture_p2p_advanced("https://tv13.lk21official.life/disco-dancer-1982/"))
