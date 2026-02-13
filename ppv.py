import asyncio
import os
import random
from playwright.async_api import async_playwright

# --- SETTINGS ---
IMDB_ID = "tt16500624" 
TARGET_URL = f"https://vidsrc.me/embed/movie?imdb={IMDB_ID}"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def run_stealth_scraper(url):
    async with async_playwright() as p:
        # CRITICAL: headless=False is necessary for high-security targets in 2026
        # Switch to True only if you are using a Stealth Plugin or a Proxy
        browser = await p.chromium.launch(headless=False) 
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=1,
        )
        
        # Injecting a script to hide the 'webdriver' property
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = await context.new_page()
        captured_m3u8 = None

        async def handle_request(request):
            nonlocal captured_m3u8
            u = request.url
            if ("neonhorizonworkshops.com" in u or ".m3u8" in u) and not captured_m3u8:
                if not u.endswith(".ts"):
                    captured_m3u8 = u

        page.on("request", handle_request)

        try:
            print(f"🚀 Launching Stealth Session...")
            await page.goto(url, wait_until="networkidle")
            
            # 1. Human-like Delay
            await asyncio.sleep(random.uniform(3, 6))

            # 2. Random Mouse Movement (Triggers 'Trusted' status)
            print("Performing human-like interactions...")
            for _ in range(3):
                await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                await asyncio.sleep(0.5)

            # 3. Clean and Click
            await page.evaluate("document.querySelectorAll('div').forEach(el => { if(parseInt(window.getComputedStyle(el).zIndex) > 100) el.remove(); })")
            await page.mouse.click(640, 360) 
            
            print("Waiting for manifest...")
            for i in range(30):
                if captured_m3u8: break
                await asyncio.sleep(1)

            if captured_m3u8:
                print(f"\n✅ SUCCESS: {captured_m3u8}")
                # Save as before...
            else:
                print("\n❌ Protection still active. Try solving any Captcha that appeared in the window.")

        finally:
            # We leave the browser open for a second so you can see the result
            await asyncio.sleep(2)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_stealth_scraper(TARGET_URL))
