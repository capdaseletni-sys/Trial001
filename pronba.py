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
SAVE_PATH = "pronba.m3u8"
MAX_WORKERS = 10 

# This is what the script looks for in the portal
TARGET_CATEGORY = "US| NBA PASS PPV ⁸ᴷ"

# This is what will be written in the #EXTINF group-title
OUTPUT_GROUP_NAME = "NBA LEAGUE PASS"

# Offset to reach GMT+8 (from Europe/Berlin UTC+1)
HOURS_OFFSET = 7 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
    "X-User-Agent": "Model: MAG250; Link: Ethernet",
    "Referer": f"{BASE_DOMAIN}/c/",
    "Accept": "*/*",
    "Cookie": f"mac={MAC_ADDRESS}; stb_lang=en; timezone=Europe/Berlin",
}

def adjust_time_string(time_str):
    """
    Parses 'Fri 06 Mar 00:00', adds offset, returns updated string.
    """
    current_year = datetime.now().year
    try:
        dt = datetime.strptime(f"{time_str} {current_year}", "%a %d %b %H:%M %Y")
        dt_new = dt + timedelta(hours=HOURS_OFFSET)
        return dt_new.strftime("%a %d %b %H:%M")
    except Exception:
        return time_str

def clean_channel_name(name):
    """
    1. Splits 'Teams | Time | Junk'
    2. Adjusts Time
    3. Removes dashes (-)
    4. Swaps to 'Time | Teams'
    """
    parts = name.split('|')
    
    if len(parts) >= 2:
        teams_raw = parts[0].strip()
        time_raw = parts[1].strip()
        
        new_time = adjust_time_string(time_raw)
        
        # Remove dashes and fix double spaces
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
    except Exception: 
        return None

def fetch_category(session, cat):
    cat_id = cat.get('id')
    cat_name = cat.get('title', 'General').strip()
    
    # Still search for the original portal category name
    if cat_name != TARGET_CATEGORY:
        return []

    chunk_data = get_stalker_data(session, "get_ordered_list", {"genre": cat_id, "max": 500})
    channels = []
    
    if isinstance(chunk_data, dict):
        ch_list = chunk_data.get('data', [])
    elif isinstance(chunk_data, list):
        ch_list = chunk_data
    else:
        ch_list = []

    for ch in ch_list:
        raw_name = ch.get("name", "")
        if "- NO EVENT STREAMING -" in raw_name:
            continue
            
        final_name = clean_channel_name(raw_name)
        channels.append({
            "name": final_name,
            "id": ch.get("id"),
            "cat_name": OUTPUT_GROUP_NAME # Use the new group name here
        })
    return channels

def generate_playlist():
    session = requests.Session()
    session.headers.update(HEADERS)
    print(f"[*] Connecting to {BASE_DOMAIN}...")

    handshake = get_stalker_data(session, "handshake")
    if isinstance(handshake, dict) and handshake.get("token"):
        session.headers.update({"Authorization": f"Bearer {handshake.get('token')}"})

    get_stalker_data(session, "get_profile")
    categories = get_stalker_data(session, "get_genres")
    
    if not categories:
        print("❌ Failed to get categories.")
        return

    all_channels = []
    print(f"[*] Searching for: {TARGET_CATEGORY}...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fetch_category, session, cat) for cat in categories]
        for future in as_completed(futures):
            all_channels.extend(future.result())

    if not all_channels:
        print(f"⚠️ No channels found.")
        return

    # Sort chronologically by the name (which starts with time)
    all_channels.sort(key=lambda x: x['name'])

    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in all_channels:
            stream_url = f"{BASE_DOMAIN}/play/live.php?mac={MAC_ADDRESS}&stream={ch['id']}&extension=m3u8"
            # Updated to use the static 'NBA LEAGUE PASS' group title
            f.write(f'#EXTINF:-1 group-title="{ch["cat_name"]}",{ch["name"]}\n{stream_url}\n')

    print(f"\n✅ SUCCESS! {len(all_channels)} NBA Channels Saved.")
    print(f"📂 Saved to: {SAVE_PATH}")
    print(f"🏷️ Group Title: {OUTPUT_GROUP_NAME}")

if __name__ == "__main__":
    generate_playlist()
