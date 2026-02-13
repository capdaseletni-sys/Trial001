import asyncio
import random
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
TARGET_URL = "https://tv13.lk21official.life/disco-dancer-1982/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def capture_deep_stream(url):
    async with async_playwright() as p:
        # headless=True is fine, but for persistent fails, try False once to check for Captchas
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        found_url = None

        # Deep Network Listener
        async def handle_response(response):
            nonlocal found_url
            u = response.url
            # TurboVIP often uses 'playlist.m3u8' or a 'master.m3u8' inside playeriframe.sbs
            if (".m3u8" in u or "playlist" in u) and not found_url:
                if not u.endswith(".ts"):
                    found_url = u

        page.on("response", handle_response)

        try:
            print(f"🚀 Loading Main Page: {url}")
            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(5)

            # --- STEP 1: Select TURBOVIP link specifically ---
            print("Selecting TURBOVIP server...")
            # Using nth(0) handles the multiple elements error
            turbovip = page.get_by_role("link", name="TURBOVIP", exact=True).nth(0)
            if await turbovip.is_visible():
                await turbovip.click()
                print("Clicked TURBOVIP. Waiting for iframe handshake...")
                await asyncio.sleep(8) 
            else:
                print("❌ Could not find the TURBOVIP link.")
                return

            # --- STEP 2: Find and Click Player ---
            # Most players hide behind multiple <iframe> layers. 
            # We will click every visible 'play' icon or video tag.
            for frame in page.frames:
                try:
                    # Look for the big play button often found in Video.js or Plyr
                    play_btn = await frame.query_selector(".vjs-big-play-button, .plyr__control--overlaid")
                    if play_btn:
                        await play_btn.click()
                        print("Clicked internal play button.")
                except:
                    pass

            # Final brute-force click in the center
            await page.mouse.click(640, 360)

            # --- STEP 3: Capturing the link ---
            print("Sniffing network traffic (this can take 30s)...")
            for i in range(35):
                if found_url: break
                await asyncio.sleep(1)
                if i % 10 == 0: print(f"Still searching... {i}s")

            if found_url:
                print(f"\n✅ CAUGHT STREAM URL:\n{found_url}")
                # Save to M3U
                entry = f"#EXTM3U\n#EXTINF:-1, Disco Dancer (TurboVIP)\n{found_url}"
                with open("disco_dancer.m3u", "w") as f:
                    f.write(entry)
            else:
                print("\n❌ Failed. The link might be a Blob or session-locked.")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_deep_stream(TARGET_URL))
