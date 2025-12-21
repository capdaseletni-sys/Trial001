import base64
import re

from selectolax.parser import HTMLParser

from .utils import Cache, Time, get_logger, leagues, network

log = get_logger(__name__)

urls: dict[str, dict[str, str | float]] = {}

TAG = "ISTRMEST"

CACHE_FILE = Cache(f"{TAG.lower()}.json", exp=3_600)

BASE_URL = "https://istreameast.app"


async def process_event(url: str, url_num: int) -> str | None:
    pattern = re.compile(r"source:\s*window\.atob\(\s*'([^']+)'\s*\)", re.IGNORECASE)

    if not (event_data := await network.request(url, log=log)):
        log.info(f"URL {url_num}) Failed to load url.")

        return

    soup = HTMLParser(event_data.content)

    if not (iframe := soup.css_first("iframe#wp_player")):
        log.warning(f"URL {url_num}) No iframe element found.")

        return

    if not (iframe_src := iframe.attributes.get("src")):
        log.warning(f"URL {url_num}) No iframe source found.")

        return

    if not (iframe_src_data := await network.request(iframe_src, log=log)):
        log.info(f"URL {url_num}) Failed to load iframe source.")

        return

    if not (match := pattern.search(iframe_src_data.text)):
        log.warning(f"URL {url_num}) No Clappr source found.")

        return

    log.info(f"URL {url_num}) Captured M3U8")

    return base64.b64decode(match[1]).decode("utf-8")


async def get_events(cached_keys: list[str]) -> list[dict[str, str]]:
    events = []

    if not (html_data := await network.request(BASE_URL, log=log)):
        return events

    pattern = re.compile(r"^(?:LIVE|(?:[1-9]|[12]\d|30)\s+minutes?\b)", re.IGNORECASE)

    soup = HTMLParser(html_data.content)

    for link in soup.css("li.f1-podium--item > a.f1-podium--link"):
        li_item = link.parent

        if not (rank_elem := li_item.css_first(".f1-podium--rank")):
            continue

        if not (time_elem := li_item.css_first(".SaatZamanBilgisi")):
            continue

        time_text = time_elem.text(strip=True)

        if not pattern.search(time_text):
            continue

        sport = rank_elem.text(strip=True)

        if not (driver_elem := li_item.css_first(".f1-podium--driver")):
            continue

        event_name = driver_elem.text(strip=True)

        if inner_span := driver_elem.css_first("span.d-md-inline"):
            event_name = inner_span.text(strip=True)

        if f"[{sport}] {event_name} ({TAG})" in cached_keys:
            continue

        if not (href := link.attributes.get("href")):
            continue

        events.append(
            {
                "sport": sport,
                "event": event_name,
                "link": href,
            }
        )

    return events


async def scrape() -> None:
    cached_urls = CACHE_FILE.load()

    cached_count = len(cached_urls)

    urls.update(cached_urls)

    log.info(f"Loaded {cached_count} event(s) from cache")

    log.info(f'Scraping from "{BASE_URL}"')

    events = await get_events(cached_urls.keys())

    log.info(f"Processing {len(events)} new URL(s)")

    if events:
        now = Time.clean(Time.now()).timestamp()

        for i, ev in enumerate(events, start=1):
            if url := await process_event(ev["link"], i):
                sport, event, link = (
                    ev["sport"],
                    ev["event"],
                    ev["link"],
                )

                key = f"[{sport}] {event} ({TAG})"

                tvg_id, logo = leagues.get_tvg_info(sport, event)

                entry = {
                    "url": url,
                    "logo": logo,
                    "base": "https://gooz.aapmains.net",
                    "timestamp": now,
                    "id": tvg_id or "Live.Event.us",
                    "link": link,
                }

                urls[key] = cached_urls[key] = entry

    if new_count := len(cached_urls) - cached_count:
        log.info(f"Collected and cached {new_count} new event(s)")

    else:
        log.info("No new events found")

    CACHE_FILE.write(cached_urls)

def main():
    playlist_lines = ["#EXTM3U"]

    sections = list(discover_sections(BASE_URL))
    if not sections:
        logging.error("No sections discovered.")
        return

    logging.info(f"Found {len(sections)} sections. Scraping for events...")

    for section_url, section_title in sections:
        logging.info(f"\n--- Processing Section: {section_title} ({section_url}) ---")

        tv_id, logo, group_name = get_tv_info(section_url)
        event_links = discover_event_links(section_url)

        if not event_links:
            logging.info(f"  No event sub-pages found. Scraping directly.")
            event_links = {(section_url, section_title)}

        valid_count = 0
        for event_url, event_title in event_links:
            logging.info(f"  Scraping: {event_title}")
            m3u8_links = extract_m3u8_links(event_url)

            for link in m3u8_links:
                if check_stream_status(link):
                    playlist_lines.append(
                        f'#EXTINF:-1 tvg-logo="{logo}" tvg-id="{tv_id}" group-title="Roxiestreams - {group_name}",{event_title}'
                    )
                    playlist_lines.append(link)
                    valid_count += 1

        logging.info(f"  Added {valid_count} valid streams for {group_name} section.")

    output_filename = "PPV.m3u8"
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write("\n".join(playlist_lines))
        logging.info(f"\n--- SUCCESS ---")
        logging.info(f"Playlist saved as {output_filename}")
        logging.info(f"Total valid streams found: {(len(playlist_lines) - 1) // 2}")
    except IOError as e:
        logging.error(f"Failed to write file {output_filename}: {e}")
