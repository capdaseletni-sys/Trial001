import re
import asyncio
import aiohttp
import time
from collections import defaultdict

# ================= CONFIG =================
OUTPUT_FILE = "supersonic.m3u8"
SOURCES = [
    "http://tvmate.icu:8080/get.php?username=n8T4rE&password=204739&type=m3u_plus"
]

# Strictly remove any stream taking longer than 4 seconds
MAX_TIMEOUT = 4          
MAX_CONCURRENCY = 40     
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# EXCLUSION - Explicitly block VOD paths
BLOCKED_PATHS = [
    "http://tvmate.icu:8080/movie",
    "http://tvmate.icu:8080/series"
]
# ==========================================

def extract_and_clean_group(extinf: str, title: str) -> str:
    """Assigns 'Cord-Cutter' group, or 'Live Cam' if title matches."""
    return "Live Cam" if "cam" in title.lower() else "Cord-Cutter"

def rebuild_extinf(extinf: str, new_group: str) -> str:
    """Injects or replaces group-title in the EXTINF line."""
    if 'group-title="' in extinf:
        return re.sub(r'group-title="[^"]*"', f'group-title="{new_group}"', extinf)
    return extinf.replace(",", f' group-title="{new_group}",', 1)

def parse_m3u_content(content):
    entries = []
    lines = content.splitlines()
    for i in range(len(lines)):
        if lines[i].startswith("#EXTINF"):
            extinf = lines[i].strip()
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                title = extinf.split(",")[-1].strip()
                
                # Check if URL starts with HTTP and is NOT in the blocked VOD paths
                if url.startswith("http"):
                    if not any(url.startswith(path) for path in BLOCKED_PATHS):
                        entries.append({"title": title, "extinf_raw": extinf, "url": url})
    return entries

async def check_stream(session, sem, entry):
    """Returns (latency, entry) if it responds within 4 seconds, else (None, None)"""
    url = entry['url']
    async with sem:
        start_time = time.time()
        try:
            # First attempt: HEAD request (Fastest)
            async with session.head(url, timeout=MAX_TIMEOUT, allow_redirects=True) as r:
                if r.status < 400:
                    latency = time.time() - start_time
                    return (latency, entry)
        except: 
            pass 
            
        try:
            # Second attempt: GET request with minimal byte range
            async with session.get(url, headers={"Range": "bytes=0-100"}, timeout=MAX_TIMEOUT) as r:
                if r.status < 400:
                    latency = time.time() - start_time
                    if latency <= MAX_TIMEOUT:
                        return (latency, entry)
        except:
            pass
            
        return (None, None)

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": USER_AGENT}) as session:
        print(f"📡 Downloading Source...")
        tasks = [session.get(url, timeout=30) for url in SOURCES]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        raw_entries = []
        for res in responses:
            if isinstance(res, aiohttp.ClientResponse) and res.status == 200:
                raw_entries.extend(parse_m3u_content(await res.text()))
        
        if not raw_entries:
            print("❌ No valid streams found (after filtering VOD).")
            return

        print(f"⚡ Testing {len(raw_entries)} streams. Max Wait: {MAX_TIMEOUT}s...")
        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        check_tasks = [check_stream(session, sem, entry) for entry in raw_entries]
        results = await asyncio.gather(*check_tasks)
        
        # Filter for working streams
        working_results = [res for res in results if res[0] is not None]
        
        # Sort by fastest to slowest
        working_results.sort(key=lambda x: x[0]) 
        
        final_list = defaultdict(list)
        seen_urls = set()
        
        for latency, item in working_results:
            if item['url'] not in seen_urls:
                group = extract_and_clean_group(item['extinf_raw'], item['title'])
                item['extinf'] = rebuild_extinf(item['extinf_raw'], group)
                final_list[group].append(item)
                seen_urls.add(item['url'])

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for group in sorted(final_list.keys()):
                for item in final_list[group]:
                    f.write(f"{item['extinf']}\n{item['url']}\n")
        
        print(f"🏁 Done! Saved {len(seen_urls)} fast streams to {OUTPUT_FILE}.")
        print(f"VOD paths (movie/series) were automatically excluded.")

if __name__ == "__main__":
    asyncio.run(main())
