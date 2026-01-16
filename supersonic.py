import asyncio
import aiohttp
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

# ---------- HIGH-SPEED CONFIG (600K OPTIMIZED) ----------
TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)  # Fast fail for dead servers
MAX_CONCURRENCY = 500         # High concurrency for large lists
MAX_HLS_DEPTH = 2             # Fewer jumps for M3U8s
SAMPLE_BYTES = 16_000         # Just need 16KB to prove it's alive (Huge speed boost)
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Range": "bytes=0-16384"   # Ask server for only the first chunk
}

# ---------- GLOBAL COUNTERS ----------
processed_count = 0
fast_count = 0
total_tasks = 0

async def stream_is_alive(session, url, headers):
    try:
        async with session.get(url, headers=headers, timeout=TIMEOUT) as r:
            if r.status >= 400: return False
            
            # If we get even 1 chunk of data, it's alive!
            measured = 0
            async for chunk in r.content.iter_chunked(4096):
                measured += len(chunk)
                if measured > 0: return True # Instant success
                if measured >= SAMPLE_BYTES: break
            return measured > 0
    except:
        return False

async def check_link(session, url, headers, depth=0):
    if depth > MAX_HLS_DEPTH: return False
    
    # Check non-m3u8 links directly (TS, MP4, etc)
    if ".m3u8" not in url.lower():
        return await stream_is_alive(session, url, headers)

    # M3U8 Manifest handling
    try:
        async with session.get(url, headers=headers, timeout=5) as r:
            if r.status >= 400: return False
            text = await r.text()
            if not text.startswith("#EXTM3U"): return False
            
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"): continue
                
                target_url = urljoin(url, line)
                return await stream_is_alive(session, target_url, headers)
    except:
        return False
    return False

async def worker(queue, session, semaphore, results):
    global processed_count, fast_count
    while True:
        entry = await queue.get()
        if entry is None:
            queue.task_done()
            break
        
        extinf, vlcopts, url = entry
        headers = DEFAULT_HEADERS.copy()
        for opt in vlcopts:
            content = opt[len("#EXTVLCOPT:"):].strip()
            if "=" in content:
                k, v = content.split("=", 1)
                if k.lower() == "http-user-agent": headers["User-Agent"] = v
                elif k.lower() == "http-referrer": headers["Referer"] = v

        async with semaphore:
            if await check_link(session, url, headers):
                group = urlparse(url).netloc.upper()
                results.append((group, extinf, vlcopts, url))
                fast_count += 1
        
        processed_count += 1
        if processed_count % 100 == 0:
            sys.stdout.write(f"\rScanning: {(processed_count/total_tasks*100):.1f}% | Alive: {fast_count}")
            sys.stdout.flush()
        queue.task_done()

async def main(input_paths, output_path):
    global total_tasks
    queue, results, all_entries = asyncio.Queue(), [], []
    seen_urls = set() # Duplicate filter

    print("📖 Loading files and removing duplicates...")
    for path in input_paths:
        p = Path(path)
        if not p.exists(): continue
        curr_extinf, curr_vlc = [], []
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#EXTINF"): curr_extinf = [line]
                elif line.startswith("#EXTVLCOPT"): curr_vlc.append(line)
                elif line.startswith(("http://", "https://")):
                    if line not in seen_urls: # Filter
                        all_entries.append((curr_extinf.copy(), curr_vlc.copy(), line))
                        seen_urls.add(line)
                    curr_extinf, curr_vlc = [], []
    
    total_tasks = len(all_entries)
    if total_tasks == 0: return print("No links found.")
    print(f"🚀 Processing {total_tasks} unique channels (Concurrency: {MAX_CONCURRENCY})")
    
    # Optimized Connector with DNS Caching
    connector = aiohttp.TCPConnector(
        limit=MAX_CONCURRENCY, 
        ssl=False, 
        use_dns_cache=True, 
        ttl_dns_cache=300
    )
    
    async with aiohttp.ClientSession(connector=connector) as session:
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        workers = [asyncio.create_task(worker(queue, session, semaphore, results)) for _ in range(MAX_CONCURRENCY)]
        
        for entry in all_entries: await queue.put(entry)
        for _ in workers: await queue.put(None)
        await queue.join()

    print(f"\n💾 Saving {len(results)} working links...")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for group, extinf, vlc, url in results:
            if extinf: f.write(extinf[0] + "\n")
            for v in vlc: f.write(v + "\n")
            f.write(url + "\n")
    print("✨ All tasks complete.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python forcem3u.py output.m3u input1.m3u ...")
    else:
        asyncio.run(main(sys.argv[2:], sys.argv[1]))
