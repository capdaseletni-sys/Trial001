import os
import json
import time
import re
from datetime import datetime, timedelta
from curl_cffi import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION ---
BASE_DOMAIN = "http://pro.reott8k.xyz:80"
PORTAL_URL = f"{BASE_DOMAIN}/portal.php"
MAC_ADDRESS = "00:1A:79:7B:BB:36" 
SAVE_FOLDER = "nba_playlists"
MASTER_FILENAME = "pronba.m3u8"

# UPDATE THIS: Replace with your GitHub details
# Format: https://raw.githubusercontent.com/USERNAME/REPO_NAME/BRANCH_NAME/FOLDER_NAME/
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/capdaseletni-sys/Trial001/main/nba_playlists/"

MAX_WORKERS = 10 
TARGET_CATEGORY = "US| NBA PASS PPV ⁸ᴷ"
OUTPUT_GROUP_NAME = "NBA LEAGUE PASS"
HOURS_OFFSET = 8 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
    "X-User-Agent": "Model: MAG250; Link: Ethernet",
    "Referer": f"{BASE_DOMAIN}/c/",
    "Accept": "*/*",
    "Cookie": f"mac={MAC_ADDRESS}; stb_lang=en; timezone=Europe/Berlin",
}

def adjust_time_string(time_str):
    current_year = datetime.now().year
    try:
        dt = datetime.strptime(f"{time_str} {current_year}", "%a %d %b %H:%M %Y")
        dt_new = dt + timedelta(hours=HOURS_OFFSET)
        return dt_new.strftime("%a %d %b %H:%M")
    except Exception:
        return time_str

def clean_channel_name(name):
    parts = name.split('|')
    if len(parts) >= 2:
        teams_raw = parts[0].strip()
        time_raw = parts[1].strip()
        new_time = adjust_time_string(time_raw)
        teams_clean = teams_raw.replace("-", "").replace("  ", " ").strip()
        return f"{new_time} | {teams_clean}"
    return name.strip()

def get_stalker_data(session, action, extra_params=None):
    params = {"type": "itv", "action": action, "JsHttpRequest": "1-xml"}
    if extra_params: params.update(extra_params)
    try:
        res = session.get(PORTAL_URL, params=params, headers=session.headers, impersonate="chrome110", timeout=120)
        data = res.json()
        return data.get("js") if isinstance(data, dict) else data
    except Exception: return None

def fetch_category(session, cat):
    cat_id = cat.get('id')
    cat_name = cat.get('title', 'General').strip()
    if cat_name != TARGET_CATEGORY: return []
    chunk_data = get_stalker_data(session, "get_ordered_list", {"genre": cat_id, "max": 500})
    channels = []
    ch_list = chunk_data.get('data', []) if isinstance(chunk_data, dict) else []
    for ch in ch_list:
        raw_name = ch.get("name", "")
        if "- NO EVENT STREAMING -" in raw_name or "##### NBA PASS PPV ⁸ᴷ #####" in raw_name: continue
        final_name = clean_channel_name(raw_name)
        channels.append({"name": final_name, "id": ch.get("id")})
    return channels

def generate_playlist():
    if not os.path.exists(SAVE_FOLDER):
        os.makedirs(SAVE_FOLDER)
    else:
        for file in os.listdir(SAVE_FOLDER):
            os.remove(os.path.join(SAVE_FOLDER, file))

    session = requests.Session(); session.headers.update(HEADERS)
    print(f"[*] Connecting to {BASE_DOMAIN}...")
    handshake = get_stalker_data(session, "handshake")
    if isinstance(handshake, dict) and handshake.get("token"):
        session.headers.update({"Authorization": f"Bearer {handshake.get('token')}"})
    get_stalker_data(session, "get_profile")
    categories = get_stalker_data(session, "get_genres")
    
    if not categories: return print("❌ Failed to get categories.")

    all_channels = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fetch_category, session, cat) for cat in categories]
        for future in as_completed(futures):
            all_channels.extend(future.result())

    if not all_channels: return print("⚠️ No channels found.")
    all_channels.sort(key=lambda x: x['name'])

    # Write individual files AND build the Master Playlist content
    master_lines = ["#EXTM3U\n"]
    
    for ch in all_channels:
        stream_url = f"{BASE_DOMAIN}/play/live.php?mac={MAC_ADDRESS}&stream={ch['id']}&extension=m3u8"
        
        # 1. Create individual filename (URL encoded for GitHub links)
        safe_filename = re.sub(r'[\\/*?:"<>|]', "", ch['name']) + ".m3u"
        github_safe_name = safe_filename.replace(" ", "%20")
        
        # 2. Save individual M3U
        file_path = os.path.join(SAVE_FOLDER, safe_filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=2500000\n{stream_url}\n")

        # 3. Add entry to Master Playlist pointing to GitHub
        github_url = f"{GITHUB_RAW_BASE}{github_safe_name}"
        master_lines.append(f'#EXTINF:-1 group-title="{OUTPUT_GROUP_NAME}",{ch["name"]}\n{github_url}\n')

    # 4. Save Master M3U8
    with open(MASTER_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(master_lines)

    print(f"\n✅ SUCCESS!")
    print(f"📂 Individual files in: '{SAVE_FOLDER}'")
    print(f"🔗 Master file created: '{MASTER_FILENAME}' pointing to GitHub Raw.")

if __name__ == "__main__":
    generate_playlist()
