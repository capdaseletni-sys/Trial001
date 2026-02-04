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
SPEED_CUTOFF = 0.5     
MAX_CONCURRENCY = 60   
TEST_TIMEOUT = 3       
USER_AGENT = "IPTVSmartersPlayer"

tested_count = 0
working_results = []

async def check_stream(session, sem, title, url, total):
    global tested_count
    async with sem:
        try:
            # 1. Filter out unwanted keywords immediately
            clean_title = title.lower()
            if "adult" in clean_title or "24/7" in clean_title:
                tested_count += 1
                return

            start_time = time.time()
            async with session.get(url, timeout=TEST_TIMEOUT) as r:
                if r.status == 200:
                    content = await r.content.read(2048) 
                    if content:
                        latency = time.time() - start_time
                        if latency <= SPEED_CUTOFF:
                            # Save only title and url (no ms label)
                            working_results.append((latency, title, url))
        except:
            pass
        
        tested_count += 1
        percentage = (tested_count / total) * 100
        sys.stdout.write(f"\r⚡ SCANNING: {percentage:.1f}% | Valid: {len(working_results)} | Testing: {tested_count}/{total}")
        sys.stdout.flush()

async def run():
    connector = aiohttp.TCPConnector(ssl=False, limit=0)
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*", "Connection": "keep-alive"}

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        print(f"📡 Fetching ALL streams from {ROCKET_BASE}...")
        
        try:
            api_url = f"{ROCKET_BASE}/player_api.php"
            params = {"username": USER, "password": PASS, "action": "get_live_streams"}
            
            async with session.get(api_url, params=params) as response:
                raw_data = await response.json()
                raw_channels = [(s['name'], f"{ROCKET_BASE}/live/{USER}/{PASS}/{s['stream_id']}.ts") for s in raw_data]
                total_streams = len(raw_channels)
                print(f"🔍 Total found: {total_streams}. Applying Filters (No Adult, No 24/7)...\n")
        except Exception as e:
            print(f"❌ API Error: {e}")
            return

        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = [check_stream(session, sem, t, u, total_streams) for t, u in raw_channels]
        await asyncio.gather(*tasks)

        # Sort by speed, then strip latency for the final file
        working_results.sort(key=lambda x: x[0])

        print(f"\n\n💾 Saving {len(working_results)} clean supersonic streams...")
        with open(FINAL_NAME, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for _, title, url in working_results:
                # Clean output: No (ms) tags
                f.write(f'#EXTINF:-1 group-title="Verified Supersonic",{title}\n{url}\n')

        print(f"✅ DONE! File created: {FINAL_NAME}")

if __name__ == "__main__":
    asyncio.run(run())
