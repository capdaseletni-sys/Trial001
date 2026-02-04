import re
import asyncio
import aiohttp
from collections import defaultdict

# ================= CONFIG =================
OUTPUT_FILE = "supersonic.m3u8"
SOURCES = [
    "http://server.iptvxxx.net/get.php?username=77569319&password=43886568&type=m3u_plus"
]

MAX_TIMEOUT = 5          
MAX_CONCURRENCY = 25     
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# EXCLUSION RULES
BLOCKED_URL_PARTS = [
    "https://xc.adultiptv.net/movie", 
    "/movie/", 
    "/series/", 
    "S01", "E01", "Season"
]

VALID_STREAM_EXTENSIONS = (".m3u8", ".ts", ".mpegts")
# ==========================================

def is_readable_and_allowed(url: str, title: str) -> bool:
    url_lower = url.lower()
    
    # Block specific movie domains and VOD keywords
    if any(part in url_lower for part in BLOCKED_URL_PARTS):
        return False
    
    # Block standard movie file extensions
    if any(url_lower.endswith(ext) for ext in [".mp4", ".mkv", ".avi", ".mov"]):
        return False
        
    # Allow live stream patterns
    if any(url_lower.endswith(ext) for ext in VALID_STREAM_EXTENSIONS):
        return True
    if "/live/" in url_lower or "get.php" in url_lower:
        return True
        
    return False

def extract_and_clean_group(extinf: str, title: str) -> str:
    """Extracts group and forces 'Live Cam' if title matches."""
    if "cam" in title.lower():
        return "Live Cam"
        
    match = re.search(r'group-title="([^"]*)"', extinf)
    return match.group(1) if match else "Uncategorized"

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
                
                if url.startswith("http") and is_readable_and_allowed(url, title):
                    # Determine Group
                    group = extract_and_clean_group(extinf, title)
                    # Update EXTINF line with the new group
                    clean_extinf = rebuild_extinf(extinf, group)
                    
                    entries.append({
                        "title": title, 
                        "extinf": clean_extinf, 
                        "url": url, 
                        "group": group
                    })
    return entries

async def check_stream(session, sem, entry):
    url = entry['url']
    async with sem:
        try:
            async with session.head(url, timeout=MAX_TIMEOUT, allow_redirects=True) as r:
                if r.status < 400: return True
        except: pass
        try:
            headers = {"Range": "bytes=0-1024"}
            async with session.get(url, headers=headers, timeout=MAX_TIMEOUT) as r:
                if r.status < 400: return True
        except: pass
        return False

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    headers = {"User-Agent": USER_AGENT}
    
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        print(f"📡 Downloading Source...")
        tasks = [session.get(url, timeout=30) for url in SOURCES]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        raw_entries = []
        for res in responses:
            if isinstance(res, aiohttp.ClientResponse) and res.status == 200:
                text = await res.text()
                raw_entries.extend(parse_m3u_content(text))
        
        if not raw_entries:
            print("❌ No readable streams found.")
            return

        print(f"⚡ Validating {len(raw_entries)} streams...")
        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        check_tasks = [check_stream(session, sem, entry) for entry in raw_entries]
        check_results = await asyncio.gather(*check_tasks)
        
        working_entries = [raw_entries[i] for i, ok in enumerate(check_results) if ok]
        
        final_list = defaultdict(list)
        seen_urls = set()
        
        for item in working_entries:
            if item['url'] not in seen_urls:
                final_list[item['group']].append(item)
                seen_urls.add(item['url'])

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for group in sorted(final_list.keys()):
                for item in sorted(final_list[group], key=lambda x: x['title']):
                    f.write(f"{item['extinf']}\n{item['url']}\n")
        
        print(f"🏁 Done! {len(seen_urls)} streams saved. 'Live Cam' group created.")

if __name__ == "__main__":
    asyncio.run(main())
