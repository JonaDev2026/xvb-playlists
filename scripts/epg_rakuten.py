import os
import re
import time
import requests
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PLAYLIST_URL = "https://raw.githubusercontent.com/JonaDev2026/xvb-playlists/refs/heads/main/output/Rakuten%40it.m3u"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(BASE_DIR, "epg", "rakuten_it.xml")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

API_URL = "https://gizmo.rakuten.tv/v3/live_channels"

HEADERS = {
    "Origin": "https://www.rakuten.tv",
    "Referer": "https://www.rakuten.tv/",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0",
    "Accept": "application/json, text/plain, */*"
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

RETRY = Retry(
    total=4,
    connect=4,
    read=3,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)

SESSION.mount("https://", HTTPAdapter(max_retries=RETRY))


def extract_numeric_ids(url):
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    found = set()

    for key, values in params.items():
        if key.lower() in (
            "channel_id",
            "ads.rtv_channel_id",
            "ads.rtv_content_id"
        ):
            for value in values:
                if value.isdigit():
                    found.add(int(value))

    return found


def get_playlist():
    response = SESSION.get(PLAYLIST_URL, timeout=(15, 60))
    response.raise_for_status()

    channels = []
    current = None

    for line in response.text.splitlines():
        line = line.strip()

        if line.startswith("#EXTINF:"):
            match = re.search(
                r'tvg-id="([^"]*)".*?tvg-name="([^"]*)".*?tvg-logo="([^"]*)"',
                line
            )

            if not match:
                current = None
                continue

            current = {
                "id": match.group(1),
                "name": match.group(2),
                "logo": match.group(3),
                "url": ""
            }

        elif line.startswith("http") and current:
            current["url"] = line
            current["numeric_ids"] = extract_numeric_ids(line)
            channels.append(current)
            current = None

    return channels


def api_request(page=1, start=None, end=None):
    params = {
        "classification_id": 36,
        "device_identifier": "web",
        "device_stream_audio_quality": "2.0",
        "device_stream_hdr_type": "NONE",
        "device_stream_video_quality": "FHD",
        "epg_duration_minutes": 240,
        "locale": "it",
        "market_code": "it",
        "page": page,
        "per_page": 25
    }

    if start and end:
        params.update({
            "epg_starts_at": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "epg_starts_at_timestamp": int(start.timestamp()),
            "epg_ends_at": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "epg_ends_at_timestamp": int(end.timestamp())
        })

    response = SESSION.get(
        API_URL,
        params=params,
        timeout=(15, 60)
    )
    response.raise_for_status()

    return response.json().get("data", [])


def get_catalogue():
    catalogue = {}
    print("Recupero catalogo Rakuten Italia...")

    page = 1

    while True:
        print(f"Catalogo italiano - pagina {page}")
        channels = api_request(page)

        if not channels:
            break

        for channel in channels:
            api_id = channel.get("id")

            if api_id:
                catalogue[str(api_id).strip().lower()] = channel

        if len(channels) < 25:
            break

        page += 1
        time.sleep(0.3)

    return catalogue


def parse_timestamp(program, *keys):
    for key in keys:
        value = program.get(key)

        if value is None:
            continue

        try:
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value, timezone.utc)

            return datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            ).astimezone(timezone.utc)

        except (ValueError, TypeError, OverflowError):
            pass

    return None


