import asyncio
from playwright.async_api import async_playwright

TEST_MOVIE_URL = "https://tv13.lk21official.life/disco-dancer-1982/" 
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def capture_p2p_stream(url):
    async with async_playwright() as p:
        # headless=False is recommended for the first run to see if it clicks the right button
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        
        found_url = None

        # Listen for the manifest file
        async def handle_response(response):
            nonlocal found_url
            u = response.url
            if ".m3u8" in u and not found_url:
                if "master" in u or "index" in u or "playlist" in u:
                    found_url = u

        page.on("response", handle_response)

        try:
            print(f"🚀 Loading page: {url}")
            await page.goto(url, wait_until="domcontentloaded")
            
            # --- STEP 1: Select the P2P Server ---
            print("Searching for P2P server button...")
            await asyncio.sleep(5) # Wait for the UI to load server tabs
            
            # We look for a link or button that contains the text "P2P"
            p2p_button = page.get_by_text("P2P", exact=True)
            
            if await p2p_button.is_visible():
                print("Found P2P button. Clicking...")
                await p2p_button.click()
                # Clicking a server usually reloads the player iframe
                await asyncio.sleep(5) 
            else:
                print("⚠️ P2P button not found via direct text. Checking all links...")
                # Fallback: find any link with P2P in the text or title
                links = await page.query_selector_all("a")
                for link in links:
                    text = await link.inner_text()
                    if "P2P" in text.upper():
                        print(f"Found match: {text}. Clicking...")
                        await link.click()
                        await asyncio.sleep(5)
                        break

            # --- STEP 2: Trigger the Video ---
            print("Attempting to trigger play on the P2P player...")
            # Often, clicking the center of the player area is required after switching servers
            await page.mouse.click(640, 360) 

            # --- STEP 3: Capture ---
            for i in range(25):
                if found_url: break
                await asyncio.sleep(1)
                if i % 5 == 0: print(f"Sniffing network... ({i}s)")

            if found_url:
                print(f"\n✅ P2P STREAM CAPTURED:\n{found_url}")
            else:
                print("\n❌ Failed to capture. P2P server might be down or require manual captcha.")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_p2p_stream(TEST_MOVIE_URL))
