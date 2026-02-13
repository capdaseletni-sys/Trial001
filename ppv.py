import asyncio
import random
from playwright.async_api import async_playwright

BASE_URL = "https://tv13.lk21official.life/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0"

async def get_all_movie_links(page, max_pages=3):
    """Navigates through pages and collects all movie URLs."""
    movie_links = []
    for i in range(1, max_pages + 1):
        url = f"{BASE_URL}page/{i}/" if i > 1 else BASE_URL
        print(f"Scouting Page {i}: {url}")
        try:
            await page.goto(url, wait_until="domcontentloaded")
            # Selector for movie links (usually inside an article or div with a specific class)
            links = await page.eval_on_selector_all("article a", "elements => elements.map(e => e.href)")
            # Filter unique movie links (ignoring categories/tags)
            filtered = [l for l in links if "/movie/" in l or l.count("/") >= 4]
            movie_links.extend(filtered)
        except Exception as e:
            print(f"Error scouting page {i}: {e}")
            break
    return list(set(movie_links))

async def extract_stream(browser, movie_url):
    """Visits a single movie page and catches the .m3u8."""
    context = await browser.new_context(user_agent=USER_AGENT)
    page = await context.new_page()
    found_url = None
    movie_title = "Unknown"

    page.on("request", lambda req: handle_m3u8(req))
    
    def handle_m3u8(request):
        nonlocal found_url
        if ".m3u8" in request.url and not found_url:
            found_url = request.url

    try:
        await page.goto(movie_url, wait_until="load", timeout=60000)
        movie_title = await page.title()
        
        # Trigger player
        await asyncio.sleep(4)
        await page.mouse.click(640, 360) 
        
        # Wait for capture
        for _ in range(15):
            if found_url: break
            await asyncio.sleep(1)
            
        if found_url:
            entry = (
                f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n'
                f'#EXTVLCOPT:http-referrer={BASE_URL}\n'
                f'#EXTINF:-1 group-title="Movies", {movie_title}\n'
                f'{found_url}\n'
            )
            return entry
    except:
        return None
    finally:
        await context.close()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Step 1: Get list of movies
        all_links = await get_all_movie_links(page, max_pages=2) # Adjust pages as needed
        print(f"Found {len(all_links)} potential movies.")
        
        # Step 2: Extract streams (One by one to avoid detection)
        with open("full_library.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            for link in all_links:
                print(f"Processing: {link}")
                result = await extract_stream(browser, link)
                if result:
                    f.write(result + "\n")
                    print("✅ Stream Captured")
                await asyncio.sleep(2) # Be polite to the server
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
