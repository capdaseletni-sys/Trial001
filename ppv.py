import asyncio
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
# Replace this with the specific movie page you want to test
TEST_MOVIE_URL = " https://tv13.lk21official.life/disco-dancer-1982/" 
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0"
REFERRER = "https://tv13.lk21official.life/"

async def capture_single_m3u8(url):
    async with async_playwright() as p:
        # Launch browser (headless=False if you want to see what's happening)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        
        found_m3u8 = None

        # This listener 'catches' every network request the browser makes
        def handle_request(request):
            nonlocal found_m3u8
            # Look for m3u8 in the URL but ignore individual chunks (.ts files)
            if ".m3u8" in request.url and not found_m3u8:
                if not request.url.endswith(".ts"):
                    found_m3u8 = request.url

        page.on("request", handle_request)

        try:
            print(f"Opening: {url}")
            await page.goto(url, wait_until="load", timeout=60000)
            
            # 1. Extract the Movie Title
            title = await page.title()
            print(f"Title detected: {title}")

            # 2. Wait for the player to initialize
            print("Waiting for player to load (10 seconds)...")
            await asyncio.sleep(10)

            # 3. Simulate a click on the player
            # We click the center of the screen where the 'Play' button usually sits
            print("Clicking play...")
            await page.mouse.click(640, 360) 
            
            # 4. Wait for the background traffic to show the m3u8
            print("Intercepting network...")
            for _ in range(20):
                if found_m3u8: break
                await asyncio.sleep(1)

            if found_m3u8:
                print("\n" + "="*30)
                print("✅ CAPTURED SUCCESSFULLY!")
                print("="*30)
                outcome = (
                    f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n'
                    f'#EXTVLCOPT:http-referrer={REFERRER}\n'
                    f'#EXTINF:-1 group-title="Movies", {title}\n'
                    f'{found_m3u8}'
                )
                print(outcome)
                print("="*30)
                
                # Save to a temporary test file
                with open("test_result.m3u", "w") as f:
                    f.write("#EXTM3U\n\n" + outcome)
            else:
                print("❌ Failed to capture m3u8. The link might be protected or requires a different server.")

        except Exception as e:
            print(f"Error during capture: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_single_m3u8(TEST_MOVIE_URL))
