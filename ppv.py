import asyncio
from playwright.async_api import async_playwright

TARGET_URL = "https://www.cineby.gd/movie/1426964"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def scrape_cineby_with_play_click(url):
    async with async_playwright() as p:
        # Running in headed mode via xvfb-run
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context(user_agent=USER_AGENT, viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        captured_link = None

        async def handle_request(request):
            nonlocal captured_link
            u = request.url
            if (".m3u8" in u or "aW5kZXgubTN1OA==" in u) and not u.endswith(".ts"):
                if not captured_link:
                    captured_link = u
                    print(f"🎯 MANIFEST CAPTURED: {u}")

        page.on("request", handle_request)

        try:
            print(f"🚀 Navigating to Cineby...")
            await page.goto(url, wait_until="networkidle")
            
            # 1. Target the 'Play' button from your screenshot
            print("🔘 Clicking the 'Play' button...")
            # We use a robust selector that looks for the 'Play' text inside a button
            play_btn = page.get_by_role("button", name="Play")
            
            if await play_btn.is_visible():
                await play_btn.click()
                print("✅ Clicked main Play button.")
            else:
                # Fallback: Click the exact coordinates if the selector fails
                print("⚠️ Play button not found by text, trying coordinate click...")
                await page.mouse.click(80, 735) # Based on standard layout for that button position

            # 2. Wait for the player to swap in
            print("⏳ Waiting for player to load and handshake...")
            await asyncio.sleep(10)

            # 3. Handle secondary 'Play' inside the player iframe
            # Often, after clicking the site 'Play', the actual player iframe has its own button
            frames = page.frames
            for frame in frames:
                try:
                    # Click center of all frames to bypass 'click-to-play' overlays
                    await frame.click("body", position={"x": 500, "y": 300}, timeout=2000, force=True)
                except:
                    continue

            # 4. Final Polling
            for i in range(20):
                if captured_link: break
                await asyncio.sleep(1)

            # 5. Debug Screenshot
            await page.screenshot(path="debug.png")
            print("📸 Debug screenshot saved as 'debug.png'")

            if captured_link:
                with open("stream.m3u", "w") as f:
                    f.write(f"#EXTM3U\n#EXTVLCOPT:http-referrer={url}\n{captured_link}")
                print("💾 SUCCESS: stream.m3u created.")
            else:
                print("❌ FAILED: No m3u8 detected. Check debug.png to see what happened.")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_cineby_with_play_click(TARGET_URL))
