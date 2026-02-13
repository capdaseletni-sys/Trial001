import asyncio
from playwright.async_api import async_playwright

# Paddington in Peru IMDb ID: tt16500624
IMDB_ID = "tt16500624"
# Direct API endpoint
VIDSRC_URL = f"https://vidsrc.me/embed/movie?imdb={IMDB_ID}"

async def scrape_vidsrc_api(api_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        found_m3u8 = None

        async def handle_response(response):
            nonlocal found_m3u8
            if ".m3u8" in response.url and not found_m3u8:
                found_m3u8 = response.url

        page.on("response", handle_response)

        try:
            print(f"🚀 Querying API: {api_url}")
            await page.goto(api_url, wait_until="networkidle")
            
            # VidSrc usually has a big 'Play' button in an iframe
            print("Interacting with VidSrc player...")
            await asyncio.sleep(5)
            
            # Brute force click to start the stream protocol
            await page.mouse.click(640, 360) 
            
            for i in range(20):
                if found_m3u8: break
                await asyncio.sleep(1)
            
            if found_m3u8:
                print(f"✅ FOUND DIRECT STREAM:\n{found_m3u8}")
            else:
                print("❌ API did not release a public M3U8. It may be using encrypted chunks.")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_vidsrc_api(VIDSRC_URL))
