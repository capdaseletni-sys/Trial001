import asyncio
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
TARGET_URL = "https://pinoymovieshub.org/movies/paddington-in-peru-2024/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def capture_pmh_stream(url):
    async with async_playwright() as p:
        # headless=False is recommended here so you can see if it gets stuck on an ad
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        found_url = None

        # Network interceptor
        async def handle_response(response):
            nonlocal found_url
            u = response.url
            # PinoyMoviesHub servers often use 'master.m3u8' or 'index.m3u8'
            if ".m3u8" in u and not found_url:
                if not u.endswith(".ts"):
                    found_url = u

        page.on("response", handle_response)

        try:
            print(f"🚀 Loading PMH: {url}")
            await page.goto(url, wait_until="load")
            
            # --- STEP 1: Handle Popups and Select Main Server ---
            print("Looking for 'Main Server' button...")
            await asyncio.sleep(5) 

            # Target the server list. PMH usually uses a list of buttons.
            # We look for 'Main' or 'Server 1'
            server_btn = page.get_by_role("link", name="Main", exact=True).first
            
            if await server_btn.is_visible():
                print("Clicking Main Server...")
                # Start waiting for a popup to appear when we click
                async with page.expect_popup() as popup_info:
                    await server_btn.click()
                
                # Close the popup immediately if it opens
                ad_popup = await popup_info.value
                await ad_popup.close()
                print("Closed ad popup.")
            else:
                print("⚠️ Main server button not found by role. Attempting generic click.")
                await page.click("text='Main'")

            # --- STEP 2: Play the Video ---
            print("Waking up the player iframe...")
            await asyncio.sleep(8) # Wait for iframe to load

            # In PMH, the player is usually a play button in the middle of the iframe
            for frame in page.frames:
                try:
                    # Look for play buttons
                    await frame.click(".play-button, #play-btn, video", timeout=2000)
                    print("Clicked internal play button.")
                except:
                    pass

            # --- STEP 3: Sniff ---
            print("Sniffing network traffic...")
            for i in range(30):
                if found_url: break
                await asyncio.sleep(1)
                if i % 10 == 0: print(f"Searching... {i}s")

            if found_url:
                print("\n" + "="*50)
                print("✅ CAPTURED LINK:")
                print(found_url)
                print("="*50)
                
                with open("pmh_stream.m3u", "w") as f:
                    f.write(f"#EXTM3U\n#EXTINF:-1, Paddington in Peru\n{found_url}")
            else:
                print("\n❌ Failed. The server may be using an encrypted HLS blob.")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_pmh_stream(TARGET_URL))
