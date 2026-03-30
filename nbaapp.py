import requests
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# List of servers to process
SERVERS = [
    {"url": "http://app.tecnomolly.com:8080/get.php", "user": "82948sns", "pass": "a7hHZewDgAkb", "label": "Server 1"},
    {"url": "http://app.tecnomolly.com:8080/get.php", "user": "israellopez17", "pass": "GWZ7zADPwJUt", "label": "Server 2"},
    {"url": "http://app.tecnomolly.com:8080/get.php", "user": "836829173", "pass": "6e6tMMH2Cq", "label": "Server 3"}
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_and_process_server(server):
    """Function to process a single server. Returns a list of lines."""
    server_lines = []
    # Pattern to split metadata: [Prefix][Group-Title][Middle][Display Name]
    inf_pattern = re.compile(r'(#EXTINF.*group-title=")([^"]*)(".*,)(.*)')
    
    try:
        print(f"Starting fetch: {server['label']}")
        params = {
            "username": server["user"],
            "password": server["pass"],
            "type": "m3u_plus"
        }
        
        # Adding a smaller timeout per request to keep it snappy
        response = requests.get(server["url"], params=params, headers=headers, timeout=20)
        response.raise_for_status()

        lines = response.text.splitlines()
        
        for i in range(len(lines)):
            line = lines[i]
            
            if line.startswith("#EXTINF"):
                match = inf_pattern.search(line)
                if match:
                    prefix, original_group, middle, display_name = match.groups()
                    
                    if "nba" in original_group.lower():
                        if display_name.strip().lower() == "nba tv":
                            continue
                        
                        # Formatting: Group rename and Bracketed Server Label
                        new_inf_line = f'{prefix}Nba Live [HD]{middle}'
                        current_display_name = f"{display_name.strip()} [{server['label']}]"
                        
                        # Time Shift: Add 14 hours
                        time_match = re.search(r'(\d{1,2}):(\d{2})', current_display_name)
                        if time_match:
                            original_time_str = time_match.group(0)
                            try:
                                time_obj = datetime.strptime(original_time_str, "%H:%M")
                                new_time_str = (time_obj + timedelta(hours=14)).strftime("%H:%M")
                                current_display_name = current_display_name.replace(original_time_str, new_time_str)
                            except ValueError:
                                pass
                        
                        server_lines.append(new_inf_line + current_display_name)
                        
                        # URL Processing
                        if i + 1 < len(lines):
                            stream_url = lines[i+1].strip()
                            if not stream_url.lower().endswith("output=m3u8"):
                                separator = "&" if "?" in stream_url else "?"
                                stream_url += f"{separator}output=m3u8"
                            server_lines.append(stream_url)

        print(f"Finished: {server['label']}")
        return server_lines

    except Exception as e:
        print(f"Error on {server['label']}: {e}")
        return []

def main():
    final_list = ["#EXTM3U"]
    
    # Using ThreadPoolExecutor to run fetches in parallel
    with ThreadPoolExecutor(max_workers=len(SERVERS)) as executor:
        # map ensures the results come back in the order of the SERVERS list
        results = list(executor.map(fetch_and_process_server, SERVERS))
    
    # Flatten the list of lists into the final playlist
    for result in results:
        final_list.extend(result)

    with open("nbaapp.m3u8", "w", encoding="utf-8") as f:
        f.write("\n".join(final_list))
    
    print(f"\nParallel processing complete! 'nbaapp.m3u8' saved.")

if __name__ == "__main__":
    main()
