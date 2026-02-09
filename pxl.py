import requests

def process_m3u():
    url = "https://raw.githubusercontent.com/doms9/iptv/refs/heads/default/M3U8/events.m3u8"
    old_domain = "https://hd.bestlive.top:443"
    new_domain = "https://hd.pixelhd.online:443"
    
    try:
        print(f"Fetching playlist from: {url}")
        response = requests.get(url)
        response.raise_for_status()
        lines = response.text.splitlines()

        output = ["#EXTM3U"]
        
        for i in range(len(lines)):
            # Check if line contains PIXEL (case insensitive)
            if lines[i].startswith("#EXTINF") and "PIXEL" in lines[i].upper():
                # 1. Add the #EXTINF line
                output.append(lines[i])
                
                # 2. Look ahead for the URL, keeping any #EXTVLCOPT lines in between
                cursor = i + 1
                while cursor < len(lines):
                    current_line = lines[cursor].strip()
                    
                    if not current_line:
                        cursor += 1
                        continue
                        
                    if current_line.startswith("#EXTVLCOPT"):
                        output.append(current_line)
                    elif current_line.startswith("http"):
                        # This is the URL - modify and add it
                        modified_url = current_line.replace(old_domain, new_domain)
                        output.append(modified_url)
                        break
                    else:
                        # Reached another tag or end of block
                        break
                    cursor += 1

        # Save the result
        with open("pixelsports.m3u8", "w", encoding="utf-8") as f:
            f.write("\n".join(output))
            
        # Count based on EXTINF lines added (minus header)
        count = sum(1 for line in output if line.startswith("#EXTINF"))
        print(f"Success! Extracted {count} channels.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    process_m3u()
