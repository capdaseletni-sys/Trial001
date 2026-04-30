import requests
import re
from concurrent.futures import ThreadPoolExecutor

# Source URL
M3U_URL = "https://raw.githubusercontent.com/abusaeeidx/IPTV-Scraper-Zilla/refs/heads/main/PlutoTV-All.m3u"
OUTPUT_FILE = "plutotv.m3u8"
MAX_WORKERS = 25  # Increased slightly for speed

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VLC/3.0.18",
    "Accept": "*/*"
}

def check_link(item):
    """Checks if a URL is active and returns the metadata + URL."""
    title, info, url = item
    try:
        # stream=True is essential to stop after the header check
        response = requests.get(url, headers=HEADERS, timeout=5, stream=True, verify=False)
        is_ok = response.status_code == 200
        response.close()
        if is_ok:
            return {"title": title, "info": info, "url": url}
    except:
        pass
    return None

def extract_title(info_line):
    """Extracts the display name of the channel from the #EXTINF line."""
    # Looks for the text after the last comma
    match = re.search(r',(.*)$', info_line)
    if match:
        return match.group(1).strip()
    return info_line

def process_m3u():
    requests.packages.urllib3.disable_warnings()
    
    print("Fetching source M3U...")
    try:
        response = requests.get(M3U_URL, headers=HEADERS)
        response.raise_for_status()
    except Exception as e:
        print(f"Error: {e}")
        return

    lines = response.text.splitlines()
    tasks = []
    current_info = None

    # Step 1: Parse and Prepare Tasks
    for line in lines:
        line = line.strip()
        if not line: continue
        
        if line.startswith("#EXTINF"):
            # Update group-title to Pluto TV
            if 'group-title="' in line:
                updated_line = re.sub(r'group-title="[^"]*"', 'group-title="Pluto TV"', line)
            else:
                updated_line = line.replace('#EXTINF:-1', '#EXTINF:-1 group-title="Pluto TV"')
            current_info = updated_line
            
        elif line.startswith("http") and current_info:
            title = extract_title(current_info)
            tasks.append((title, current_info, line))
            current_info = None

    print(f"Checking {len(tasks)} streams (Removing duplicates)...")
    
    final_channels = {} # Dictionary to store: { 'Channel Name': (info, url) }

    # Step 2: Multi-threaded verification
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # We use as_completed to process results as soon as they are ready (faster)
        from concurrent.futures import as_completed
        future_to_url = {executor.submit(check_link, t): t for t in tasks}
        
        for future in as_completed(future_to_url):
            result = future.result()
            if result:
                title = result['title']
                # Step 3: Deduplication logic
                # Only add if the title isn't already in our 'working' dictionary
                if title not in final_channels:
                    final_channels[title] = (result['info'], result['url'])
                    print(f"[UNIQUE] Added: {title}")

    # Step 4: Write Output
    new_m3u = ["#EXTM3U"]
    for title in sorted(final_channels.keys()):
        info, url = final_channels[title]
        new_m3u.append(info)
        new_m3u.append(url)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(new_m3u))
    
    print(f"\nSuccess! Cleaned playlist saved to {OUTPUT_FILE}")
    print(f"Total unique channels found: {len(final_channels)}")

if __name__ == "__main__":
    process_m3u()
