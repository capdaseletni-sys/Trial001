import asyncio
import aiohttp
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

# ---------- CONFIG ----------
TIMEOUT = aiohttp.ClientTimeout(total=12)
MAX_CONCURRENCY = 80
MAX_HLS_DEPTH = 3

MIN_SPEED_KBPS = 350
MAX_TTFB = 5.0
SAMPLE_BYTES = 384_000
WARMUP_BYTES = 32_000
RETRIES = 3

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}

BLOCKED_DOMAINS = {"amagi.tv", "ssai2-ads.api.leiniao.com"}
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi")

# ---------- SPEED TEST ----------
async def stream_is_fast(session, url, headers):
    for attempt in range(RETRIES):
        try:
            start = time.perf_counter()
            async with session.get(url, headers=headers) as r:
                if r.status >= 400:
                    return False

                first_byte_time = None
                speed_start_time = None
                total = 0
                measured = 0

                async for chunk in r.content.iter_chunked(8192):
                    now = time.perf_counter()
                    if first_byte_time is None:
                        first_byte_time = now

                    total += len(chunk)
                    if total < WARMUP_BYTES:
                        continue

                    if speed_start_time is None:
                        speed_start_time = now

                    measured += len(chunk)
                    if measured >= SAMPLE_BYTES:
                        break

                if not speed_start_time:
                    continue

                ttfb = first_byte_time - start
                duration = max(now - speed_start_time, 0.001)
                speed_kbps = (measured / 1024) / duration

                if ttfb <= MAX_TTFB and speed_kbps >= MIN_SPEED_KBPS:
                    return True

        except Exception:
            pass

        await asyncio.sleep(0.2 * (attempt + 1))
    return False

# ---------- HLS / STREAM CHECK ----------
async def is_stream_fast(session, url, headers, depth=0):
    for d in BLOCKED_DOMAINS:
        if d in url:
            return False

    if url.lower().endswith(VIDEO_EXTENSIONS):
        return False

    if depth > MAX_HLS_DEPTH:
        return False

    if ".m3u8" not in url:
        return await stream_is_fast(session, url, headers)

    try:
        async with session.get(url, headers=headers) as r:
            if r.status >= 400:
                return False
            text = await r.text()
    except Exception:
        return False

    if not text.startswith("#EXTM3U"):
        return False

    lines = text.splitlines()

    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
            variant_url = urljoin(url, lines[i + 1].strip())
            if await is_stream_fast(session, variant_url, headers, depth + 1):
                return True

    segments = [l for l in lines if l and not l.startswith("#")]
    if not segments:
        return False

    return await stream_is_fast(session, urljoin(url, segments[0]), headers)

# ---------- HOST CACHE ----------
host_cache = {}
host_lock = asyncio.Lock()

async def host_allowed(session, url, headers):
    host = urlparse(url).netloc
    async with host_lock:
        if host in host_cache:
            return host_cache[host]
    fast = await is_stream_fast(session, url, headers)
    async with host_lock:
        host_cache[host] = bool(fast)
    return fast

# ---------- HELPER: Group title from URL ----------
def get_group_title_from_url(url):
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host.split(".")[0].upper()  # main domain, ALL CAPS

# ---------- WORKER ----------
async def worker(queue, session, semaphore, results):
    while True:
        entry = await queue.get()
        if entry is None:
            queue.task_done()
            return

        extinf, vlcopts, url = entry
        headers = {}

        for opt in vlcopts:
            key, _, value = opt[len("#EXTVLCOPT:"):].partition("=")
            k = key.lower()
            if k == "http-referrer":
                headers["Referer"] = value
            elif k == "http-origin":
                headers["Origin"] = value
            elif k == "http-user-agent":
                headers["User-Agent"] = value

        try:
            async with semaphore:
                if not await host_allowed(session, url, headers):
                    print(f"⚠ SKIPPED (host slow/blocked or invalid): {url}")
                    continue

            if url.lower().endswith(VIDEO_EXTENSIONS):
                print(f"⚠ SKIPPED (direct video file): {url}")
                continue

            title = ""
            if extinf:
                parts = extinf[0].split(",", 1)
                title = parts[1].strip() if len(parts) == 2 else ""

            title_upper = title.upper()
            group_title = get_group_title_from_url(url)
            results.append((title_upper, group_title, extinf, vlcopts, url))
            print(f"✓ FAST: {title_upper} ({url}) [Group: {group_title}]")

        finally:
            queue.task_done()

# ---------- MAIN ----------
async def filter_fast_streams_multiple(input_paths, output_path):
    queue = asyncio.Queue(maxsize=MAX_CONCURRENCY * 2)
    results = []

    connector = aiohttp.TCPConnector(
        limit=MAX_CONCURRENCY,
        limit_per_host=20,
        ttl_dns_cache=300,
        ssl=False,
        enable_cleanup_closed=True
    )

    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async with aiohttp.ClientSession(
        timeout=TIMEOUT,
        connector=connector,
        headers=DEFAULT_HEADERS,
    ) as session:

        workers = [
            asyncio.create_task(worker(queue, session, semaphore, results))
            for _ in range(MAX_CONCURRENCY)
        ]

        for input_path in input_paths:
            if not Path(input_path).exists():
                print(f"⚠ Input file does not exist: {input_path}")
                continue

            extinf, vlcopts = [], []
            with open(input_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#EXTINF"):
                        extinf = [line]
                    elif line.startswith("#EXTVLCOPT"):
                        vlcopts.append(line)
                    elif line.startswith(("http://", "https://")):
                        await queue.put((extinf.copy(), vlcopts.copy(), line))
                        extinf.clear()
                        vlcopts.clear()

        for _ in workers:
            await queue.put(None)

        await queue.join()
        for w in workers:
            await w

    # Sort playlist by group-title first, then title
    results.sort(key=lambda x: (x[1], x[0]))

    # Write playlist with uppercase title and uppercase group-title
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for title_upper, group_title, extinf, vlcopts, url in results:
            if extinf:
                parts = extinf[0].split(",", 1)
                duration = parts[0][len("#EXTINF:"):]
                line = f'#EXTINF:{duration} tvg-name="{title_upper}" group-title="{group_title}", {title_upper}'
                f.write(line + "\n")
            for line in vlcopts:
                f.write(line + "\n")
            f.write(url + "\n")

    print(f"\nSaved FAST playlist to: {output_path}")

# ---------- CLI ----------
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fast_filter.py output.m3u input1.m3u input2.m3u ...")
        sys.exit(1)

    output_file = sys.argv[1]
    input_files = sys.argv[2:]

    asyncio.run(filter_fast_streams_multiple(input_files, output_file))
