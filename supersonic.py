import asyncio
import aiohttp
import time
import sys

# --- CONFIGURATION ---
USER = "Z3nXfkOnf0"
PASS = "Madt8rUvmN"
ROCKET_BASE = "http://s.rocketdns.info:8080"
FINAL_NAME = "supersonic.m3u8"

# PERFORMANCE SETTINGS
SPEED_CUTOFF = 0.6     # ULTRA-FAST: Only keeps streams responding under 600ms
MAX_CONCURRENCY = 60   # High speed scanning
TEST_TIMEOUT = 3       # If it doesn't respond in 3s, we don't want it anyway
USER_AGENT = "IPTVSmartersPlayer"

tested_count = 0
working_results = []

async def check_stream(session, sem, title, url, total):
    global tested_count
    async with sem:
        try:
            start_time = time.time()
            # Standard request - mimics a real player behavior
            async with session.get(url, timeout=TEST_TIMEOUT) as r:
                if r.status == 200:
                    # Read only the first 2KB to confirm the stream is sending data
                    content = await r.content.read(2048) 
                    if content:
                        latency = time.time() - start_time
                        
                        # Apply the "Supersonic" filter
                        if latency <= SPEED_CUTOFF:
                            working_results.append((latency, title, url))
        except:
            pass
        
        # Update UI Progress
        tested_count += 1
        percentage = (tested_count / total) * 100
        sys.stdout.write(f"\r⚡ SCANNING: {percentage:.1f}% | Fast Found: {len(working_results)} | Testing: {tested_count}/{total}")
        sys.stdout.flush()

async def run():
    connector = aiohttp.TCPConnector(ssl=False, limit=0) # limit=0 allows max speed
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*", "Connection": "keep-alive"}

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        print(f"📡 Fetching ALL streams from {ROCKET_BASE}...")
        
        try:
            api_url = f"{ROCKET_BASE}/player_api.php"
            params = {"username": USER, "password": PASS, "action": "get_live_streams"}
            
            async with session.get(api_url, params=params) as response:
                raw_data = await response.json()
                # Prepare all URLs
                raw_channels = [(s['name'], f"{ROCKET_BASE}/live/{USER}/{PASS}/{s['stream_id']}.ts") for s in raw_data]
                
                total_streams = len(raw_channels)
                print(f"🔍 Total found: {total_streams}. Filtering for < {SPEED_CUTOFF}s latency...\n")
        except Exception as e:
            print(f"❌ API Error: {e}")
            return

        # Start the massive concurrent scan
        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = [check_stream(session, sem, t, u, total_streams) for t, u in raw_channels]
        await asyncio.gather(*tasks)

        # Final Sort: Fastest results at the very top of the file
        working_results.sort(key=lambda x: x[0])

        print(f"\n\n💾 Saving {len(working_results)} supersonic streams...")
        with open(FINAL_NAME, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for lat, title, url in working_results:
                f.write(f'#EXTINF:-1 group-title="Verified Supersonic",{title} ({int(lat*1000)}ms)\n{url}\n')

        print(f"✅ DONE! File created: {FINAL_NAME}")

if __name__ == "__main__":
    asyncio.run(run())
