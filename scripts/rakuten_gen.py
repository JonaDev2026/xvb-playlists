import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
SOURCE_URL = "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/it_rakuten.m3u"
API_BASE = "https://gizmo.rakuten.tv/v3"
EPG_FILE = ROOT / "epg" / "rakuten_it.xml"
OUTPUT_FILE = ROOT / "output" / "Rakuten@it.m3u"
TEMP_FILE = ROOT / "temp" / "Rakuten@it.m3u.tmp"

PARAMS = {
    "classification_id": 36,
    "device_identifier": "web",
    "locale": "it",
    "market_code": "it",
}

HEADERS = {
    "Origin": "https://www.rakuten.tv",
    "Referer": "https://www.rakuten.tv/",
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
}


def clean(value):
    return str(value or "").replace('"', "'").strip()


def parse_playlist(text):
    channels = []
    current = None

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if line.startswith("#EXTINF:"):
            title = line.rsplit(",", 1)[-1].strip() if "," in line else ""
            match = re.search(r'tvg-id="([^"]*)"', line)
            current = {
                "source_id": match.group(1).strip() if match else "",
                "name": title,
                "url": "",
            }

        elif line.startswith(("http://", "https://")) and current:
            current["url"] = line
            channels.append(current)
            current = None

    return channels


def load_epg_ids():
    if not EPG_FILE.is_file():
        raise FileNotFoundError(f"EPG Rakuten non trovato: {EPG_FILE}")

    root = ET.parse(EPG_FILE).getroot()
    ids = {
        element.get("id", "").strip()
        for element in root.findall("./channel")
        if element.get("id")
    }

    if not ids:
        raise RuntimeError("Nessun ID canale trovato nell'EPG Rakuten")

    return ids


def extract_numeric_ids(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    found = set()

    for key, values in query.items():
        normalized = key.lower().replace("_", ".")
        if normalized in {
            "channel.id",
            "ads.rtv.channel.id",
            "ads.rtv.content.id",
        }:
            for value in values:
                if value.isdigit():
                    found.add(int(value))

    for value in re.findall(r"LiveChannel-(\d+)", parsed.path, re.IGNORECASE):
        found.add(int(value))

    return found


def get_catalogue(session):
    catalogue = {}
    page = 1

    while True:
        response = session.get(
            API_BASE + "/live_channels",
            params={**PARAMS, "page": page, "per_page": 50},
            timeout=(15, 60),
        )
        response.raise_for_status()
        channels = response.json().get("data", [])

        if not channels:
            break

        for channel in channels:
            channel_id = str(channel.get("id") or "").strip()
            if channel_id:
                catalogue[channel_id] = channel

        print(f"Catalogo Rakuten pagina {page}: {len(channels)} | Totale: {len(catalogue)}", flush=True)

        if len(channels) < 50:
            break

        page += 1
        time.sleep(0.3)

    if not catalogue:
        raise RuntimeError("Il catalogo API Rakuten è vuoto")

    response = session.get(
        API_BASE + "/live_channel_categories",
        params=PARAMS,
        timeout=(15, 60),
    )
    response.raise_for_status()

    categories = {}
    for category in response.json().get("data", []):
        name = clean(category.get("name"))
        for channel_id in category.get("live_channels", []):
            categories[str(channel_id)] = name

    by_numeric_id = {}
    for channel_id, channel in catalogue.items():
        numeric_id = channel.get("numerical_id")
        if numeric_id is not None:
            by_numeric_id.setdefault(str(numeric_id), []).append(channel)

        channel["rakuten_category"] = categories.get(channel_id, "")

    return catalogue, by_numeric_id


def match_channel(source, epg_ids, catalogue, by_numeric_id):
    source_id = source["source_id"]

    if source_id in epg_ids and source_id in catalogue:
        return catalogue[source_id]

    candidates = {}
    for numeric_id in extract_numeric_ids(source["url"]):
        for channel in by_numeric_id.get(str(numeric_id), []):
            channel_id = str(channel.get("id") or "")
            if channel_id in epg_ids:
                candidates[channel_id] = channel

    if len(candidates) == 1:
        return next(iter(candidates.values()))

    return None


def generate_playlist(source_channels, epg_ids, catalogue, by_numeric_id):
    lines = ["#EXTM3U"]
    included = set()
    skipped = []

    for source in source_channels:
        channel = match_channel(source, epg_ids, catalogue, by_numeric_id)

        if not channel:
            skipped.append(source["name"])
            continue

        channel_id = str(channel.get("id") or "").strip()
        if not channel_id or channel_id not in epg_ids or channel_id in included:
            continue

        images = channel.get("images") or {}
        logo = images.get("artwork_negative") or ""
        title = clean(source["name"] or channel.get("title") or channel_id)
        category = clean(channel.get("rakuten_category") or "Altri")
        number = clean(channel.get("channel_number"))

        lines.append(
            f'#EXTINF:-1 tvg-id="{channel_id}" '
            f'tvg-name="{title}" '
            f'tvg-logo="{clean(logo)}" '
            f'tvg-chno="{number}" '
            f'group-title="{category}",{title}'
        )
        lines.append(source["url"])
        included.add(channel_id)

    if not included:
        raise RuntimeError(
            "Nessun canale iptv-org associato agli ID presenti in epg/rakuten_it.xml"
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEMP_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEMP_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    TEMP_FILE.replace(OUTPUT_FILE)

    print(f"Canali iptv-org letti: {len(source_channels)}")
    print(f"Canali presenti nell'EPG e inseriti: {len(included)}")
    print(f"Canali non associati: {len(skipped)}")
    for name in skipped:
        print(f"NON ASSOCIATO: {name}")
    print(f"Playlist creata: {OUTPUT_FILE}", flush=True)


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    print("Lettura playlist iptv-org...", flush=True)
    response = session.get(SOURCE_URL, timeout=(15, 60))
    response.raise_for_status()
    source_channels = parse_playlist(response.text)

    if not source_channels:
        raise RuntimeError("La playlist iptv-org è vuota o non valida")

    print(f"Stream iptv-org letti: {len(source_channels)}", flush=True)

    epg_ids = load_epg_ids()
    print(f"ID presenti nell'EPG Rakuten: {len(epg_ids)}", flush=True)

    catalogue, by_numeric_id = get_catalogue(session)
    generate_playlist(source_channels, epg_ids, catalogue, by_numeric_id)


if __name__ == "__main__":
    main()
