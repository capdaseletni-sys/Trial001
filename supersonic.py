import asyncio
import aiohttp
import time
from collections import defaultdict

# Settings for "Fast Only"
MIN_SPEED_KBPS = 500  # Minimum 500KB/s to be considered "fast"
MAX_TEST_TIMEOUT = 5  # If it takes more than 5s to get 100KB, it's too slow

async def check_stream(session, sem, entry):
    url = entry['url']
    async with sem:
        start_time = time.time()
        try:
            # Range header asks for exactly 100KB
            headers = {"Range": "bytes=0-102400", "User-Agent": USER_AGENT}
            async with session.get(url, headers=headers, timeout=MAX_TEST_TIMEOUT) as r:
                if r.status < 400:
                    content = await r.read()
                    duration = time.time() - start_time
                    
                    # 1. Verification: Did we get actual video data?
                    if len(content) >= 102400: 
                        # 2. Speed Calculation: (Bytes / 1024) / Seconds
                        speed_kbps = (len(content) / 1024) / duration
                        
                        if speed_kbps >= MIN_SPEED_KBPS:
                            return (duration, entry) # Lower duration = Faster
        except:
            pass
        return (None, None)

async def main():
    # ... (Keep your existing session and download logic) ...

    # Filter and Sort
    # results contains (latency, entry)
    working_results = [res for res in results if res[0] is not None]
    
    # SORTING: This puts the lowest latency (fastest) at the top
    working_results.sort(key=lambda x: x[0]) 

    final_list = []
    seen_urls = set()

    # Limit to top results if the list is too long
    for latency, item in working_results:
        if item['url'] not in seen_urls:
            # We keep only the best version of each stream
            final_list.append(item)
            seen_urls.add(item['url'])

    # Write to File
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in final_list:
            f.write(f"{item['extinf_raw']}\n{item['url']}\n")

    print(f"✅ Filtered {len(raw_entries)} down to {len(final_list)} high-speed streams.")
