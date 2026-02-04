import re
import asyncio
import aiohttp
import time
from collections import defaultdict

# ================= CONFIG =================
OUTPUT_FILE = "supersonic.m3u8"
SOURCES = [
    "http://tvmate.icu:8080/get.php?username=n8T4rE&password=204739&type=m3u_plus",
]

MAX_TIMEOUT = 4          
MAX_CONCURRENCY = 20     # Lowered slightly to give more bandwidth to each test
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

BLOCKED_PATHS = [
    "http://tvmate.icu:8080/movie",
    "http://tvmate.icu:8080/series"
]
# ==========================================

def extract_and_clean_group(extinf: str, title: str) -> str:
    return "Live Cam" if "cam" in title.lower() else "Cord-Cutter"

def rebuild_extinf(extinf: str, new_group: str) -> str:
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
                if url.startswith("http") and not any(url.startswith(path) for path in BLOCKED_PATHS):
                    entries.append({"title": title, "extinf_raw": extinf, "url": url})
    return entries

async def check_stream(session, sem, entry):
    """
    Downloads a small burst of data (100KB) to verify real speed.
    """
    url = entry['url']
    async with sem:
        start_time = time.time()
        try:
            # Requesting a small chunk (100KB) to test actual throughput
            headers = {"Range": "bytes=0-102400", "User-Agent": USER_AGENT}
            async with session.get(url, headers=headers, timeout=MAX_TIMEOUT) as r:
                if r.status < 400:
                    content = await r.read()
                    # Verify we actually got data, not just a tiny error page
                    if len(content) > 1000:
                        latency = time.time() - start_time
                        return (latency, entry)
        except:
            pass
        return (None, None)

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    # Using a longer timeout for the initial download of the massive M3U source
    async with aiohttp.ClientSession(connector=connector) as session:
        print(f"📡 Downloading Source...")
        try:
            async with session.get(SOURCES[0], timeout=60) as res:
                if res.status != 200:
                    print("❌ Failed to download source.")
                    return
                text = await res.text()
        except Exception as e:
            print(f"❌ Error: {e}")
            return

        raw_entries = parse_m3u_content(text)
        if not raw_entries:
            print("❌ No valid streams found."); return

        print(f"⚡ Testing {len(raw_entries)} streams with 100KB Burst Test...")
        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        check_tasks = [check_stream(session, sem, entry) for entry in raw_entries]
        results = await asyncio.gather(*check_tasks)
        
        # Filter and sort by real transfer speed
        working_results = [res for res in results if res[0] is not None]
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
        
        print(f"🏁 Done! Saved {len(seen_urls)} verified streams.")
        print(f"Top result latency: {working_results[0][0]:.3f}s")

if __name__ == "__main__":
    asyncio.run(main())
