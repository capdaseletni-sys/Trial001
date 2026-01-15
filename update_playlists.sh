#!/bin/bash

# Define the output files and their corresponding URLs
urls=(
    "http://supersonictv.live:8080/get.php?username=611366&password=682256&&type=m3u_plus"
    "http://cord-cutter.net:8080/get.php?username=15564292&password=15564292&type=m3u_plus"
    "http://www.sansat.plus:88/get.php?username=02060789178359&password=02:00:00:00:00:00&type=m3u"
    "http://protv65.shop:8080/get.php?username=hsn3868&password=hsn00xy&type=m3u_plus"
    "http://portal-iptv.net:8080/get.php?username=077998950140&password=077998950140&&type=m3u_plus"
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
