import asyncio
import aiohttp
import time
import re
from curl_cffi import requests as curl_requests

# --- CONFIGURATION ---
USER = "Z3nXfkOnf0"
PASS = "Madt8rUvmN"
ROCKET_BASE = "http://s.rocketdns.info:8080"
FINAL_NAME = "supersonic.m3u8"

# Performance Settings
MAX_CONCURRENCY = 30  
TEST_TIMEOUT = 5      
USER_AGENT = "IPTVSmartersPlayer"

async def check_stream(session, sem, title, url):
    """Downloads a small burst to verify the stream is fast and alive."""
    async with sem:
        try:
            start_time = time.time()
            # Range header verifies real data flow, not just a 200 OK header
            headers = {"User-Agent": USER_AGENT, "Range": "bytes=0-102400"}
            async with session.get(url, headers=headers, timeout=TEST_TIMEOUT) as r:
                if r.status < 400:
                    content = await r.read()
                    if len(content) > 1000:
                        latency = time.time() - start_time
                        return (latency, title, url)
        except:
            pass
        return (None, None, None)

def get_all_from_api():
    """Extracts ALL channels from the RocketDNS API without category filters."""
    channels = []
    # Using curl_cffi to bypass potential TLS/Fingerprint blocks
    with curl_requests.Session() as session:
        session.headers = {"User-Agent": USER_AGENT}
        print(f"📡 Connecting to {ROCKET_BASE}...")
        try:
            api_url = f"{ROCKET_BASE}/player_api.php"
            # Getting ALL live streams via API
            params = {"username": USER, "password": PASS, "action": "get_live_streams"}
            res = session.get(api_url, params=params).json()
            
            for s in res:
                stream_url = f"{ROCKET_BASE}/live/{USER}/{PASS}/{s['stream_id']}.ts"
                channels.append((s['name'], stream_url))
        except Exception as e:
            print(f"❌ API Fetch Failed: {e}")
            
    return channels

async def verify_and_sort(raw_channels):
    """Tests streams concurrently and ranks them by speed."""
    print(f"⚡ Testing {len(raw_channels)} streams for speed and availability...")
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = [check_stream(session, sem, t, u) for t, u in raw_channels]
        results = await asyncio.gather(*tasks)
        
        # Keep only working results and sort by fastest (lowest latency)
        working = [r for r in results if r[0] is not None]
        working.sort(key=lambda x: x[0])
        return working

def run():
    # 1. Pull the data
    raw_list = get_all_from_api()
    if not raw_list:
        print("❌ No data retrieved. Check credentials.")
        return

    # 2. Test the data
    verified_list = asyncio.run(verify_and_sort(raw_list))

    # 3. Save the data
    with open(FINAL_NAME, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for latency, title, url in verified_list:
            # We add the latency to the title so you can see the speed in your player
            f.write(f'#EXTINF:-1, {title} [{latency:.2f}s]\n{url}\n')

    print(f"✅ SUCCESS! Saved {len(verified_list)} fast streams to {FINAL_NAME}")

if __name__ == "__main__":
    run()
