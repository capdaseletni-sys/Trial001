import asyncio
import aiohttp
import time
import sys

# --- CONFIGURATION ---
USER = "Z3nXfkOnf0"
PASS = "Madt8rUvmN"
ROCKET_BASE = "http://s.rocketdns.info:8080"
FINAL_NAME = "verified_rocket_streams.m3u8"

MAX_CONCURRENCY = 40  # Lowered slightly to avoid triggering firewall blocks
TEST_TIMEOUT = 8      # Increased timeout for slower initial connections
USER_AGENT = "IPTVSmartersPlayer" # Best for RocketDNS

tested_count = 0
working_count = 0

async def check_stream(session, sem, title, url, total):
    global tested_count, working_count
    async with sem:
        result = (None, None, None)
        try:
            start_time = time.time()
            # We use a standard GET but with a short timeout and no Range header first
            # to see if the server actually starts sending bits.
            async with session.get(url, timeout=TEST_TIMEOUT) as r:
                if r.status == 200:
                    # Read just a tiny bit of the stream to confirm it's video
                    content = await r.content.read(5000) 
                    if len(content) > 0:
                        latency = time.time() - start_time
                        working_count += 1
                        result = (latency, title, url)
        except:
            pass
        
        # UI Progress Update
        tested_count += 1
        percentage = (tested_count / total) * 100
        sys.stdout.write(f"\r⚡ Progress: {percentage:.1f}% | Tested: {tested_count}/{total} | Found Working: {working_count}")
        sys.stdout.flush()
        
        return result

async def run():
    # Crucial for RocketDNS: Some use self-signed SSL or have expired certs
    connector = aiohttp.TCPConnector(ssl=False)
    
    # We set common browser/player headers globally
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Connection": "keep-alive"
    }

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        print(f"📡 Connecting to {ROCKET_BASE}...")
        
        try:
            api_url = f"{ROCKET_BASE}/player_api.php"
            params = {"username": USER, "password": PASS, "action": "get_live_streams"}
            
            async with session.get(api_url, params=params, timeout=30) as response:
                if response.status != 200:
                    print(f"❌ Login Failed: Status {response.status}")
                    return
                
                raw_data = await response.json()
                
                # Filter out any VOD (movies) if they were accidentally included
                raw_channels = [
                    (s['name'], f"{ROCKET_BASE}/live/{USER}/{PASS}/{s['stream_id']}.ts") 
                    for s in raw_data if 'stream_id' in s
                ]
                
                total_streams = len(raw_channels)
                if total_streams == 0:
                    print("❌ No streams returned from the server.")
                    return
                    
                print(f"🔍 Found {total_streams} total streams. Verifying connections...\n")
        except Exception as e:
            print(f"❌ API Error: {e}")
            return

        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = [check_stream(session, sem, t, u, total_streams) for t, u in raw_channels]
        results = await asyncio.gather(*tasks)

        verified_list = [r for r in results if r[0] is not None]
        verified_list.sort(key=lambda x: x[0])

        if not verified_list:
            print("\n\n❌ All streams failed. The server might be blocking this script's IP.")
            return

        print(f"\n\n💾 Saving {len(verified_list)} results...")
        with open(FINAL_NAME, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for latency, title, url in verified_list:
                f.write(f'#EXTINF:-1, {title}\n{url}\n')

        print(f"✅ SUCCESS! Generated {FINAL_NAME}")

if __name__ == "__main__":
    asyncio.run(run())
