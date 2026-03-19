import requests
import re

url = "https://airtel4k.rkdyiptv.workers.dev/rkdyiptv.m3u"
headers = {
    "User-Agent": "Mozilla/5.0 (m3u-ip.tv 3.0.10) Android",
    "Accept": "*/*",
    "Host": "airtel4k.rkdyiptv.workers.dev"
}

# List of keywords we want to keep
TARGET_CHANNELS = ["STAR MOVIES", "STAR MOVIES SELECT"]
NEW_GROUP_NAME = "Cable TV [Mix]"

def save_filtered_m3u8():
    try:
        print("Fetching and filtering playlist...")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        content = response.text

        # Regex to capture attributes, channel name, and the URL
        pattern = re.compile(r'#EXTINF:-1(.*),(.*)\n(http.*)', re.MULTILINE)
        matches = pattern.findall(content)

        count = 0
        with open("rk.m3u8", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            
            for attributes, name, link in matches:
                clean_name = name.strip()
                
                # Check if the channel name matches our targets
                if any(target.upper() in clean_name.upper() for target in TARGET_CHANNELS):
                    # Replace the existing group-title with the new one
                    # This uses regex to swap whatever is inside group-title="..."
                    new_attr = re.sub(r'group-title="[^"]*"', f'group-title="{NEW_GROUP_NAME}"', attributes)
                    
                    f.write(f"#EXTINF:-1{new_attr},{clean_name}\n")
                    f.write(f"{link.strip()}\n")
                    count += 1

        if count > 0:
            print(f"Success! Saved {count} matching channels to 'filtered_star_movies.m3u8'.")
        else:
            print("No matching channels found. Check the channel names in the source.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    save_filtered_m3u8()
