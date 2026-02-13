import asyncio
import random
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
TARGET_URL = "https://tv13.lk21official.life/disco-dancer-1982/" 
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def extract_turbovip_m3u8(url):
    async with async_playwright() as p:
        # headless=False is recommended for debugging if the click fails
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        
        found_m3u8 = None

        # Network Sniffer: Catches the manifest URL from background traffic
        async def handle_response(response):
            nonlocal found_m3u8
            u = response.url
            if ".m3u8" in u and not found_m3u8:
                # We want the master/index manifest, not the .ts data chunks
                if not u.endswith(".ts"):
                    found_m3u8 = u

        page.on("response", handle_response)

        try:
            print(f"🚀 Loading: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # --- STEP 1: Select TURBOVIP (Fixing Strict Mode) ---
            print("Locating TURBOVIP server link...")
            await asyncio.sleep(4) # Allow server tabs to render
            
            # We use .first() to resolve the 'Strict Mode Violation' 
            # and role='link' to ignore the dropdown menu option
            turbovip_btn = page.get_by_role("link", name="TURBOVIP", exact=True).first
            
            if await turbovip_btn.is_visible():
                print("Found TURBOVIP button. Clicking...")
                await turbovip_btn.click()
                # Wait for the player iframe to reload with the new server
                await asyncio.sleep(7) 
            else:
                # Emergency Fallback if the role locator fails
                print("⚠️ Role selector failed. Trying direct data-server attribute...")
                await page.click("a[data-server='turbovip']", timeout=5000)
                await asyncio.sleep(7)

            # --- STEP 2: Trigger Player Interaction ---
            print("Triggering player interaction...")
            # Click center of the player area to start the stream request
            await page.mouse.click(640, 360) 
            
            # Also try to click 'video' tags inside nested iframes
            for frame in page.frames:
                try:
                    await frame.click("video", force=True, timeout=1000)
                except:
                    pass

            # --- STEP 3: Wait for Network Traffic ---
            print("Sniffing network for .m3u8 manifest...")
            for i in range(30):
                if found_m3u8: break
                await asyncio.sleep(1)
                if i % 5 == 0: print(f"Polling... ({i}s)")

            if found_m3u8:
                print("\n" + "="*50)
                print("✅ SUCCESS! STREAM CAPTURED:")
                print(found_m3u8)
                print("="*50)
                
                # Format for M3U playlist
                playlist_entry = (
                    f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n'
                    f'#EXTVLCOPT:http-referrer={url}\n'
                    f'#EXTINF:-1, {await page.title()}\n'
                    f'{found_m3u8}\n'
                )
                with open("turbovip_stream.m3u", "w") as f:
                    f.write("#EXTM3U\n\n" + playlist_entry)
                print("Saved to: turbovip_stream.m3u")
            else:
                print("\n❌ Failed. The server might be using a BLOB or protected session.")

        except Exception as e:
            print(f"Error encountered: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(extract_turbovip_m3u8(TARGET_URL))
