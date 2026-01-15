import webbrowser
import time

# List your manifest URLs here
manifests = [
    "https://addon-1.com/manifest.json",
    "https://addon-2.com/manifest.json",
    # Add as many as you want
]

def install():
    for url in manifests:
        # Convert to stremio protocol
        stremio_link = url.replace("https://", "stremio://").replace("http://", "stremio://")
        
        print(f"Triggering installation for: {stremio_link}")
        
        # Opens the default browser which triggers the Stremio App
        webbrowser.open(stremio_link)
        
        # Short pause to prevent the OS from getting overwhelmed
        time.sleep(1.5)

if __name__ == "__main__":
    install()
