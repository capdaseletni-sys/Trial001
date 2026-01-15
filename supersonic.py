import asyncio
import aiohttp
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

# ---------- FORGIVING CONFIG (MAXIMIZE SAVES) ----------
TIMEOUT = aiohttp.ClientTimeout(total=25)   # Wait up to 25s for slow servers
MAX_CONCURRENCY = 80                       # Moderate speed to avoid getting banned
MAX_HLS_DEPTH = 3

MIN_SPEED_KBPS = 400                        # Bare minimum to be "alive"
MAX_TTFB = 2.0                            # Allow very slow server responses
SAMPLE_BYTES = 16_000                      # Just need a tiny bit of data to verify
WARMUP_BYTES = 0                           # No warmup needed for basic check
RETRIES = 1                                

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

# ---------- GLOBAL COUNTERS ----------
processed_count = 0
fast_count = 0
total_tasks = 0

async def stream_is_alive(session, url, headers):
    """Verifies if a stream is reachable and sending any data."""
    try:
        start = time.perf_counter()
        # Using GET directly as some servers block HEAD
        async with session.get(url, headers=headers, timeout=TIMEOUT) as r:
            if r.status >= 400: return False
            
            first_byte_time = None
            measured = 0
            
            # If we get even 1 chunk of data, it's alive!
            async for chunk in r.content.iter_chunked(4096):
                if first_byte_time is None:
                    first_byte_time = time.perf_counter()
                
                measured += len(chunk)
                if measured >= SAMPLE_BYTES:
                    break
            
            if measured > 0:
                return True
    except:
        return False
    return False

async def check_link(session, url, headers, depth=0):
    """Detects if M3U8 or TS and checks life."""
    if depth > MAX_HLS_DEPTH: return False
    
    # Xtream codes / Direct links
    if ".m3u8" not in url.lower():
        return await stream_is_alive(session, url, headers)

    # M3U8 Manifests
    try:
        async with session.get(url, headers=headers, timeout=10) as r:
            if r.status >= 400: return False
            text = await r.text()
            if not text.startswith("#EXTM3U"): return False
            
            lines = text.splitlines()
            # Try to find the first playable segment or variant
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    if line.startswith("#EXT-X-STREAM-INF"):
                        continue # We'll check the next line for URL
                    continue
                
                # Check the first URL found in the manifest
                target_url = urljoin(url, line)
                return await stream_is_alive(session, target_url, headers)
    except:
        return False
    return False

def update_progress():
    global processed_count, fast_count, total_tasks
    percent = (processed_count / total_tasks * 100) if total_tasks > 0 else 0
    sys.stdout.write(f"\rScanning: {percent:.1f}% ({processed_count}/{total_tasks}) | Saved: {fast_count}")
    sys.stdout.flush()

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
                title = "UNTITLED"
                if extinf:
                    parts = extinf[0].split(",", 1)
                    title = parts[1].strip() if len(parts) == 2 else "UNTITLED"
                
                group = urlparse(url).netloc.upper()
                results.append((title.upper(), group, extinf, vlcopts, url))
                fast_count += 1
        
        processed_count += 1
        if processed_count % 10 == 0: update_progress()
        queue.task_done()

async def main(input_paths, output_path):
    global total_tasks
    queue, results, all_entries = asyncio.Queue(), [], []
    
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
                    all_entries.append((curr_extinf.copy(), curr_vlc.copy(), line))
                    curr_extinf, curr_vlc = [], []
    
    total_tasks = len(all_entries)
    if total_tasks == 0: return print("No links found.")

    print(f"Broad Scanning {total_tasks} channels...")
    
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENCY, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        workers = [asyncio.create_task(worker(queue, session, semaphore, results)) for _ in range(MAX_CONCURRENCY)]
        for entry in all_entries: await queue.put(entry)
        for _ in workers: await queue.put(None)
        await queue.join()

    results.sort(key=lambda x: (x[1], x[0]))
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for title, group, extinf, vlc, url in results:
            if extinf:
                dur = extinf[0].split(",", 1)[0].split(":")[-1]
                f.write(f'#EXTINF:{dur} group-title="{group}", {title}\n')
            for v in vlc: f.write(v + "\n")
            f.write(url + "\n")
    print(f"\n\n✅ Finished! Successfully saved {len(results)} links.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 supersonic.py output.m3u input1.m3u ...")
    else:
        asyncio.run(main(sys.argv[2:], sys.argv[1]))
