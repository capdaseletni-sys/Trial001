import asyncio
from playwright.async_api import async_playwright

TEST_MOVIE_URL = "https://tv13.lk21official.life/disco-dancer-1982/" 
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def capture_m3u8_advanced(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        
        found_url = None

        # Using 'on response' is often more reliable for catching redirects
        async def handle_response(response):
            nonlocal found_url
            u = response.url
            if ".m3u8" in u and not found_url:
                if not u.endswith(".ts"): # Skip segments
                    found_url = u

        page.on("response", handle_response)

        try:
            print(f"Loading page: {url}")
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # 1. Wait for any 'I am not a bot' or overlay to vanish
            await asyncio.sleep(5)

            # 2. Strategy: Click every iframe on the page
            # Movie sites often nest the real player 2-3 levels deep
            frames = page.frames
            print(f"Found {len(frames)} nested frames. Attempting to trigger player...")
            
            for frame in frames:
                try:
                    # Look for play buttons or common player IDs
                    await frame.click("video", timeout=1000, force=True)
                except:
                    try:
                        # Fallback: Click the center of every frame
                        await frame.click("body", timeout=1000, force=True)
                    except:
                        continue

            # 3. Final brute-force click on the main page center
            await page.mouse.click(640, 360)

            # 4. Extended polling
            for i in range(30):
                if found_url: break
                await asyncio.sleep(1)
                if i % 5 == 0: print(f"Polling network traffic... ({i}s)")

            if found_url:
                print(f"\n✅ SUCCESS! STREAM CAUGHT:\n{found_url}\n")
            else:
                print("\n❌ Failed. The site might require a 'Server' selection click first.")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_m3u8_advanced(TEST_MOVIE_URL))
