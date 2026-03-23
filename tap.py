import asyncio
import json
import random
from playwright.async_api import async_playwright

# --- SETTINGS ---
MAX_CONCURRENT_TABS = 5  # How many channels to scrape at the exact same time
OUTPUT_FILE = "tap.m3u8"
GROUP_TITLE = "TV APP [SD]"
# ----------------

async def fetch_channel_token(context, ch, semaphore):
    async with semaphore:  # Limits the number of active tasks
        page = await context.new_page()
        try:
            print(f"🚀 Processing: {ch['name']}")
            # Use 'domcontentloaded' to finish faster than a full 'networkidle'
            await page.goto(ch['href'], wait_until="domcontentloaded", timeout=30000)
            
            # Shorter wait: just enough for the site's background scripts
            await asyncio.sleep(1.2) 

            response = await page.evaluate(f"""
                fetch("https://thetvapp.to/token/{ch['slug']}", {{
                    headers: {{ "Accept": "application/json" }}
                }}).then(res => res.json())
            """)

            if "url" in response:
                return f'#EXTINF:-1 group-title="{GROUP_TITLE}",{ch["name"]}\n{response["url"]}'
        except Exception as e:
            print(f"❌ Error on {ch['name']}: {e}")
        finally:
            await page.close()
    return None

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        )
        
        # 1. Get the list of channels
        print("Scoping out the channels...")
        main_page = await context.new_page()
        await main_page.goto("https://thetvapp.to/tv/", wait_until="domcontentloaded")
        
        channels = await main_page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href*="/tv/"]')).map(a => ({
                name: a.innerText.trim(),
                href: a.href,
                slug: a.href.split('/').filter(Boolean).pop().replace('-live-stream', '').toUpperCase()
            })).filter(c => c.name && c.slug !== 'TV');
        }""")
        await main_page.close()

        # Remove duplicates
        unique_channels = list({c['slug']: c for c in channels}.values())
        print(f"Found {len(unique_channels)} channels. Running {MAX_CONCURRENT_TABS} at a time...")

        # 2. Run scraping concurrently
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TABS)
        tasks = [fetch_channel_token(context, ch, semaphore) for ch in unique_channels]
        
        # This runs all tasks together
        results = await asyncio.gather(*tasks)

        # 3. Save to M3U8
        m3u_content = ["#EXTM3U"] + [r for r in results if r]
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_content))

        print(f"\n✅ Done! Saved {len(m3u_content)-1} streams to {OUTPUT_FILE}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
