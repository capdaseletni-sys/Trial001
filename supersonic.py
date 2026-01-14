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

# VERY FAST ONLY
MIN_SPEED_KBPS = 1200        # ~1.2 MB/s
MAX_TTFB = 1.5              # seconds
SAMPLE_BYTES = 768_000
WARMUP_BYTES = 64_000
RETRIES = 1

# 1080p ENFORCEMENT
MIN_WIDTH = 1920
MIN_HEIGHT = 1080
MIN_BANDWIDTH = 5_000_000   # fallback if RESOLUTION missing

# GROUP FILTER
REQUIRED_GROUP_KEYWORD = "xxx"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

BLOCKED_DOMAINS = {
    "amagi.tv",
    "ssai2-ads.api.leiniao.com",
}

# ---------- SPEED TEST ----------

async def stream_is_fast(session, url, headers):
    for _ in range(RETRIES):
        try:
            start = time.perf_counter()
            now = start

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

                if not speed_start_time or measured < SAMPLE_BYTES * 0.9:
                    return False

                ttfb = first_byte_time - start
                duration = max(now - speed_start_time, 0.001)
                speed_kbps = (measured / 1024) / duration

                if ttfb <= MAX_TTFB and speed_kbps >= MIN_SPEED_KBPS:
                    return True

                if ttfb > MAX_TTFB * 1.5:
                    return False

        except Exception:
            pass

    return False

# ---------- HLS / STREAM CHECK ----------

async def is_stream_fast(session, url, headers, depth=0):
    if depth > MAX_HLS_DEPTH:
        return False

    for d in BLOCKED_DOMAINS:
        if d in url:
            return False

    if ".m3u8" not in url:
        return False  # non-HLS rejected (cannot verify 1080p)

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

    # ---------- MASTER PLAYLIST (1080p ENFORCED) ----------
    best_variant = None

    for i, line in enumerate(lines):
        if not line.startswith("#EXT-X-STREAM-INF"):
            continue

        attrs = line.split(":", 1)[-1]
        width = height = bandwidth = 0

        for attr in attrs.split(","):
            if attr.startswith("RESOLUTION="):
                try:
                    w, h = attr.split("=")[1].split("x")
                    width, height = int(w), int(h)
                except Exception:
                    pass
            elif attr.startswith("BANDWIDTH="):
                try:
                    bandwidth = int(attr.split("=")[1])
                except Exception:
                    pass

        if (
            (width >= MIN_WIDTH and height >= MIN_HEIGHT)
            or bandwidth >= MIN_BANDWIDTH
        ):
            if i + 1 < len(lines):
                uri = lines[i + 1].strip()
                if not uri.startswith("#"):
                    best_variant = urljoin(url, uri)
                    break

    if best_variant:
        return await is_stream_fast(
            session, best_variant, headers, depth + 1
        )

    # ---------- MEDIA PLAYLIST ----------
    segments = [l for l in lines if l and not l.startswith("#")]
    if len(segments) < 2:
        return False

    for seg in segments[:2]:
        if not await stream_is_fast(
            session, urljoin(url, seg), headers
        ):
            return False

    return True

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

# ---------- WORKER ----------

async def worker(queue, session, semaphore, results):
    while True:
        entry = await queue.get()
        if entry is None:
            queue.task_done()
            return

        extinf, vlcopts, url = entry

        # ---- GROUP-TITLE FILTER (XXX ONLY) ----
        if extinf:
            line = extinf[0].lower()
            if 'group-title="' in line:
                group = line.split('group-title="', 1)[1].split('"', 1)[0]
                if REQUIRED_GROUP_KEYWORD not in group:
                    queue.task_done()
                    continue

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
                    continue

            title = ""
            if extinf:
                parts = extinf[0].split(",", 1)
                title = parts[1].strip() if len(parts) == 2 else ""
                extinf[0] = (
                    f'{parts[0]} group-title="Fast",{parts[1]}'
                    if len(parts) == 2
                    else f'{parts[0]} group-title="Fast"'
                )

            results.append((title.lower(), extinf, vlcopts, url))
            print(f"✓ FAST 1080p XXX: {title}")

        finally:
            queue.task_done()

# ---------- MAIN ----------

async def filter_fast_streams(input_path, output_path):
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

    results.sort(key=lambda x: x[0])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for _, extinf, vlcopts, url in results:
            for line in extinf + vlcopts + [url]:
                f.write(line + "\n")

    print(f"\nSaved FAST 1080p XXX playlist to: {output_path}")

# ---------- CLI ----------

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python fast_filter.py input.m3u output.m3u")
        sys.exit(1)

    if not Path(sys.argv[1]).exists():
        print("Input file does not exist.")
        sys.exit(1)

    asyncio.run(filter_fast_streams(sys.argv[1], sys.argv[2]))
