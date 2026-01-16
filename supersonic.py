import re
from collections import defaultdict

INPUT_FILE = "supersonic.m3u8"
OUTPUT_FILE = "supersonic.m3u8"

# 1️⃣ Primary grouping by channel name
NAME_GROUPS = {
    "Documentary": ["discovery", "nat geo", "history", "animal"],
    "Entertainment": ["entertainment", "series", "show"],
    "Kids": ["kids", "cartoon", "nick", "disney"],
    "Movies": ["movie", "cinema", "film", "hbo", "starz"],
    "Music": ["music", "mtv", "vh1"],
    "News": ["cnn", "bbc", "fox news", "al jazeera", "sky news", "cnbc"],
    "Religious": ["islam", "quran", "christian", "church"],
    "Sports": ["sport", "espn", "beins", "sky sports", "fox sports"],
}

# 2️⃣ Fallback keyword detection
KEYWORD_GROUPS = {
    "News": ["news", "report", "live"],
    "Sports": ["match", "league", "cup", "football", "soccer"],
    "Movies": ["movie", "film", "cinema"],
    "Kids": ["kids", "cartoon", "baby"],
    "Music": ["music", "radio", "hits"],
}

# ❌ Excluded stream extensions
EXCLUDED_EXTENSIONS = (".mkv", ".mp4")

# ❌ Ignored quality prefixes
IGNORED_PREFIXES = ("hd", "fhd", "uhd", "4k", "8k")

def normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"^[\[\(\{]?(hd|fhd|uhd|4k|8k)[\]\)\}]?\s*-?\s*", "", t)
    t = re.sub(r"\s+", " ", t)
    return t

def detect_group(title: str) -> str:
    t = title.lower()

    for group, words in NAME_GROUPS.items():
        if any(w in t for w in words):
            return group

    for group, words in KEYWORD_GROUPS.items():
        if any(w in t for w in words):
            return group

    return "Mix"

def rebuild_extinf(extinf, group):
    if 'group-title="' in extinf:
        return re.sub(r'group-title="[^"]*"', f'group-title="{group}"', extinf)
    return extinf.replace("#EXTINF:-1", f'#EXTINF:-1 group-title="{group}"')

def parse_playlist(lines):
    entries = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            extinf = lines[i].strip()
            url = lines[i + 1].strip()

            # ❌ Skip excluded formats
            if url.lower().endswith(EXCLUDED_EXTENSIONS):
                i += 2
                continue

            title = extinf.split(",")[-1].strip()
            entries.append((title, extinf, url))
            i += 2
        else:
            i += 1
    return entries

def main():
    with open(INPUT_FILE, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    header = [l for l in lines if l.startswith("#EXTM3U")]
    entries = parse_playlist(lines)

    grouped = defaultdict(dict)  # group -> {normalized_title: (sort_key, extinf, url)}

    for title, extinf, url in entries:
        normalized = normalize_title(title)
        group = detect_group(title)
        extinf = rebuild_extinf(extinf, group)

        # 🧹 Deduplicate by normalized title
        if normalized not in grouped[group]:
            grouped[group][normalized] = (normalized, extinf, url)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(header)

        # 🔤 Sort groups A–Z
        for group in sorted(grouped.keys()):
            # 🔤 Sort channels A–Z (ignoring prefixes)
            for _, extinf, url in sorted(grouped[group].values(), key=lambda x: x[0]):
                f.write(extinf + "\n")
                f.write(url + "\n")

if __name__ == "__main__":
    main()
