#!/bin/bash

# Define the output files and their corresponding URLs
urls=(
    "http://localiptv.site:85/get.php?username=lacigalfov&password=lacigalfov&type=m3u_plus"
)

# Array to keep track of downloaded filenames
files=()

echo "Starting downloads..."

for i in "${!urls[@]}"; do
    filename="playlist${i}.m3u8"
    # Use -s for silent mode but show errors with -S
    curl -sSL -A "Mozilla/5.0" -o "$filename" "${urls[$i]}"
    
    if [ $? -eq 0 ]; then
        echo "Successfully downloaded $filename"
        files+=("$filename")
    else
        echo "Failed to download ${urls[$i]}"
    fi
done

# Run your python script using the list of files successfully downloaded
echo "Merging playlists..."
python3 supersonic.py supersonic.m3u8 "${files[@]}"

echo "Done!"
