import re
import asyncio
import aiohttp
import time
from collections import defaultdict

INPUT_FILE = "supersonic.m3u8"
OUTPUT_FILE = "supersonic.m3u8"

# ================= CONFIG =================
MAX_TIMEOUT = 5          # seconds (fast streams only)
MAX_CONCURRENCY = 25     # safe for GitHub Actions
EXCLUDED_EXTENSIONS = (".mp4", ".mkv")
IGNORED_PREFIXES = ("hd", "fhd", "uhd", "4k", "8k")
# ==========================================

NAME_GROUPS = {
    "Documentary": ["discovery", "nat geo", "history", "animal"],
    "Entertainment": ["entertainment", "series", "show"],
    "Kids": ["kids", "cartoon", "nick", "disney"],
    "Movies": ["movie", "cinema", "film", "hbo", "starz"],
    "Music": ["music", "mtv", "vh1"],
    "News": ["cnn", "bbc", "fox news", "al jazeera", "sky news", "cnbc"],
    "Religious": ["islam", "quran", "christian", "church"],
    "Sports": ["sport", "espn", "beins", "sky sports", "fox sports"],
}

KEYWORD_GROUPS = {
    "News": ["news", "report", "live"],
    "Sports": ["match", "league", "cup", "football", "soccer"],
    "Movies": ["movie", "film", "cinema"],
    "Kids": ["kids", "cartoon", "baby"],
    "Music": ["music", "radio", "hits"],
}

# ---------- Helpers ----------
def normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"^[\[\(\{]?(hd|fhd|uhd|4k|8k)[\]\)\}]?\s*-?\s*", "", t)
    return re.sub(r"\s+", " ", t)

def detect_group(title: str) -> str:
    t = title.lower()
    for g, words in NAME_GROUPS.items():
        if any(w in t for w in words):
            return g
    for g, words in KEYWORD_GROUPS.items():
        if any(w in t for w in words):
            return g
    return "Mix"

def rebuild_extinf(extinf, group):
    if 'group-title="' in extinf:
        return re.sub(r'group-title="[^"]*"', f'group-title="{group}"', extinf)
    return extinf.replace("#EXTINF:-1", f'#EXTINF:-1 group-title="{group}"')

def parse_playlist(lines):
    entries = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            extinf = lines[i].strip()
            url = lines[i + 1].strip()

            if url.lower().endswith(EXCLUDED_EXTENSIONS):
                i += 2
                continue

            title = extinf.split(",")[-1].strip()
            entries.append((title, extinf, url))
            i += 2
        else:
            i += 1
    return entries

# ---------- Stream validation ----------
async def check_stream(session, sem, url):
    async with sem:
        start = time.monotonic()
        try:
            async with session.head(url, timeout=MAX_TIMEOUT, allow_redirects=True) as r:
                if r.status < 400:
                    return True, time.monotonic() - start
        except:
            pass

        # Fallback GET (range request)
        try:
            headers = {"Range": "bytes=0-1024"}
            async with session.get(url, headers=headers, timeout=MAX_TIMEOUT) as r:
                if r.status < 400:
                    return True, time.monotonic() - start
        except:
            pass

        return False, None

async def filter_fast_streams(entries):
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    timeout = aiohttp.ClientTimeout(total=MAX_TIMEOUT)
    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [
            check_stream(session, sem, url)
            for _, _, url in entries
        ]
        results = await asyncio.gather(*tasks)

    return [
        entries[i]
        for i, (ok, _) in enumerate(results)
        if ok
    ]

# ---------- Main ----------
def main():
    with open(INPUT_FILE, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    header = [l for l in lines if l.startswith("#EXTM3U")]
    entries = parse_playlist(lines)

    print(f"🔍 Checking {len(entries)} streams...")
    entries = asyncio.run(filter_fast_streams(entries))
    print(f"✅ {len(entries)} fast & working streams kept")

    grouped = defaultdict(dict)

    for title, extinf, url in entries:
        normalized = normalize_title(title)
        group = detect_group(title)
        extinf = rebuild_extinf(extinf, group)

        if normalized not in grouped[group]:
            grouped[group][normalized] = (normalized, extinf, url)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(header)

        for group in sorted(grouped.keys()):
            for _, extinf, url in sorted(grouped[group].values(), key=lambda x: x[0]):
                f.write(extinf + "\n")
                f.write(url + "\n")

if __name__ == "__main__":
    main()
