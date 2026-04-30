import requests
import re
from concurrent.futures import ThreadPoolExecutor

# Source URL
M3U_URL = "https://raw.githubusercontent.com/abusaeeidx/IPTV-Scraper-Zilla/refs/heads/main/PlutoTV-All.m3u"
OUTPUT_FILE = "plutotv.m3u8"
MAX_WORKERS = 20  # Number of simultaneous checks

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VLC/3.0.18",
    "Accept": "*/*"
}

def check_link(item):
    """
    Worker function to check a single stream.
    'item' is a tuple of (info_line, url_line)
    """
    info, url = item
    try:
        # We use a shorter timeout for speed; 5s is usually enough for a handshake
        response = requests.get(url, headers=HEADERS, timeout=5, stream=True, verify=False)
        is_ok = response.status_code == 200
        response.close()
        if is_ok:
            return (info, url)
    except:
        pass
    return None

def process_m3u():
    requests.packages.urllib3.disable_warnings()
    
    print(f"Fetching source...")
    try:
        response = requests.get(M3U_URL, headers=HEADERS)
        response.raise_for_status()
    except Exception as e:
        print(f"Error: {e}")
        return

    lines = response.text.splitlines()
    tasks = []
    current_info = None

    # Prepare pairs of (Info, URL) to check
    for line in lines:
        line = line.strip()
        if not line: continue
        
        if line.startswith("#EXTINF"):
            if 'group-title="' in line:
                updated_line = re.sub(r'group-title="[^"]*"', 'group-title="Pluto TV"', line)
            else:
                updated_line = line.replace('#EXTINF:-1', '#EXTINF:-1 group-title="Pluto TV"')
            current_info = updated_line
            
        elif line.startswith("http") and current_info:
            tasks.append((current_info, line))
            current_info = None

    print(f"Verifying {len(tasks)} streams using {MAX_WORKERS} workers...")
    
    working_streams = []
    # ThreadPoolExecutor runs checks in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(check_link, tasks))
    
    # Filter out the 'None' results (failed links)
    working_streams = [r for r in results if r is not None]

    # Rebuild the M3U file
    new_m3u = ["#EXTM3U"]
    for info, url in working_streams:
        new_m3u.append(info)
        new_m3u.append(url)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(new_m3u))
    
    print(f"\nDone! Saved {len(working_streams)} working streams to {OUTPUT_FILE}")

if __name__ == "__main__":
    process_m3u()
