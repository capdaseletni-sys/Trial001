import asyncio
from playwright.async_api import async_playwright

async def get_tv_tokens():
    # Define the channels you want: { "Display Name": "Token Slug" }
    channels = {
        "ESPN [SD]": "ESPN",
        "ESPN 2 [SD]": "ESPN2",
        "CBS Sports Network": "CBSSportsNetworkUSA",
        "CBS KCBS Los Angeles CA": "cbs-kcbs-los-angeles-ca",
        "CBS WCBS New York": "WCBSDT1",
        "NFL Network": "NFLNetwork",
        "NFL Redzone": "NFLRedZone",
        "NHL Network": "NHLNetwork",
        "Big Ten Network": "BTN",
        "ACC Network": "ACCNetwork",
        "NBA TV [SD]": "NBATV",
        "Chicago Sports Network": "chicago-sports-network",
        "Fox Sports 1": "FoxSports1",
        "Fox Sports 2": "FoxSports2",
        "NBC Los Angeles": "nbc-knbc-los-angeles-ca",
        "NBC New York": "WNBCDT1",
        "NBC Sports Bay Area": "nbc-sports-bay-area",
        "NBC Sports Boston": "nbc-sports-boston",
        "NBC Sports California": "nbc-sports-california",
        "NBC Sports Philadelphia": "nbc-sports-philadelphia",
        "MLB Network": "MLBNetwork"  
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        m3u_lines = ["#EXTM3U"]

        for display_name, slug in channels.items():
            try:
                print(f"Fetching token for {display_name}...")
                
                # Navigate to the specific channel page to refresh session
                await page.goto(f"https://thetvapp.to/tv/{slug.lower()}-live-stream/", wait_until="networkidle")

                # Fetch the token via the browser context
                response = await page.evaluate(f"""
                    fetch("https://thetvapp.to/token/{slug}", {{
                        headers: {{ "Accept": "application/json" }}
                    }}).then(res => res.json())
                """)

                if "url" in response:
                    final_url = response["url"]
                    m3u_lines.append(f'#EXTINF:-1 group-title="Cable TV [Sports]",{display_name}')
                    m3u_lines.append(final_url)
                    print(f"Successfully added {display_name}")
                else:
                    print(f"Failed to get URL for {display_name}")

            except Exception as e:
                print(f"Error fetching {display_name}: {e}")

        # Save all results to the file
        with open("tap.m3u8", "w") as f:
            f.write("\n".join(m3u_lines))
            
        print("\n--- DONE! ---")
        print("'tap.m3u8' updated with all available channels.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tv_tokens())
