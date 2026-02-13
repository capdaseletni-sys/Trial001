import asyncio
import random
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
TARGET_URL = "https://tv13.lk21official.life/disco-dancer-1982/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def capture_cast_m3u8(url):
    async with async_playwright() as p:
        # Running headless=True. If this fails, switch to False to bypass potential captchas.
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        found_url = None

        # Network interceptor for M3U8 manifest
        async def handle_response(response):
            nonlocal found_url
            u = response.url
            # Filter for playlist/manifest files, ignoring individual video chunks (.ts)
            if (".m3u8" in u or "playlist" in u or "master" in u) and not found_url:
                if not u.endswith(".ts"):
                    found_url = u

        page.on("response", handle_response)

        try:
            print(f"🚀 Loading page: {url}")
            # Wait for the DOM to be ready
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # --- STEP 1: Select the CAST Server ---
            print("Searching for CAST server link...")
            await asyncio.sleep(5) # Allow UI to render tabs
            
            # Using .nth(0) to resolve Strict Mode Violation if multiple CAST elements exist
            cast_btn = page.get_by_role("link", name="CAST", exact=True).nth(0)
            
            if await cast_btn.is_visible():
                print("Found CAST button. Clicking...")
                await cast_btn.click()
                # CAST often takes a moment to swap the iframe source
                await asyncio.sleep(8) 
            else:
                print("⚠️ CAST button not found by role. Trying direct text search...")
                await page.get_by_text("CAST").first.click()
                await asyncio.sleep(8)

            # --- STEP 2: Trigger the Video Player ---
            print("Attempting to wake up the player...")
            # Brute-force click on the player area in all frames
            for frame in page.frames:
                try:
                    # Target common player play buttons
                    play_icon = await frame.query_selector(".vjs-big-play-button, .play-button, video")
                    if play_icon:
                        await play_icon.click(force=True, timeout=1000)
                except:
                    pass
            
            # Main page fallback click
            await page.mouse.click(640, 360)

            # --- STEP 3: Sniff Traffic ---
            print("Intercepting network traffic (30s window)...")
            for i in range(30):
                if found_url: break
                await asyncio.sleep(1)
                if i % 10 == 0: print(f"Sniffing... {i}s")

            if found_url:
                print("\n" + "="*50)
                print("✅ CAST STREAM CAPTURED!")
                print(f"URL: {found_url}")
                print("="*50)
                
                # Create the playlist entry
                title = await page.title()
                m3u_entry = (
                    f'#EXTM3U\n'
                    f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n'
                    f'#EXTVLCOPT:http-referrer={url}\n'
                    f'#EXTINF:-1, {title}\n'
                    f'{found_url}'
                )
                
                with open("movie_cast.m3u", "w", encoding="utf-8") as f:
                    f.write(m3u_entry)
                print("Saved to: movie_cast.m3u")
            else:
                print("\n❌ CAST server failed to provide a visible .m3u8 link.")
                print("The site may be using session-tokens or blob storage.")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_cast_m3u8(TARGET_URL))
