import asyncio
import aiohttp
import time
import sys

# --- CONFIGURATION ---
USER = "Z3nXfkOnf0"
PASS = "Madt8rUvmN"
ROCKET_BASE = "http://s.rocketdns.info:8080"
FINAL_NAME = "supersonic.m3u8"

# BALANCED SETTINGS
MIN_MBPS = 0.8          # Lowered: 0.8Mbps is enough for SD/HD stability
SAMPLE_SIZE = 500000    # Lowered to 500KB (faster test, less likely to be blocked)
MAX_CONCURRENCY = 10    # Slow and steady to avoid IP bans
TEST_TIMEOUT = 10       
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebkit/537.36"

tested_count = 0
working_results = []

async def check_stream(session, sem, title, url, total):
    global tested_count
    async with sem:
        try:
            clean_title = title.lower()
            if any(x in clean_title for x in ["adult", "24/7", "xxx"]):
                tested_count += 1
                return

            start_time = time.time()
            async with session.get(url, timeout=TEST_TIMEOUT) as r:
                if r.status == 200:
                    # We skip the strict MIME check and just try to read data
                    content = await r.content.read(SAMPLE_SIZE)
                    
                    if len(content) > 1000: # Ensure we got at least some data
                        elapsed = time.time() - start_time
                        mbps = (len(content) * 8) / elapsed / 1000000
                        
                        if mbps >= MIN_MBPS:
                            working_results.append((mbps, title, url))
        except Exception:
            pass
        
        tested_count += 1
        sys.stdout.write(f"\r⚡ SCANNING: {tested_count}/{total} | Found Smooth: {len(working_results)}")
        sys.stdout.flush()

async def run():
    # Use a standard connector; some servers dislike 'limit=0'
    connector = aiohttp.TCPConnector(ssl=False)
    headers = {"User-Agent": USER_AGENT}

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        print(f"📡 Accessing RocketDNS...")
        
        try:
            api_url = f"{ROCKET_BASE}/player_api.php"
            params = {"username": USER, "password": PASS, "action": "get_live_streams"}
            
            async with session.get(api_url, params=params) as response:
                raw_data = await response.json()
                raw_channels = [(s['name'], f"{ROCKET_BASE}/live/{USER}/{PASS}/{s['stream_id']}.ts") for s in raw_data]
                total_streams = len(raw_channels)
                print(f"🔍 Found {total_streams} channels. Testing for stability...\n")
        except Exception as e:
            print(f"❌ Connection Error: {e}")
            return

        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = [check_stream(session, sem, t, u, total_streams) for t, u in raw_channels]
        await asyncio.gather(*tasks)

        # Sort by speed
        working_results.sort(key=lambda x: x[0], reverse=True)

        print(f"\n\n💾 Exporting {len(working_results)} streams to {FINAL_NAME}")
        with open(FINAL_NAME, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for mbps, title, url in working_results:
                f.write(f'#EXTINF:-1 group-title="Verified",{title}\n{url}\n')

        print(f"✅ DONE!")

if __name__ == "__main__":
    asyncio.run(run())
