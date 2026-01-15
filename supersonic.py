import asyncio
import aiohttp
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

# ---------- CONFIG ----------
TIMEOUT = aiohttp.ClientTimeout(total=15)
MAX_CONCURRENCY = 80
MAX_HLS_DEPTH = 3
MIN_SPEED_KBPS = 300
MAX_TTFB = 6.0
SAMPLE_BYTES = 384_000
WARMUP_BYTES = 8_000 
RETRIES = 2
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}
BLOCKED_DOMAINS = {"amagi.tv", "ssai2-ads.api.leiniao.com"}
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi")

# ---------- GLOBAL COUNTERS ----------
processed_count = 0
fast_count = 0
total_tasks = 0

# ---------- HOST CACHE & LOCKS ----------
host_cache = {}
host_lock = asyncio.Lock()

async def stream_is_fast(session, url, headers):
    for attempt in range(RETRIES):
        try:
            start = time.perf_counter()
            async with session.get(url, headers=headers, timeout=TIMEOUT) as r:
                if r.status >= 400: return False
                first_byte_time, speed_start_time, total, measured = None, None, 0, 0
                async for chunk in r.content.iter_chunked(8192):
                    now = time.perf_counter()
                    if first_byte_time is None: first_byte_time = now
                    total += len(chunk)
                    if total < WARMUP_BYTES: continue
                    if speed_start_time is None: speed_start_time = now
                    measured += len(chunk)
                    if measured >= SAMPLE_BYTES: break
                
                if not speed_start_time: continue
                ttfb = first_byte_time - start
                duration = max(now - speed_start_time, 0.001)
                speed_kbps = (measured / 1024) / duration
                return ttfb <= MAX_TTFB and speed_kbps >= MIN_SPEED_KBPS
        except: pass
        await asyncio.sleep(0.1 * (attempt + 1))
    return False

async def is_stream_fast(session, url, headers, depth=0):
    for d in BLOCKED_DOMAINS:
        if d in url: return False
    if depth > MAX_HLS_DEPTH: return False
    if ".m3u8" not in url.lower():
        return await stream_is_fast(session, url, headers)
    try:
        async with session.get(url, headers=headers) as r:
            if r.status >= 400: return False
            text = await r.text()
    except: return False
    if not text.startswith("#EXTM3U"): return False
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
            variant_url = urljoin(url, lines[i + 1].strip())
            return await is_stream_fast(session, variant_url, headers, depth + 1)
    segments = [l for l in lines if l and not l.startswith("#")]
    if segments: return await stream_is_fast(session, urljoin(url, segments[0]), headers)
    return False

async def host_allowed(session, url, headers):
    host = urlparse(url).netloc
    async with host_lock:
        if host in host_cache: return host_cache[host]
    fast = await is_stream_fast(session, url, headers)
    async with host_lock:
        host_cache[host] = bool(fast)
    return fast

def get_group_title_from_url(url):
    host = urlparse(url).netloc.lower()
    if host.startswith("www."): host = host[4:]
    return host.split(".")[0].upper()

def update_progress():
    global processed_count, fast_count, total_tasks
    percent = (processed_count / total_tasks * 100) if total_tasks > 0 else 0
    bar_width = 40
    filled = int(bar_width * percent / 100)
    bar = "█" * filled + "-" * (bar_width - filled)
    sys.stdout.write(f"\r|{bar}| {percent:.1f}% ({processed_count}/{total_tasks}) - Found: {fast_count}")
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
                key, value = content.split("=", 1)
                k = key.lower()
                if k == "http-referrer": headers["Referer"] =
