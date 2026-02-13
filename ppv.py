import asyncio
import random
import logging
from playwright.async_api import async_playwright

# --- Configuration ---
BASE_URL = "https://tv13.lk21official.life/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0"
MAX_PAGES = 1  
OUTPUT_FILE = "movies_library.m3u"

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger("LK21_Crawler")

async def apply_stealth(context):
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = { runtime: {} };
    """)

async def get_movie_links(page, num_pages):
    movie_links = []
    # These are fragments that appear in category/menu links that we want to SKIP
    system_patterns = ['?page=', '/genre/', '/year/', '/country/', '/search/', '/tag/', 'contact', 'dmca', 'quality/', 'release/']
    
    for i in range(1, num_pages + 1):
        url = f"{BASE_URL}page/{i}/" if i > 1 else BASE_URL
        log.info(f"Scouting Page {i}: {url}")
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Target links inside the main content area only
            hrefs = await page.eval_on_selector_all("a", "elements => elements.map(e => e.href)")
            
            for href in hrefs:
                # 1. Must stay on the same domain
                # 2. Must NOT be a system/category link
                # 3. Usually movie slugs don't have '?' or 'page' in the URL
                if BASE_URL in href and href != BASE_URL:
                    if not any(pattern in href for pattern in system_patterns):
                        movie_links.append(href)
        except Exception as e:
            log.error(f"Error on page {i}: {e}")
            break
            
    unique_links = list(set(movie_links))
    log.info(f"Filtered down to {len(unique_links)} actual movie pages.")
    return unique_links

async def extract_stream(browser, movie_url):
    context = await browser.new_context(user_agent=USER_AGENT)
    await apply_stealth(context)
    page = await context.new_page()
    
    found_url = None
    movie_title = "Unknown Movie"

    def handle_request(request):
        nonlocal found_url
        if ".m3u8" in request.url and not found_url:
            # We want the master/index manifest, not individual chunks (.ts)
            if not request.url.endswith(".ts"):
                found_url = request.url

    page.on("request", handle_request)

    try:
        log.info(f"Processing Movie: {movie_url}")
        await page.goto(movie_url, wait_until="domcontentloaded", timeout=45000)
        
        # Get Movie Title
        title_el = await page.query_selector("h1")
        if title_el:
            movie_title = (await title_el.inner_text()).strip()

        # Click the play button area
        await asyncio.sleep(6) # Wait for anti-bot & overlays to load
        await page.mouse.click(640, 360) 
        
        # Wait up to 15 seconds for the .m3u8 to appear in network traffic
        for _ in range(15):
            if found_url: break
            await asyncio.sleep(1)

        if found_url:
            return (
                f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n'
                f'#EXTVLCOPT:http-referrer={BASE_URL}\n'
                f'#EXTINF:-1 group-title="Movies", {movie_title}\n'
                f'{found_url}\n'
            )
    except Exception:
        pass
    finally:
        await context.close()
    return None

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        scout_page = await browser.new_page()
        await apply_stealth(scout_page)
        
        links = await get_movie_links(scout_page, MAX_PAGES)
        
        if not links:
            log.error("Could not find any movie links. Check if the site is blocked.")
            await browser.close()
            return

        log.info(f"Found {len(links)} movies. Starting extraction...")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            for link in links:
                result = await extract_stream(browser, link)
                if result:
                    f.write(result + "\n")
                    log.info("✅ Success")
                else:
                    log.warning("❌ No stream found")
                await asyncio.sleep(random.uniform(2, 4))

        await browser.close()
        log.info(f"Done! Created {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
