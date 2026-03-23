import asyncio
import json
import random
from playwright.async_api import async_playwright

async def scrape_to_m3u():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print("Step 1: Gathering channel list...")
        await page.goto("https://thetvapp.to/tv/", wait_until="networkidle")
        
        channels = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href*="/tv/"]')).map(a => ({
                name: a.innerText.trim(),
                href: a.href,
                slug: a.href.split('/').filter(Boolean).pop().replace('-live-stream', '').toUpperCase()
            })).filter(c => c.name && c.slug !== 'TV');
        }""")

        unique_channels = {c['slug']: c for c in channels}.values()
        print(f"Found {len(unique_channels)} channels. Starting extraction...")

        # Initialize the M3U content with the header
        m3u_lines = ["#EXTM3U"]

        # Step 2: Visit each page and grab the token
        for ch in unique_channels:
            print(f"Processing: {ch['name']}...")
            try:
                await page.goto(ch['href'], wait_until="networkidle")
                await asyncio.sleep(1.5) # Allow security tokens to load

                response = await page.evaluate(f"""
                    fetch("https://thetvapp.to/token/{ch['slug']}", {{
                        headers: {{ "Accept": "application/json" }}
                    }}).then(res => res.json())
                """)

                if "url" in response:
                    stream_url = response["url"]
                    # Format for M3U: #EXTINF:-1 group-title="NAME",CHANNEL NAME
                    m3u_lines.append(f'#EXTINF:-1 group-title="TV APP [SD]",{ch["name"]}')
                    m3u_lines.append(stream_url)
                    print(f"  [+] Success")
                else:
                    print(f"  [-] No URL found for {ch['slug']}")

            except Exception as e:
                print(f"  [!] Error: {e}")

            # Random delay to stay under the radar
            await asyncio.sleep(random.uniform(1, 2.5))

        # Step 3: Write to file
        with open("tap.m3u8", "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_lines))

        print(f"\n--- COMPLETED ---")
        print(f"Playlist saved as: tap.m3u8")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_to_m3u())