def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def main():
    print("Lettura playlist Rakuten...")
    playlist = get_playlist()

    if not playlist:
        raise RuntimeError("Nessun canale trovato nella playlist")

    print(f"Canali nella playlist: {len(playlist)}")

    catalogue = get_catalogue()

    matched = []
    unmatched = []

    for channel in playlist:
        api_channel = catalogue.get(channel["id"].strip().lower())

        if api_channel:
            channel["api_id"] = api_channel.get("id")
            channel["numerical_id"] = api_channel.get("numerical_id")
            matched.append(channel)
        else:
            unmatched.append(channel)

    print(f"Canali associati al catalogo Rakuten: {len(matched)}")
    print(f"Canali senza corrispondenza: {len(unmatched)}")

    for channel in unmatched:
        print(f"NON TROVATO: {channel['id']} - {channel['name']}")

    if not matched:
        raise RuntimeError("Nessun canale della playlist associato al catalogo Rakuten")

    root = ET.Element("tv", attrib={"source-info-name": "Rakuten TV"})

    for channel in playlist:
        element = ET.SubElement(root, "channel", id=channel["id"])
        ET.SubElement(element, "display-name").text = channel["name"]

        if channel["logo"]:
            ET.SubElement(element, "icon", src=channel["logo"])

    now = datetime.now(timezone.utc).replace(
        minute=0,
        second=0,
        microsecond=0
    )

    finish = now + timedelta(days=3)
    windows = []
    cursor = now

    while cursor < finish:
        end = min(cursor + timedelta(hours=4), finish)
        windows.append((cursor, end))
        cursor = end

    programmes = set()
    total = 0

    matched_by_numeric_id = {}

    for channel in matched:
        numeric_id = channel.get("numerical_id")

        if numeric_id is not None:
            matched_by_numeric_id.setdefault(
                int(numeric_id), []
            ).append(channel)

    print(f"\nMercato IT - {len(matched)} canali")

    for start, end in windows:
        print(
            f"Finestra: {start.strftime('%d/%m %H:%M')} - "
            f"{end.strftime('%d/%m %H:%M')}"
        )

        page = 1

        while True:
            try:
                api_channels = api_request(page, start, end)

                if not api_channels:
                    break

                for api_channel in api_channels:
                    numeric_id = api_channel.get("numerical_id")

                    if numeric_id is None:
                        continue

                    target_channels = matched_by_numeric_id.get(
                        int(numeric_id), []
                    )

                    if not target_channels:
                        continue

                    live_programs = api_channel.get("live_programs", [])

                    if isinstance(live_programs, dict):
                        live_programs = live_programs.get("data", [])

                    for program in live_programs:
                        title = clean_text(
                            program.get("title") or program.get("name")
                        )

                        if not title:
                            continue

                        start_time = parse_timestamp(
                            program,
                            "starts_at_timestamp",
                            "starts_at"
                        )

                        end_time = parse_timestamp(
                            program,
                            "ends_at_timestamp",
                            "ends_at"
                        )

                        if not start_time or not end_time:
                            continue

                        description = clean_text(
                            program.get("description")
                        )

                        for target in target_channels:
                            key = (
                                target["id"],
                                start_time,
                                end_time,
                                title
                            )

                            if key in programmes:
                                continue

                            programmes.add(key)

                            element = ET.SubElement(
                                root,
                                "programme",
                                start=start_time.strftime("%Y%m%d%H%M%S +0000"),
                                stop=end_time.strftime("%Y%m%d%H%M%S +0000"),
                                channel=target["id"]
                            )

                            ET.SubElement(
                                element,
                                "title",
                                lang="it"
                            ).text = title

                            if description:
                                ET.SubElement(
                                    element,
                                    "desc",
                                    lang="it"
                                ).text = description

                            total += 1

                if len(api_channels) < 25:
                    break

                page += 1
                time.sleep(0.3)

            except Exception as error:
                print(f"Errore pagina {page}: {error}")
                raise

        time.sleep(0.3)

    if total == 0:
        raise RuntimeError("EPG Rakuten vuoto: nessun programma recuperato")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)
    temporary_file = os.path.join(TEMP_DIR, "rakuten_it.xml.tmp")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")

    tree.write(
        temporary_file,
        encoding="utf-8",
        xml_declaration=True
    )

    ET.parse(temporary_file)
    os.replace(temporary_file, OUTPUT_FILE)

    print("\nCompletato")
    print(f"Canali playlist: {len(playlist)}")
    print(f"Canali associati: {len(matched)}")
    print(f"Programmi EPG: {total}")
    print(f"File creato: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
