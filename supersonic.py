import asyncio
import aiohttp
import sys
import time
from pathlib import Path

# ---------- ULTIMATE SPEED CONFIG ----------
# Increase these if you are on a high-end VPS (1Gbps+ connection)
MAX_CONCURRENCY = 250  
TIMEOUT = aiohttp.ClientTimeout(total=5) # If it doesn't respond in 5s, it's dead
SAMPLE_BYTES = 32_000                    # Tiny sample for 400k scan
WARMUP_BYTES = 512                       
MAX_TTFB = 3.0                           # Very strict response time

# ---------- OPTIMIZED WORKER ----------
async def fast_check(session, url, semaphore):
    async with semaphore:
        try:
            # Phase 1: Quick HEAD check (The "Filter")
            async with session.head(url, timeout=3, allow_redirects=True) as h:
                if h.status >= 400: return None

            # Phase 2: Tiny Stream Sample (The "Speed Test")
            start = time.perf_counter()
            async with session.get(url, timeout=TIMEOUT) as r:
                if r.status >= 400: return None
                
                measured = 0
                async for chunk in r.content.iter_chunked(4096):
                    if not measured: ttfb = time.perf_counter() - start
                    measured += len(chunk)
                    if measured >= SAMPLE_BYTES: break
                
                # Verify it didn't take too long
                duration = time.perf_counter() - start
                if ttfb <= MAX_TTFB:
                    return url
        except:
            return None

async def main(input_file, output_file):
    # Use a set to instantly remove duplicate URLs from your 400k list
    urls = set()
    with open(input_file, 'r', errors='ignore') as f:
        for line in f:
            if line.startswith('http'):
                urls.add(line.strip())

    print(f"Unique URLs to check: {len(urls)}")
    
    # High-performance connector settings
    connector = aiohttp.TCPConnector(
        limit=MAX_CONCURRENCY,
        ttl_dns_cache=600,  # Cache DNS for 10 minutes
        use_dns_cache=True,
        force_close=False   # Reuse connections!
    )
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    results = []

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fast_check(session, url, semaphore) for url in urls]
        
        # Process in chunks to avoid overwhelming system memory
        print("Starting massive scan...")
        for i in range(0, len(tasks), 1000):
            batch = tasks[i:i+1000]
            batch_results = await asyncio.gather(*batch)
            results.extend([r for r in batch_results if r])
            print(f"Checked: {i+1000}/{len(urls)} | Found: {len(results)}", end='\r')

    with open(output_file, 'w') as f:
        f.write("#EXTM3U\n" + "\n".join(results))
    
    print(f"\nScan complete. Saved {len(results)} links.")

if __name__ == "__main__":
    asyncio.run(main(sys.argv[2], sys.argv[1]))
