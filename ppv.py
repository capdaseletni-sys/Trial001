import asyncio
import os
from playwright.async_api import async_playwright

TARGET_URL = "https://www.cineby.gd/movie/1426964"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def scrape_cineby(url):
    async with async_playwright() as p:
        # Switching to headless=True for CI environments like GitHub Actions
        # If you use xvfb-run, you can switch this back to False
        browser = await p.chromium.launch(headless=True) 
        
        context = await browser.new_context(
            user_agent=USER_AGENT, 
            viewport={'width': 1920, 'height': 1080}
        )
        
        # Inject stealth to pretend we aren't a bot
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = await context.new_page()
        captured_link = None

        async def handle_request(request):
            nonlocal captured_link
            u = request.url
            # Broadened pattern to catch the techparadise/frostcomet style links
            if (".m3u8" in u or "aW5kZXgubTN1OA==" in u) and not u.endswith(".ts"):
                if not captured_link:
                    captured_link = u
                    print(f"\n🎯 FOUND: {u[:70]}...")

        page.on("request", handle_request)

        try:
            print(f"🚀 Starting scrape on {url}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            await asyncio.sleep(8) # Wait for provider to load

            # Click center of screen to trigger player
            print("🖱️ Clicking player area...")
            await page.mouse.click(960, 540)
            
            # Wait for sniffing
            for i in range(20):
                if captured_link: break
                await asyncio.sleep(1)

            if captured_link:
                with open("stream.m3u", "w") as f:
                    f.write(f"#EXTM3U\n#EXTVLCOPT:http-referrer={url}\n#EXTINF:-1, Cineby\n{captured_link}")
                print("✅ Successfully saved stream.m3u")
            else:
                print("❌ Failed to capture m3u8.")

        except Exception as e:
            print(f"⚠️ Runtime Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_cineby(TARGET_URL))
