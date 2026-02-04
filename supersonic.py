import asyncio
import aiohttp
import time
import sys

# --- CONFIGURATION ---
USER = "Z3nXfkOnf0"
PASS = "Madt8rUvmN"
ROCKET_BASE = "http://s.rocketdns.info:8080"
FINAL_NAME = "supersonic.m3u8"

# ADJUSTMENTS
MAX_RESULTS = 500      # Stop saving after 500 working streams
SPEED_CUTOFF = 1.5     # Only keep streams that respond in less than 1.5s
MAX_CONCURRENCY = 40   
TEST_TIMEOUT = 5       
USER_AGENT = "IPTVSmartersPlayer"

tested_count = 0
working_results = [] # Store results here to sort them later

async def check_stream(session, sem, title, url, total):
    global tested_count
    async with sem:
        try:
            # Skip testing if we already have enough high-quality results
            if len(working_results) >= MAX_RESULTS:
                tested_count += 1
                return

            start_time = time.time()
            async with session.get(url, timeout=TEST_TIMEOUT) as r:
                if r.status == 200:
                    # Quick bit-check
                    content = await r.content.read(5000) 
                    if len(content) > 0:
                        latency = time.time() - start_time
                        
                        # Only add if it meets our speed requirement
                        if latency <= SPEED_CUTOFF:
                            working_results.append((latency, title, url))
        except:
            pass
        
        tested_count += 1
        percentage = (tested_count / total) * 100
        sys.stdout.write(f"\r⚡ Progress: {percentage:.1f}% | Tested: {tested_count}/{total} | Fast Streams Found: {len(working_results)}")
        sys.stdout.flush()

async def run():
    connector = aiohttp.TCPConnector(ssl=False)
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        print(f"📡 Fetching list from {ROCKET_BASE}...")
        
        try:
            api_url = f"{ROCKET_BASE}/player_api.php"
            params = {"username": USER, "password": PASS, "action": "get_live_streams"}
            
            async with session.get(api_url, params=params) as response:
                raw_data = await response.json()
                raw_channels = [(s['name'], f"{ROCKET_BASE}/live/{USER}/{PASS}/{s['stream_id']}.ts") for s in raw_data]
                
                total_streams = len(raw_channels)
                print(f"🔍 Total available: {total_streams}. Looking for the top {MAX_RESULTS} fastest...")
        except Exception as e:
            print(f"❌ API Error: {e}")
            return

        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = [check_stream(session, sem, t, u, total_streams) for t, u in raw_channels]
        await asyncio.gather(*tasks)

        # Sort by speed (Fastest first)
        working_results.sort(key=lambda x: x[0])

        print(f"\n\n💾 Saving the best {len(working_results)} streams...")
        with open(FINAL_NAME, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for latency, title, url in working_results:
                # Add a group tag so your player categorizes them
                f.write(f'#EXTINF:-1 group-title="Verified Fast",{title}\n{url}\n')

        print(f"✅ SUCCESS! Generated {FINAL_NAME}")

if __name__ == "__main__":
    asyncio.run(run())
