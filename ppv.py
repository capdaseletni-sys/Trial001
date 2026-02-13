import asyncio
from playwright.async_api import async_playwright

TEST_MOVIE_URL = "https://tv13.lk21official.life/disco-dancer-1982/" 
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def capture_turbovip_stream(url):
    async with async_playwright() as p:
        # headless=False helps you see if a popup ad blocks the click
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        
        found_url = None

        # Network sniffer for the manifest
        async def handle_response(response):
            nonlocal found_url
            u = response.url
            # Filter for playlist files
            if (".m3u8" in u or "playlist.m3u8" in u) and not found_url:
                if not u.endswith(".ts"): # Avoid video segments
                    found_url = u

        page.on("response", handle_response)

        try:
            print(f"🚀 Navigating to: {url}")
            await page.goto(url, wait_until="domcontentloaded")
            
            # --- STEP 1: Select the TURBOVIP Server ---
            print("Searching for TURBOVIP server button...")
            await asyncio.sleep(5) # Allow page scripts to load tabs
            
            # Try to click TurboVIP by text
            turbovip_btn = page.get_by_text("TURBOVIP", exact=False)
            
            if await turbovip_btn.is_visible():
                print("Found TURBOVIP button. Clicking...")
                await turbovip_btn.click()
                # Switching servers reloads the iframe
                await asyncio.sleep(6) 
            else:
                print("⚠️ TURBOVIP button not found directly. Scanning all elements...")
                # Fallback: Find links containing 'TURBO'
                all_links = await page.query_selector_all("a, li, span")
                for link in all_links:
                    text = await link.inner_text()
                    if "TURBO" in text.upper():
                        print(f"Clicking match: {text}")
                        await link.click()
                        await asyncio.sleep(6)
                        break

            # --- STEP 2: Trigger the Player ---
            print("Attempting to trigger play on TurboVIP player...")
            # Brute force click on video area in all frames
            for frame in page.frames:
                try:
                    await frame.click("video", force=True, timeout=1000)
                except: pass
            
            await page.mouse.click(640, 360) # Main page fallback click

            # --- STEP 3: Capture ---
            for i in range(25):
                if found_url: break
                await asyncio.sleep(1)
                if i % 5 == 0: print(f"Sniffing network traffic... ({i}s)")

            if found_url:
                print(f"\n✅ TURBOVIP STREAM CAUGHT:\n{found_url}")
            else:
                print("\n❌ Failed to capture TurboVIP. It might be hidden in a Blob or the server is busy.")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_turbovip_stream(TEST_MOVIE_URL))
