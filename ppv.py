import asyncio
import os
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
# The specific movie link you provided
TARGET_URL = "https://www.cineby.gd/movie/1426964"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def scrape_cineby(url):
    async with async_playwright() as p:
        # headless=False is needed if running via a virtual display (Xvfb)
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context(user_agent=USER_AGENT, viewport={'width': 1920, 'height': 1080})
        
        # Stealth injection
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = await context.new_page()
        captured_link = None

        # --- ADVANCED SNIFFER ---
        async def handle_request(request):
            nonlocal captured_link
            u = request.url
            
            # Keywords based on your successful example and Cineby's providers
            patterns = [".m3u8", "aW5kZXgubTN1OA==", "techparadise", "frostcomet", "one.tech"]
            
            if any(p in u for p in patterns) and not u.endswith(".ts"):
                if not captured_link:
                    captured_link = u
                    print(f"\n🎯 MANIFEST DETECTED: {u[:85]}...")

        page.on("request", handle_request)

        try:
            print(f"🚀 Opening Cineby: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # 1. Wait for page elements to settle
            await asyncio.sleep(5)

            # 2. Look for the Play Button or Server Button
            # Cineby often has a "Play Now" overlay or a list of servers
            print("🔘 Attempting to trigger the player...")
            play_selectors = [
                "button:has-text('Play')", 
                ".play-button", 
                "#player-iframe",
                "div[class*='PlayButton']"
            ]
            
            for selector in play_selectors:
                try:
                    if await page.is_visible(selector):
                        await page.click(selector)
                        print(f"   Clicked: {selector}")
                        await asyncio.sleep(2)
                except:
                    continue

            # 3. Clean up UI (Overlays/Ads)
            print("🧹 Removing blockers...")
            await page.evaluate("""() => {
                const elements = document.querySelectorAll('div, section, ins');
                for (const el of elements) {
                    const z = parseInt(window.getComputedStyle(el).zIndex);
                    if (z > 100) el.remove();
                }
            }""")

            # 4. The Interaction Loop
            # We click center screen and look for the manifest
            print("🖱️ Simulating player interaction...")
            for i in range(5):
                # Click center of the player area
                await page.mouse.click(960, 540)
                await asyncio.sleep(3)
                if captured_link: break
                print(f"   Polling... {i+1}/5")

            if captured_link:
                print("\n" + "═"*70)
                print("✅ CAPTURE SUCCESS")
                print(f"LINK: {captured_link}")
                print("═"*70)
                
                # Save with Referer (Cineby or Vidsrc depending on source)
                with open("stream.m3u", "w") as f:
                    f.write(f"#EXTM3U\n#EXTVLCOPT:http-referrer={url}\n#EXTINF:-1, Cineby Movie\n{captured_link}")
                print("\n💾 Saved to 'stream.m3u'.")
            else:
                print("\n❌ FAILED: Manifest not found. Check if the video actually loads in a normal browser.")

        except Exception as e:
            print(f"⚠️ Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_cineby(TARGET_URL))
