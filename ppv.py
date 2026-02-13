import asyncio
import os
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
IMDB_ID = "tt16500624" 
TARGET_URL = f"https://vidsrc.me/embed/movie?imdb={IMDB_ID}"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def scrape_vidsrc_optimized(url):
    async with async_playwright() as p:
        # Launching with headless=False is crucial for 'headed' simulation via Xvfb
        browser = await p.chromium.launch(headless=False) 
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
        )
        
        # Inject stealth script to bypass basic detection
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = await context.new_page()
        captured_link = None

        # --- BROADENED REQUEST SNIFFER ---
        async def handle_request(request):
            nonlocal captured_link
            u = request.url
            
            # Look for common patterns: .m3u8 extension or known CDN keywords
            # Added check for 'techparadise' and 'frostcomet' patterns
            is_manifest = ".m3u8" in u.lower() or "aW5kZXgubTN1OA==" in u
            is_not_segment = not u.endswith(".ts")
            
            if is_manifest and is_not_segment and not captured_link:
                # Exclude obvious ad/tracker noise
                if "google" not in u and "doubleclick" not in u:
                    captured_link = u
                    print(f"\n🎯 FOUND TARGET: {u[:80]}...")

        page.on("request", handle_request)

        try:
            print(f"🚀 Navigating to: {url}")
            # Networkidle is risky on ad-heavy sites, but good for catching initial loads
            await page.goto(url, wait_until="domcontentloaded")
            
            # 1. Wait for the player/iframe to load
            print("⏳ Waiting for player initialization (10s)...")
            await asyncio.sleep(10)

            # 2. Aggressive Overlay Removal (Clearing the path for clicks)
            print("🧹 Deleting invisible blocker overlays...")
            await page.evaluate("""() => {
                const blockers = document.querySelectorAll('div, section, ins');
                blockers.forEach(el => {
                    const style = window.getComputedStyle(el);
                    const z = parseInt(style.zIndex);
                    // Remove high z-index layers and fixed/absolute position ads
                    if (z > 100 || style.position === 'fixed') {
                        el.remove();
                    }
                });
            }""")

            # 3. Simulation: The Handshake Clicks
            # We click the center of the screen multiple times to trigger the player logic
            print("🖱️ Performing interaction handshake...")
            for i in range(4):
                print(f"   Clicking player... ({i+1}/4)")
                await page.mouse.click(960, 540) 
                await asyncio.sleep(2) # Wait for potential popups to trigger/be blocked

            # 4. Final Sniffing Window
            print("🕵️ Sniffing background traffic for manifest...")
            for i in range(30):
                if captured_link: break
                await asyncio.sleep(1)
                if i % 10 == 0: print(f"   Searching... {i}s")

            if captured_link:
                print("\n" + "="*70)
                print("✅ CAPTURE SUCCESSFUL")
                print(f"URL: {captured_link}")
                print("="*70)
                
                # Create the local M3U file with necessary headers
                with open("stream.m3u", "w") as f:
                    # Referer is essential for bypass on techparadise/vidsrc
                    f.write(f"#EXTM3U\n#EXTVLCOPT:http-referrer=https://vidsrc.me/\n#EXTINF:-1, Scraped Movie\n{captured_link}")
                print("\n💾 Saved to 'stream.m3u'. Use VLC to play.")
            else:
                print("\n❌ FAILED: No .m3u8 detected. The site might require a manual Captcha solve.")

        except Exception as e:
            print(f"⚠️ Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_vidsrc_optimized(TARGET_URL))
