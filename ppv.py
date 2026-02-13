import asyncio
import random
import logging
from playwright.async_api import async_playwright

# --- Configuration ---
BASE_URL = "https://tv13.lk21official.life/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0"
MAX_PAGES = 1  # Set this higher to crawl more movies (e.g., 5 or 10)
OUTPUT_FILE = "movies_library.m3u"

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger("LK21_Crawler")

async def apply_stealth(context):
    """Injects scripts to hide Playwright's automated nature."""
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
    """)

async def get_movie_links(page, num_pages):
    """Scans the homepage and pagination for movie URLs."""
    movie_links = []
    ignore_list = ['/genre/', '/year/', '/country/', '/search/', '/tag/', 'contact', 'dmca', 'paling-banyak-dicari']
    
    for i in range(1, num_pages + 1):
        url = f"{BASE_URL}page/{i}/" if i > 1 else BASE_URL
        log.info(f"Scouting Page {i}: {url}")
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            # Find all links that look like movie pages
            hrefs = await page.eval_on_selector_all("a", "elements => elements.map(e => e.href)")
            
            for href in hrefs:
                if BASE_URL in href and href != BASE_URL:
                    if not any(x in href.lower() for x in ignore_list):
                        # LK21 movies usually have at least 4 slashes in URL
                        if href.count('/') >= 4:
                            movie_links.append(href)
        except Exception as e:
            log.error(f"Failed to scan page {i}: {e}")
            break
            
    unique_links = list(set(movie_links))
    log.info(f"Found {len(unique_links)} unique movie links.")
    return unique_links

async def extract_stream(browser, movie_url):
    """Navigates to a movie page and captures the .m3u8 stream."""
    context = await browser.new_context(user_agent=USER_AGENT)
    await apply_stealth(context)
    page = await context.new_page()
    
    found_url = None
    movie_title = "Unknown Movie"

    def handle_request(request):
        nonlocal found_url
        u = request.url
        if ".m3u8" in u and not found_url:
            if any(x in u for x in ["index", "master", "m3u8", "playlist"]):
                found_url = u

    page.on("request", handle_request)

    try:
        log.info(f"Visiting: {movie_url}")
        await page.goto(movie_url, wait_until="domcontentloaded", timeout=60000)
        
        # Extract title
        title_el = await page.query_selector("h1")
        if title_el:
            movie_title = (await title_el.inner_text()).strip()

        # Trigger Player
        await asyncio.sleep(5) # Wait for ads to settle
        await page.mouse.click(640, 360) # Click center of video area
        
        # Poll for network link
        for _ in range(20):
            if found_url: break
            await asyncio.sleep(1)

        if found_url:
            log.info(f"✅ Captured: {movie_title}")
            return (
                f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n'
                f'#EXTVLCOPT:http-referrer={BASE_URL}\n'
                f'#EXTINF:-1 group-title="Movies", {movie_title}\n'
                f'{found_url}\n'
            )
    except Exception as e:
        log.debug(f"Error extracting {movie_url}: {e}")
    finally:
        await context.close()
    return None

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # We use a dedicated page for scouting
        scout_page = await browser.new_page()
        await apply_stealth(scout_page)
        
        links = await get_movie_links(scout_page, MAX_PAGES)
        
        if not links:
            log.error("No movie links found. The site structure might have changed.")
            await browser.close()
            return

        log.info("Starting stream extraction...")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            for link in links:
                result = await extract_stream(browser, link)
                if result:
                    f.write(result + "\n")
                # Human-like delay to avoid IP ban
                await asyncio.sleep(random.uniform(2, 4))

        log.info(f"Finished! Playlist saved to {OUTPUT_FILE}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
