import requests
import re

def process_m3u_playlist(url):
    target_tvg_name = 'tvg-name="PIXEL"'
    old_domain = "https://hd.bestlive.top:443"
    new_domain = "https://hd.pixelhd.online:443"
    
    try:
        # 1. Download the playlist
        print(f"Fetching playlist from: {url}")
        response = requests.get(url)
        response.raise_for_status()
        lines = response.text.splitlines()

        extracted_lines = ["#EXTM3U"] # Start with the standard M3U header
        
        # 2. Iterate through lines to find matches
        # M3U files usually have pairs: #EXTINF line followed by the URL line
        for i in range(len(lines)):
            if lines[i].startswith("#EXTINF") and target_tvg_name in lines[i]:
                # We found a matching info line
                inf_line = lines[i]
                
                # The URL is typically on the next line
                if i + 1 < len(lines):
                    url_line = lines[i+1]
                    
                    # 3. Convert the URL domain
                    modified_url = url_line.replace(old_domain, new_domain)
                    
                    # Add both the info line and the modified URL to our list
                    extracted_lines.append(inf_line)
                    extracted_lines.append(modified_url)

        # 4. Output the results
        output_content = "\n".join(extracted_lines)
        
        # Save to a local file
        with open("pixelsport.m3u8", "w", encoding="utf-8") as f:
            f.write(output_content)
            
        print(f"Success! Extracted {int((len(extracted_lines)-1)/2)} channels.")
        print("File saved as: pixel_playlist.m3u")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    m3u_url = "https://raw.githubusercontent.com/doms9/iptv/refs/heads/default/M3U8/events.m3u8"
    process_m3u_playlist(m3u_url)
