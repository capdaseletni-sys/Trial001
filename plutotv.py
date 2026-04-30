import requests
import re

# Source URL
M3U_URL = "https://raw.githubusercontent.com/abusaeeidx/IPTV-Scraper-Zilla/refs/heads/main/PlutoTV-All.m3u"
OUTPUT_FILE = "plutotv.m3u8"

# Standard Player User-Agent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VLC/3.0.18",
    "Accept": "*/*"
}

def check_link(url):
    """Checks if a URL is active using a GET request (more reliable for IPTV)."""
    try:
        # stream=True allows us to check the status without downloading the whole video file
        response = requests.get(url, headers=HEADERS, timeout=10, stream=True, verify=False)
        is_ok = response.status_code == 200
        response.close() # Close connection immediately
        return is_ok
    except Exception as e:
        return False

def process_m3u():
    # Disable SSL warnings for the "verify=False" part
    requests.packages.urllib3.disable_warnings()
    
    print(f"Fetching source...")
    try:
        response = requests.get(M3U_URL, headers=HEADERS)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching source: {e}")
        return

    lines = response.text.splitlines()
    new_m3u = ["#EXTM3U"]
    current_info = None

    print("Verifying streams... (Using GET mode)")
    
    for line in lines:
        line = line.strip()
        if not line: continue
            
        if line.startswith("#EXTINF"):
            # Force Group Title to Pluto TV
            if 'group-title="' in line:
                updated_line = re.sub(r'group-title="[^"]*"', 'group-title="Pluto TV"', line)
            else:
                updated_line = line.replace('#EXTINF:-1', '#EXTINF:-1 group-title="Pluto TV"')
            current_info = updated_line
            
        elif line.startswith("http"):
            url = line
            if check_link(url):
                print(f"[WORKING] {url[:50]}...")
                if current_info:
                    new_m3u.append(current_info)
                new_m3u.append(url)
            else:
                print(f"[FAILED]  {url[:50]}...")
            
            current_info = None

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(new_m3u))
    
    print(f"\nDone! Check {OUTPUT_FILE}")

if __name__ == "__main__":
    process_m3u()
