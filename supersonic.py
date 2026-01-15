import asyncio
import aiohttp
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

# ---------- ADJUSTED CONFIG FOR MAXIMUM RESULTS ----------
TIMEOUT = aiohttp.ClientTimeout(total=20)   # 20 seconds to allow for slow handshakes
MAX_CONCURRENCY = 50                       # Lowered slightly to prevent IP blocking
MAX_HLS_DEPTH = 3

MIN_SPEED_KBPS = 300                       # Minimal speed for SD/Compressed HD
MAX_TTFB = 5.0                            # Very generous time for server response
SAMPLE_BYTES = 256_000                     # Smaller sample for faster individual tests
WARMUP_BYTES = 4_000                       # Minimal warmup
RETRIES = 1                                

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi")

# ---------- GLOBAL COUNTERS ----------
processed_count = 0
fast_count = 0
total_tasks = 0

async def stream_is_fast(session, url, headers):
    """Performs a real-time speed and availability test on a single stream."""
    try:
        start = time.perf_counter()
        async with session.get(url, headers=headers, timeout=TIMEOUT) as r:
            if r.status >= 400: return False
            
            first_byte_time = None
            speed_start_time = None
            total = 0
            measured = 0
            
            async for chunk in r.content.iter_chunked(8192):
                now = time.perf_counter()
                if first_byte_time is None:
                    first_byte_time = now
                
                total += len(chunk)
                if total < WARMUP_BYTES: continue
                if speed_start_time is None: speed_start_time = now

                measured += len(chunk)
                # Break if we have enough data or if it's taking too long (5s max data read)
                if measured >= SAMPLE_BYTES or (now - speed_start_time) > 5:
                    break
            
            if not speed_start_time: return False
            
            ttfb = first_byte_time - start
            duration = max(now - speed_start_time, 0.001)
            speed_kbps = (measured / 1024) / duration

            # Return True if server responds within limit and meets min speed
            return ttfb <= MAX_TTFB and speed_kbps >= MIN_SPEED_KBPS
    except:
        return False

async def is_stream_fast(session, url, headers, depth=0):
    """Determines if the URL is an M3U8 manifest or a direct stream and tests accordingly."""
    if depth > MAX_HLS_DEPTH: return False
    
    # Check for direct TS/numeric streams (Xtream Codes style)
    is_m3u8 = ".m3u8" in url.lower()
    
    if not is_m3u8:
        return await stream_is_fast(session, url, headers)

    try:
        async with session.get(url, headers=headers) as r:
            if r.status >= 400: return False
            text = await r.text()
    except: return False

    if not text.startswith("#EXTM3U"): return False
    lines = text.splitlines()
    
    # Handle Master Playlists (Variant Streams)
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
            variant_url = urljoin(url, lines[i + 1].strip())
            return await is_stream_fast(session, variant_url, headers, depth + 1)

    # Handle Media Playlists (Segments)
    segments = [l for l in lines if l and not l.startswith("#")]
    if segments:
        return await stream_is_fast(session, urljoin(url, segments[0]), headers)
    return False

def update_progress():
    global processed_count, fast_count, total_tasks
    percent = (processed_count / total_tasks * 100) if total_tasks > 0 else 0
    sys.stdout.write(f"\rScanning: {percent:.1f}% ({processed_count}/{total_tasks}) | Playable: {fast_count}")
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
            # EVERY stream is tested individually now
            if await is_stream_fast(session, url, headers):
                title = "UNTITLED"
                if extinf:
                    parts = extinf[0].split(",", 1)
                    title = parts[1].strip() if len(parts) == 2 else "UNTITLED"
                
                # Get Domain for Grouping
                group = urlparse(url).netloc.upper()
                results.append((title.upper(), group, extinf, vlcopts, url))
                fast_count += 1
        
        processed_count += 1
        update_progress()
        queue.task_done()

async def main(input_paths, output_path):
    global total_tasks
    queue, results, all_entries = asyncio.Queue(), [], []
    
    # Parse all input files
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

    print(f"Deep Scanning {total_tasks} channels (Individual Test)...")
    
    # TCPConnector configuration for high-volume individual testing
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENCY, ssl=False, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        workers = [asyncio.create_task(worker(queue, session, semaphore, results)) for _ in range(MAX_CONCURRENCY)]
        
        for entry in all_entries: await queue.put(entry)
        for _ in workers: await queue.put(None)
        
        await queue.join()

    # Final Sort and Save
    results.sort(key=lambda x: (x[1], x[0]))
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for title, group, extinf, vlc, url in results:
            if extinf:
                dur = extinf[0].split(",", 1)[0].split(":")[-1]
                f.write(f'#EXTINF:{dur} group-title="{group}", {title}\n')
            for v in vlc: f.write(v + "\n")
            f.write(url + "\n")
    print(f"\n\n✅ Done! Found {len(results)} playable streams.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 supersonic.py output.m3u input1.m3u ...")
    else:
        asyncio.run(main(sys.argv[2:], sys.argv[1]))
