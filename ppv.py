import asyncio
import os
from playwright.async_api import async_playwright

# --- SETTINGS ---
# Use the IMDb ID of the movie you want to scrape
IMDB_ID = "tt16500624" # Paddington in Peru
TARGET_URL = f"https://vidsrc.me/embed/movie?imdb={IMDB_ID}"

# Standard 2026 User Agent to avoid basic bot detection
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def run_unified_scraper(url):
    async with async_playwright() as p:
        # Launching with headless=True for efficiency. 
        # If it fails, switch to False to see the interaction.
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        captured_m3u8 = None

        # 1. Network Interceptor: Specifically looking for neonhorizon manifests
        async def handle_request(request):
            nonlocal captured_m3u8
            u = request.url
            if ("neonhorizonworkshops.com" in u or ".m3u8" in u) and not captured_m3u8:
                if not u.endswith(".ts"): # Filter out video segments
                    captured_m3u8 = u

        page.on("request", handle_request)

        try:
            print(f"🚀 Initializing session for: {url}")
            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(4)

            # 2. Kill Overlays: Delete invisible click-jackers
            print("Cleaning page overlays...")
            await page.evaluate("""() => {
                document.querySelectorAll('div').forEach(el => {
                    const style = window.getComputedStyle(el);
                    if (parseInt(style.zIndex) > 1000 || style.position === 'fixed') {
                        el.remove();
                    }
                });
            }""")

            # 3. Force Handshake: Click the player area
            print("Triggering player handshake...")
            # Click the center of the player
            await page.mouse.click(640, 360) 
            
            # 4. Polling for the link
            print("Sniffing network traffic (30s window)...")
            for i in range(30):
                if captured_m3u8: break
                await asyncio.sleep(1)
                if i % 10 == 0: print(f"Wait time: {i}s...")

            if captured_m3u8:
                print("\n" + "="*60)
                print("✅ SUCCESS! LINK CAPTURED:")
                print(captured_m3u8)
                print("="*60)

                # 5. Automatically write to M3U file
                filename = f"movie_{IMDB_ID}.m3u"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    f.write(f"#EXTINF:-1, Movie ID: {IMDB_ID}\n")
                    # Many CDNs require the Referer to prevent 403 errors
                    f.write("#EXTVLCOPT:http-referrer=https://vidsrc.me/\n")
                    f.write(f"#EXTVLCOPT:http-user-agent={USER_AGENT}\n")
                    f.write(captured_m3u8)
                
                print(f"📁 Playlist saved as: {os.path.abspath(filename)}")
                print("💡 Pro-Tip: Open this file in VLC to watch.")
            else:
                print("\n❌ Failed to capture the manifest. The session might be protected.")

        except Exception as e:
            print(f"⚠️ Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_unified_scraper(TARGET_URL))
