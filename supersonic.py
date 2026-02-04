import asyncio
import aiohttp
import time
import re
from collections import defaultdict

# --- CONFIGURATION ---
# Mimicking VLC is the "secret sauce" to stop getting empty results
USER_AGENT = "VLC/3.0.18 LibVLC/3.0.18"
SOURCE_URL = "http://s.rocketdns.info:8080/get.php?username=XtremeTV&password=5ALMBnQVzb&type=m3u_plus"
OUTPUT_FILE = "supersonic.m3u8"
MAX_CONCURRENCY = 30  # Keep this low so the server doesn't ban your IP
TIMEOUT_SECONDS = 5   # If a stream takes >5s to start, it's not "fast"

async def check_stream(session, sem, entry):
    """Verifies if the stream is fast and working."""
    async with sem:
        url = entry['url']
        start_time = time.time()
        try:
            # We request only a tiny slice of data to check speed/validity
            headers = {"User-Agent": USER_AGENT, "Range": "bytes=0-102400"}
            async with session.get(url, headers=headers, timeout=TIMEOUT_SECONDS) as r:
                if r.status == 200 or r.status == 206:
                    content = await r.read()
                    if len(content) > 1000: # Ensure we didn't get an error page
                        latency = time.time() - start_time
                        return (latency, entry)
        except:
            pass
        return (None, None)

def parse_m3u_content(content):
    """Extracts ALL entries without any filtering."""
    entries = []
    lines = content.splitlines()
    for i in range(len(lines)):
        if lines[i].startswith("#EXTINF"):
            extinf = lines[i].strip()
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                # Clean title extraction
                title = extinf.split(",")[-1].strip()
                if url.startswith("http"):
                    entries.append({"title": title, "extinf_raw": extinf, "url": url})
    return entries

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    # Increase the timeout for the initial massive file download
    timeout = aiohttp.ClientTimeout(total=300) 
    
    async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": USER_AGENT}, timeout=timeout) as session:
        print(f"📡 Downloading Source (this may take a minute)...")
        try:
            async with session.get(SOURCE_URL) as res:
                if res.status != 200:
                    print(f"❌ Failed! Server returned: {res.status}")
                    return
                text = await res.text()
                print(f"✅ Downloaded {len(text) / 1024 / 1024:.2f} MB of playlist data.")
        except Exception as e:
            print(f"❌ Download Error: {e}")
            return

        raw_entries = parse_m3u_content(text)
        print(f"🔍 Found {len(raw_entries)} total streams. Starting speed test...")

        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = [check_stream(session, sem, entry) for entry in raw_entries]
        results = await asyncio.gather(*tasks)

        # Filter only working ones and sort by FASTEST (lowest latency)
        working = [r for r in results if r[0] is not None]
        working.sort(key=lambda x: x[0])

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for latency, item in working:
                f.write(f"{item['extinf_raw']}\n{item['url']}\n")

        print(f"🏁 Done! Saved {len(working)} working/fast streams to {OUTPUT_FILE}.")

if __name__ == "__main__":
    asyncio.run(main())
