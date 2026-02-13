import asyncio
from playwright.async_api import async_playwright

TARGET_URL = "https://www.cineby.gd/movie/1426964"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def scrape_cineby_advanced(url):
    async with async_playwright() as p:
        # Use headless=False with xvfb-run for best results
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context(user_agent=USER_AGENT, viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        captured_link = None

        async def handle_request(request):
            nonlocal captured_link
            u = request.url
            # Sniffing for the specific Base64 pattern or m3u8 extension
            if (".m3u8" in u or "aW5kZXgubTN1OA==" in u) and not u.endswith(".ts"):
                if not captured_link:
                    captured_link = u
                    print(f"🎯 SUCCESS! Captured Manifest: {u[:80]}...")

        page.on("request", handle_request)

        try:
            print(f"🚀 Navigating to Cineby...")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(7) # Give time for the UI to load

            # 1. Click a "Server" button if present
            print("🔘 Checking for Server buttons...")
            servers = page.locator("button:has-text('Server'), .server-item")
            if await servers.count() > 0:
                await servers.first.click()
                await asyncio.sleep(3)

            # 2. Identify and Click inside IFRAMES
            print("🕵️ Locating player frames...")
            frames = page.frames
            print(f"   Found {len(frames)} frames. Attempting internal clicks...")

            for frame in frames:
                try:
                    # We try to click the center of every frame to trigger the hidden play logic
                    # Pirate players are often nested 2-3 levels deep
                    await frame.click("body", position={"x": 960/2, "y": 540/2}, timeout=2000, force=True)
                    print(f"   Clicked inside frame: {frame.name or 'unnamed'}")
                except:
                    continue

            # 3. Fallback: Center-page click
            await page.mouse.click(960, 540)

            # 4. Wait for the sniffer
            for i in range(25):
                if captured_link: break
                await asyncio.sleep(1)

            if captured_link:
                with open("stream.m3u", "w") as f:
                    f.write(f"#EXTM3U\n#EXTVLCOPT:http-referrer={url}\n{captured_link}")
                print("✅ File 'stream.m3u' generated.")
            else:
                print("❌ Still no manifest. The provider may be using a 'Click to Play' overlay that needs specific targeting.")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_cineby_advanced(TARGET_URL))
