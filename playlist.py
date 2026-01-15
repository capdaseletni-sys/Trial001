import requests

url = "http://cchelp.xyz:826/get.php"
params = {
    "username": "Chine611",
    "password": "DEht5fmfT2",
    "type": "m3u_plus"
}

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(url, params=params, headers=headers, timeout=10)

if response.status_code == 200:
    with open("playlist.m3u8", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("Playlist saved as playlist.m3u8")
else:
    print("Failed:", response.status_code)
