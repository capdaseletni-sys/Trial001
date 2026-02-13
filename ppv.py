import asyncio
from playwright.async_api import async_playwright

TARGET_URL = "https://www.cineby.gd/movie/1426964"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def scrape_cineby_fixed(url):
    async with async_playwright() as p:
        # Added --disable-gpu to fix the white screen issue in CI/Xvfb
        browser = await p.chromium.launch(
            headless=False, 
            args=["--disable-gpu", "--disable-software-rasterizer"]
        ) 
        
        context = await browser.new_context(user_agent=USER_AGENT, viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        captured_link = None

        async def handle_request(request):
            nonlocal captured_link
            u = request.url
            if (".m3u8" in u or "aW5kZXgubTN1OA==" in u) and not u.endswith(".ts"):
                if not captured_link:
                    captured_link = u
                    print(f"🎯 LINK FOUND: {u[:80]}")

        page.on("request", handle_request)

        try:
            print("🚀 Navigating... waiting for full load...")
            # Use 'networkidle' to ensure all elements/ads are loaded
            await page.goto(url, wait_until="networkidle", timeout=90000)
            
            # Wait extra time for the UI to actually render on the virtual screen
            await asyncio.sleep(5)
            
            # Take a "pre-click" screenshot to see if it's still white
            await page.screenshot(path="pre_click.png")

            # Click the Play button by text for better accuracy
            print("🔘 Clicking Play...")
            try:
                # wait_for_selector ensures the button is present before clicking
                await page.wait_for_selector("button:has-text('Play')", timeout=10000)
                await page.get_by_role("button", name="Play").click()
            except:
                print("⚠️ Play button selector failed, using coordinate click...")
                await page.mouse.click(80, 735)

            # Wait for sniffing
            await asyncio.sleep(15)
            
            # Final debug screenshot
            await page.screenshot(path="debug.png")

            if captured_link:
                with open("stream.m3u", "w") as f:
                    f.write(f"#EXTM3U\n#EXTVLCOPT:http-referrer={url}\n{captured_link}")
                print("✅ stream.m3u created.")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_cineby_fixed(TARGET_URL))
