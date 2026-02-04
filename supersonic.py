import asyncio
import aiohttp
import time
import sys

# --- CONFIGURATION ---
USER = "Z3nXfkOnf0"
PASS = "Madt8rUvmN"
ROCKET_BASE = "http://s.rocketdns.info:8080"
FINAL_NAME = "supersonic.m3u8"

# STABILITY SETTINGS
MIN_MBPS = 3.0          # Minimum speed required (3Mbps for stable HD)
SAMPLE_SIZE = 1500000   # Download ~1.5MB to test sustained throughput
MAX_CONCURRENCY = 15    # Lowered to prevent saturating YOUR local internet
TEST_TIMEOUT = 12       # Increased to allow for the larger download
USER_AGENT = "IPTVSmartersPlayer"

tested_count = 0
working_results = []

async def check_stream(session, sem, title, url, total):
    global tested_count
    async with sem:
        try:
            # 1. Filter out unwanted keywords
            clean_title = title.lower()
            if any(x in clean_title for x in ["adult", "24/7", "xxx"]):
                tested_count += 1
                return

            start_time = time.time()
            async with session.get(url, timeout=TEST_TIMEOUT) as r:
                # 2. Check if the server is actually sending video
                ctype = r.headers.get('Content-Type', '').lower()
                is_video = any(v in ctype for v in ['video', 'mpeg', 'octet-stream'])

                if r.status == 200 and is_video:
                    # 3. Sustained Throughput Test (The "Anti-Buffer" check)
                    content = await r.content.read(SAMPLE_SIZE)
                    if len(content) > 0:
                        elapsed = time.time() - start_time
                        
                        # Calculate Mbps: (Bytes * 8 bits) / seconds / 1,000,000
                        mbps = (len(content) * 8) / elapsed / 1000000
                        
                        if mbps >= MIN_MBPS:
                            # Save with speed for sorting, then export clean
                            working_results.append((mbps, title, url))
        except Exception:
            pass
        
        tested_count += 1
        percentage = (tested_count / total) * 100
        sys.stdout.write(f"\r⚡ TESTING STABILITY: {percentage:.1f}% | Smooth: {len(working_results)} | {tested_count}/{total}")
        sys.stdout.flush()

async def run():
    connector = aiohttp.TCPConnector(ssl=False, limit=0)
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        print(f"📡 Connecting to {ROCKET_BASE}...")
        
        try:
            api_url = f"{ROCKET_BASE}/player_api.php"
            params = {"username": USER, "password": PASS, "action": "get_live_streams"}
            
            async with session.get(api_url, params=params) as response:
                raw_data = await response.json()
                # Prepare channel list
                raw_channels = [(s['name'], f"{ROCKET_BASE}/live/{USER}/{PASS}/{s['stream_id']}.ts") for s in raw_data]
                total_streams = len(raw_channels)
                print(f"🔍 Found {total_streams} streams. Starting stability stress-test...\n")
        except Exception as e:
            print(f"❌ API Error: {e}")
            return

        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = [check_stream(session, sem, t, u, total_streams) for t, u in raw_channels]
        await asyncio.gather(*tasks)

        # Sort by best Mbps (fastest/most stable first)
        working_results.sort(key=lambda x: x[0], reverse=True)

        print(f"\n\n💾 Saving {len(working_results)} high-bitrate streams...")
        with open(FINAL_NAME, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for mbps, title, url in working_results:
                # Grouped by "Verified" for easy player sorting
                f.write(f'#EXTINF:-1 group-title="Verified Smooth (>{MIN_MBPS}Mbps)",{title}\n{url}\n')

        print(f"✅ DONE! Clean playlist created: {FINAL_NAME}")

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nStopped by user.")
