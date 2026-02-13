import asyncio
from playwright.async_api import async_playwright

async def vidsrc_deep_sniff(imdb_id):
    async with async_playwright() as p:
        # headless=False is your best friend when 'networkidle' fails
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        captured_url = None

        # Listen to REQUESTS (catches the link before it's even loaded)
        async def handle_request(request):
            nonlocal captured_url
            u = request.url
            # Catching the three most common manifest patterns
            if any(x in u for x in [".m3u8", "master", "playlist"]) and not captured_url:
                if not u.endswith(".ts"): # Ignore segment chunks
                    captured_url = u

        page.on("request", handle_request)

        try:
            url = f"https://vidsrc.me/embed/movie?imdb={imdb_id}"
            print(f"🚀 Targeting API: {url}")
            
            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(4)

            # --- STEP 1: The 'Wake-Up' Click ---
            # VidSrc requires a physical interaction to start the crypto-handshake
            print("Triggering player handshake...")
            await page.mouse.move(640, 360) # Simulate a hover
            await asyncio.sleep(1)
            await page.mouse.click(640, 360) # Click the center
            
            # --- STEP 2: The Polling Loop ---
            for i in range(30):
                if captured_url: break
                await asyncio.sleep(1)
                if i % 10 == 0: print(f"Sniffing background fetches... {i}s")

            if captured_url:
                print("\n" + "="*50)
                print("✅ CAPTURED MANIFEST:")
                print(captured_url)
                print("="*50)
                print("⚠️  Note: This link usually requires Referer: https://vidsrc.me/")
            else:
                print("\n❌ Handshake failed. The site may be using WebSockets or DRM.")

        finally:
            await browser.close()

if __name__ == "__main__":
    # Trying with your Paddington ID
    asyncio.run(vidsrc_deep_sniff("tt16500624"))
