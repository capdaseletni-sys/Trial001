import re
import asyncio
import aiohttp
import time
from collections import defaultdict

# ================= CONFIG =================
OUTPUT_FILE = "supersonic.m3u8"
SOURCES = [
    "http://tvmate.icu:8080/get.php?username=n8T4rE&password=204739&type=m3u_plus",
    "http://ultrapremium.cloud:8080/get.php?username=945527550tv&password=jT670E3aM&type=m3u"  # <--- Add your second link here
]

MAX_TIMEOUT = 4          
MAX_CONCURRENCY = 20     
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# VOD Blocking
BLOCKED_PATHS = ["/movie", "/series"]
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
                # Clean up path check to work across different providers
                if url.startswith("http") and not any(p in url.lower() for p in BLOCKED_PATHS):
                    entries.append({"title": title, "extinf_raw": extinf, "url": url})
    return entries

async def check_stream(session, sem, entry):
    url = entry['url']
    async with sem:
        start_time = time.time()
        try:
            # 100KB Burst Test for real-world speed verification
            headers = {"Range": "bytes=0-102400"}
            async with session.get(url, headers=headers, timeout=MAX_TIMEOUT) as r:
                if r.status < 400:
                    content = await r.read()
                    if len(content) > 1000:
                        latency = time.time() - start_time
                        return (latency, entry)
        except:
            pass
        return (None, None)

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": USER_AGENT}) as session:
        all_raw_entries = []
        
        # --- Multi-Source Download ---
        for url in SOURCES:
            print(f"📡 Downloading: {url[:50]}...")
            try:
                async with session.get(url, timeout=60) as res:
                    if res.status == 200:
                        text = await res.text()
                        all_raw_entries.extend(parse_m3u_content(text))
                    else:
                        print(f"⚠️ Source returned status {res.status}")
            except Exception as e:
                print(f"❌ Error downloading source: {e}")

        if not all_raw_entries:
            print("❌ No valid streams found across all sources."); return

        # --- Speed Testing ---
        print(f"⚡ Testing {len(all_raw_entries)} unique streams...")
        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        check_tasks = [check_stream(session, sem, entry) for entry in all_raw_entries]
        results = await asyncio.gather(*check_tasks)
        
        working_results = [res for res in results if res[0] is not None]
        working_results.sort(key=lambda x: x[0]) 
        
        # --- Deduplication and Formatting ---
        final_list = defaultdict(list)
        seen_urls = set()
        
        for latency, item in working_results:
            if item['url'] not in seen_urls:
                group = extract_and_clean_group(item['extinf_raw'], item['title'])
                item['extinf'] = rebuild_extinf(item['extinf_raw'], group)
                final_list[group].append(item)
                seen_urls.add(item['url'])

        # --- Saving File ---
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for group in sorted(final_list.keys()):
                for item in final_list[group]:
                    f.write(f"{item['extinf']}\n{item['url']}\n")
        
        print(f"🏁 Done! {len(seen_urls)} fast streams merged into {OUTPUT_FILE}.")

if __name__ == "__main__":
    asyncio.run(main())
