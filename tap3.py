import asyncio
from playwright.async_api import async_playwright

async def get_tv_tokens():
    # Define the channels you want: { "Display Name": "Token Slug" }
    channels = {
        "Fanduel Sports Indiana": "fanduel-sports-indiana",
        "Fanduel Sports Network Detriot": "fanduel-sports-network-detroit-hd",
        "Fanduel Sports Network Florida": "fanduel-sports-network-florida",
        "Fanduel Sports Network Great Lakes": "fanduel-sports-network-great-lakes",
        "Fanduel Sports Network North": "fanduel-sports-network-north",
        "Fanduel Sports Network Ohio Cleveland": "fanduel-sports-network-ohio-cleveland",
        "Fanduel Sports Network Oklahoma": "fanduel-sports-network-oklahoma",
        "Fanduel Sports Network San Diego": "fanduel-sports-network-san-diego",
        "Fanduel Sports Network Socal": "fanduel-sports-network-socal",
        "Fanduel Sports Network South Carolinas": "fanduel-sports-network-south-carolinas",
        "Fanduel Sports Network South Tennessee": "fanduel-sports-network-south-tennessee-usa",
        "Fanduel Sports Network West": "fanduel-sports-network-west",
        "Fanduel Sports Network Wisconsin": "fanduel-sports-network-wisconsin",
        "Fanduel Sports Southeast Georgia": "fanduel-sports-southeast-georgia",
        "Fanduel Sports Southeast North Carolina": "fanduel-sports-southeast-north-carolina",
        "Fanduel Sports Southeast South Carolina": "fanduel-sports-southeast-south-carolina",
        "Fanduel Sports Southeast Tennessee Nashville": "fanduel-sports-southeast-tennessee-nashville",
        "Fanduel Sports Sun": "fanduel-sports-sun",
        "Fanduel Sports Tennessee East": "fanduel-sports-tennessee-east"
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
        with open("tap3.m3u8", "w") as f:
            f.write("\n".join(m3u_lines))
            
        print("\n--- DONE! ---")
        print("'tap3.m3u8' updated with all available channels.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tv_tokens())
