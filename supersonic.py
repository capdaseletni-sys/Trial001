import asyncio
import aiohttp
import time
import sys

# --- CONFIGURATION ---
USER = "Z3nXfkOnf0"
PASS = "Madt8rUvmN"
ROCKET_BASE = "http://s.rocketdns.info:8080"
FINAL_NAME = "verified_rocket_streams.m3u8"

MAX_CONCURRENCY = 50  # Increased slightly for faster processing
TEST_TIMEOUT = 5      
USER_AGENT = "IPTVSmartersPlayer"

# Progress Tracking Globals
tested_count = 0
working_count = 0

async def check_stream(session, sem, title, url, total):
    """Verifies stream and updates the global progress counter."""
    global tested_count, working_count
    async with sem:
        result = (None, None, None)
        try:
            start_time = time.time()
            headers = {"User-Agent": USER_AGENT, "Range": "bytes=0-102400"}
            async with session.get(url, headers=headers, timeout=TEST_TIMEOUT) as r:
                if r.status < 400:
                    content = await r.read()
                    if len(content) > 1000:
                        latency = time.time() - start_time
                        working_count += 1
                        result = (latency, title, url)
        except:
            pass
        
        # Update Progress Bar in Console
        tested_count += 1
        percentage = (tested_count / total) * 100
        # \r allows us to overwrite the same line in the terminal
        sys.stdout.write(f"\r⚡ Progress: {percentage:.1f}% | Tested: {tested_count}/{total} | Found Working: {working_count}")
        sys.stdout.flush()
        
        return result

async def run():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": USER_AGENT}) as session:
        print(f"📡 Connecting to {ROCKET_BASE}...")
        
        try:
            api_url = f"{ROCKET_BASE}/player_api.php"
            params = {"username": USER, "password": PASS, "action": "get_live_streams"}
            
            async with session.get(api_url, params=params, timeout=30) as response:
                if response.status != 200:
                    print(f"❌ API Fetch Failed: Status {response.status}")
                    return
                
                raw_data = await response.json()
                raw_channels = [(s['name'], f"{ROCKET_BASE}/live/{USER}/{PASS}/{s['stream_id']}.ts") for s in raw_data]
                total_streams = len(raw_channels)
                print(f"🔍 Found {total_streams} total streams. Starting Speed Test...\n")
        except Exception as e:
            print(f"❌ Connection Error: {e}")
            return

        # Start concurrent testing
        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = [check_stream(session, sem, t, u, total_streams) for t, u in raw_channels]
        results = await asyncio.gather(*tasks)

        # Filter and Sort
        verified_list = [r for r in results if r[0] is not None]
        verified_list.sort(key=lambda x: x[0])

        # Save to file
        print(f"\n\n💾 Saving results to {FINAL_NAME}...")
        with open(FINAL_NAME, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for latency, title, url in verified_list:
                f.write(f'#EXTINF:-1, {title} [{latency:.2f}s]\n{url}\n')

        print(f"✅ SUCCESS! {len(verified_list)} streams verified and sorted by speed.")

if __name__ == "__main__":
    asyncio.run(run())
