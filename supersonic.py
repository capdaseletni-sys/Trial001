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

MAX_TIMEOUT = 5          
MAX_CONCURRENCY = 40  # Increased for faster processing since we are checking all
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Removed BLOCKED_URL_PARTS as requested
# ==========================================

def extract_and_clean_group(extinf: str, title: str) -> str:
    """Forces 'Cord-Cutter' group, or 'Live Cam' if title matches."""
    return "Live Cam" if "cam" in title.lower() else "Cord-Cutter"

def rebuild_extinf(extinf: str, new_group: str) -> str:
    """Updates the group-title in the EXTINF string."""
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
                if url.startswith("http"):
                    entries.append({"title": title, "extinf_raw": extinf, "url": url})
    return entries

async def check_stream(session, sem, entry):
    """Returns (latency, entry) if working, else (None, None)"""
    url = entry['url']
    async with sem:
        start_time = time.time()
        try:
            # Check availability and speed
            async with session.head(url, timeout=MAX_TIMEOUT, allow_redirects=True) as r:
                if r.status < 400:
                    return (time.time() - start_time, entry)
        except: pass
        try:
            # Fallback for servers that block HEAD
            async with session.get(url, headers={"Range": "bytes=0-100"}, timeout=MAX_TIMEOUT) as r:
                if r.status < 400:
                    return (time.time() - start_time, entry)
        except: pass
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
            print("❌ No streams found."); return

        print(f"⚡ Testing {len(raw_entries)} streams and sorting by speed...")
        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        check_tasks = [check_stream(session, sem, entry) for entry in raw_entries]
        results = await asyncio.gather(*check_tasks)
        
        # Keep only working ones and sort by fastest latency
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
            # Writes groups, and within groups, streams are ordered by speed
            for group in sorted(final_list.keys()):
                for item in final_list[group]:
                    f.write(f"{item['extinf']}\n{item['url']}\n")
        
        print(f"🏁 Done! Saved {len(seen_urls)} working streams to {OUTPUT_FILE}.")
        print(f"All streams grouped under 'Cord-Cutter' (or 'Live Cam').")

if __name__ == "__main__":
    asyncio.run(main())
