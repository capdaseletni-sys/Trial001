import asyncio
import os
import random
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
IMDB_ID = "tt16500624" # Paddington in Peru
TARGET_URL = f"https://vidsrc.me/embed/movie?imdb={IMDB_ID}"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def scrape_and_save_playlist(url):
    async with async_playwright() as p:
        # headless=False allows you to manually solve any "Verify You Are Human" boxes
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context(user_agent=USER_AGENT)
        
        # Hide Playwright fingerprint
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = await context.new_page()
        captured_link = None

        # Network Sniffer
        async def handle_request(request):
            nonlocal captured_link
            u = request.url
            # Filter for the specific CDN or master manifest patterns
            if ("neonhorizonworkshops.com" in u or ".m3u8" in u) and not captured_link:
                if not u.endswith(".ts"): # Ignore individual video segments
                    captured_link = u

        page.on("request", handle_request)

        try:
            print(f"🚀 Launching Stealth Browser at: {url}")
            await page.goto(url, wait_until="domcontentloaded")
            
            # Allow time for initial ads/checks to load
            await asyncio.sleep(random.uniform(5, 8))

            # 1. Clean the 'Invisible' Ad Layer
            print("Removing ad overlays...")
            await page.evaluate("""() => {
                document.querySelectorAll('div').forEach(el => {
                    if (parseInt(window.getComputedStyle(el).zIndex) > 100) el.remove();
                });
            }""")

            # 2. Trigger the Player with a Click
            print("Triggering play handshake...")
            await page.mouse.click(640, 360) 
            
            # 3. Wait for the Sniffer to catch the link
            print("Listening for manifest...")
            for _ in range(30):
                if captured_link: break
                await asyncio.sleep(1)

            if captured_link:
                print(f"\n✅ CAPTURED: {captured_link}")
                
                # 4. Save to a VLC-compatible M3U file
                filename = f"movie_{IMDB_ID}.m3u"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    f.write(f"#EXTINF:-1, Movie {IMDB_ID}\n")
                    # VLC needs these specific lines to play protected VidSrc streams
                    f.write("#EXTVLCOPT:http-referrer=https://vidsrc.me/\n")
                    f.write(f"#EXTVLCOPT:http-user-agent={USER_AGENT}\n")
                    f.write(captured_link)
                
                print(f"📂 SAVED: {os.path.abspath(filename)}")
                print("👉 Right-click this file and 'Open with VLC'.")
            else:
                print("\n❌ FAILED: No manifest found. Check the browser window for a Captcha.")

        finally:
            await asyncio.sleep(5)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_and_save_playlist(TARGET_URL))
