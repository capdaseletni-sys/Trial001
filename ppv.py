import asyncio
import os
import random
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
IMDB_ID = "tt16500624" 
TARGET_URL = f"https://vidsrc.me/embed/movie?imdb={IMDB_ID}"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def scrape_vidsrc_ci_optimized(url):
    async with async_playwright() as p:
        # We use headless=False because xvfb-run will handle the display
        browser = await p.chromium.launch(headless=False) 
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=1,
        )
        
        # Inject stealth to hide Playwright fingerprints
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = await context.new_page()
        captured_link = None

        async def handle_request(request):
            nonlocal captured_link
            u = request.url
            if ("neonhorizonworkshops.com" in u or "master.m3u8" in u) and not captured_link:
                if not u.endswith(".ts"):
                    captured_link = u

        page.on("request", handle_request)

        try:
            print(f"🚀 Starting Headed Session in Virtual Display...")
            await page.goto(url, wait_until="networkidle")
            
            # 1. Wait for player to settle
            await asyncio.sleep(7)

            # 2. Aggressive Overlay Removal
            print("Deleting invisible blockers...")
            await page.evaluate("""() => {
                const blockers = document.querySelectorAll('div, section, ins');
                blockers.forEach(el => {
                    const z = parseInt(window.getComputedStyle(el).zIndex);
                    if (z > 100) el.remove();
                });
            }""")

            # 3. Triple Click Handshake
            # Pirate players often need multiple clicks to 'activate' the stream
            print("Performing triple-click handshake...")
            for i in range(3):
                await page.mouse.click(960, 540) # Click dead center
                await asyncio.sleep(1.5)

            # 4. Long Sniffing Window
            print("Sniffing traffic...")
            for i in range(40):
                if captured_link: break
                await asyncio.sleep(1)
                if i % 10 == 0: print(f"Polling background fetches... {i}s")

            if captured_link:
                print("\n" + "="*60)
                print("✅ CAPTURED MANIFEST:")
                print(captured_link)
                print("="*60)
                
                # Save M3U
                with open("stream.m3u", "w") as f:
                    f.write(f"#EXTM3U\n#EXTVLCOPT:http-referrer=https://vidsrc.me/\n#EXTINF:-1, Movie\n{captured_link}")
            else:
                print("\n❌ FAILED: The virtual display didn't fool the server or a Captcha is blocking.")

        except Exception as e:
            print(f"⚠️ Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_vidsrc_ci_optimized(TARGET_URL))
