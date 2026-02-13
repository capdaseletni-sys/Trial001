import asyncio
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
TARGET_URL = "https://pinoymovieshub.org/movies/paddington-in-peru-2024/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def capture_pmh_clean(url):
    async with async_playwright() as p:
        # Running headless=True; if it still fails, the site might require human interaction
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        found_url = None

        async def handle_response(response):
            nonlocal found_url
            u = response.url
            if ".m3u8" in u and not found_url:
                if not u.endswith(".ts"):
                    found_url = u

        page.on("response", handle_response)

        try:
            print(f"🚀 Loading PMH: {url}")
            await page.goto(url, wait_until="networkidle")
            
            # --- STEP 1: Kill the invisible overlays ---
            print("Removing invisible ad-blockers...")
            await page.evaluate("""() => {
                const selectors = ['div[id*="dontfoid"]', 'div[class*="overlay"]', 'div[style*="z-index: 99999"]'];
                selectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => el.remove());
                });
            }""")
            await asyncio.sleep(2)

            # --- STEP 2: Force-Click the Main Server ---
            # Based on your log, the text 'Main' is inside a span. 
            # We use 'force=True' to bypass any remaining pointer interception.
            print("Attempting forced click on 'Main' server...")
            try:
                # Target the specific list item for the Main server
                main_server = page.locator("li:has-text('Main')").first
                await main_server.click(force=True, timeout=10000)
                print("Click successful.")
            except Exception as e:
                print(f"Standard click failed, trying JavaScript click: {e}")
                await page.evaluate("() => { [...document.querySelectorAll('li')].find(el => el.innerText.includes('Main')).click(); }")

            # --- STEP 3: Handle the Player Iframe ---
            print("Waking up the player...")
            await asyncio.sleep(8) 
            
            # Click the player in all frames
            for frame in page.frames:
                try:
                    await frame.click("video, .play-button, #play-btn", force=True, timeout=2000)
                except: pass

            # --- STEP 4: Sniff ---
            for i in range(25):
                if found_url: break
                await asyncio.sleep(1)
                if i % 5 == 0: print(f"Sniffing traffic... {i}s")

            if found_url:
                print(f"\n✅ CAUGHT M3U8: {found_url}")
                with open("pmh_final.m3u", "w") as f:
                    f.write(f"#EXTM3U\n#EXTINF:-1, Paddington in Peru\n{found_url}")
            else:
                print("\n❌ Failed to catch link. The site might be using an encrypted player.")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_pmh_clean(TARGET_URL))
