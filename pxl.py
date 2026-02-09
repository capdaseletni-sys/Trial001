import requests
import re

TEAM_MAP = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS"
}

def clean_title(line):
    # 1. Force group-title to "pixelsports"
    line = re.sub(r'group-title="[^"]*"', 'group-title="pixelsports"', line)
    
    # 2. Split the line to isolate the display name (everything after the last comma)
    if "," in line:
        params, title = line.rsplit(",", 1)
        
        # Remove [NBA] and (PIXEL) - case insensitive
        title = re.sub(r'\[NBA\]', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\(PIXEL\)', '', title, flags=re.IGNORECASE)
        
        # Replace full team names with abbreviations from TEAM_MAP
        for full_name, short_name in TEAM_MAP.items():
            if full_name in title:
                title = title.replace(full_name, short_name)
        
        # Clean up extra whitespace left behind
        title = ' '.join(title.split())
        line = f"{params},{title}"
        
    return line

def process_m3u():
    url = "https://raw.githubusercontent.com/doms9/iptv/refs/heads/default/M3U8/events.m3u8"
    old_domain = "https://hd.bestlive.top:443"
    new_domain = "https://hd.pixelhd.online:443"
    
    try:
        print(f"Fetching and processing NBA/PIXEL events...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        lines = response.text.splitlines()

        output = ["#EXTM3U"]
        
        for i in range(len(lines)):
            # Filter for PIXEL entries
            if lines[i].startswith("#EXTINF") and "PIXEL" in lines[i].upper():
                # Process the title and group
                modified_extinf = clean_title(lines[i])
                output.append(modified_extinf)
                
                cursor = i + 1
                while cursor < len(lines):
                    current_line = lines[cursor].strip()
                    if not current_line:
                        cursor += 1
                        continue
                    
                    if current_line.startswith("#EXTVLCOPT"):
                        output.append(current_line)
                    elif current_line.startswith("http"):
                        output.append(current_line.replace(old_domain, new_domain))
                        break
                    elif current_line.startswith("#EXTINF"):
                        break
                    cursor += 1

        with open("pixelsports.m3u8", "w", encoding="utf-8") as f:
            f.write("\n".join(output))
            
        count = sum(1 for line in output if line.startswith("#EXTINF"))
        print(f"Success! {count} channels processed and shortened.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    process_m3u()
