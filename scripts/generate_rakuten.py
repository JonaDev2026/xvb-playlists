import json
import time
import sys
from pathlib import Path

import requests

BASE = "https://gizmo.rakuten.tv/v3"
CLASSIFICATION_ID = 36

PARAMS = {
    "classification_id": 36,
    "device_identifier": "web",
    "locale": "it",
    "market_code": "it"
}

HEADERS = {
    "Origin": "https://rakuten.tv",
    "Referer": "https://rakuten.tv/",
    "User-Agent": "Mozilla/5.0"
}

OUTPUT = Path("output")
OUTPUT.mkdir(parents=True, exist_ok=True)

CATALOG_FILE = OUTPUT / "rakuten_it.json"
STREAMS_FILE = OUTPUT / "rakuten_streams.json"
PLAYLIST_FILE = OUTPUT / "rakuten_it.m3u"


def get_catalog():
    session = requests.Session()
    session.headers.update(HEADERS)

    channels = {}
    page = 1

    while True:
        params = {**PARAMS, "page": page, "per_page": 50}

        response = session.get(
            BASE + "/live_channels",
            params=params,
            timeout=30
        )
        response.raise_for_status()

        data = response.json().get("data", [])

        if not data:
            break

        for channel in data:
            channels[channel["id"]] = channel

        print(
            f"Pagina {page}: {len(data)} canali | "
            f"Totale: {len(channels)}",
            flush=True
        )

        if len(data) < 50:
            break

        page += 1
        time.sleep(0.3)

    response = session.get(
        BASE + "/live_channel_categories",
        params=PARAMS,
        timeout=30
    )
    response.raise_for_status()

    categories = response.json()
    category_map = {}

    for category in categories.get("data", []):
        for channel_id in category.get("live_channels", []):
            category_map[channel_id] = category.get("name", "")

    result = []

    for channel in channels.values():
        channel["rakuten_category"] = category_map.get(
            channel["id"], ""
        )
        result.append(channel)

    output = {
        "country": "it",
        "total_channels": len(result),
        "categories": categories,
        "channels": result
    }

    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nCOMPLETATO: {len(result)} canali", flush=True)
    print(f"File creato: {CATALOG_FILE}", flush=True)


def get_streams():
    with open(CATALOG_FILE, encoding="utf-8") as f:
        catalog = json.load(f)

    session = requests.Session()
    session.headers.update(HEADERS)

    base = BASE + "/avod/streamings"

    params = {
        "classification_id": 36,
        "device_identifier": "web",
        "device_stream_audio_quality": "2.0",
        "device_stream_hdr_type": "NONE",
        "device_stream_video_quality": "FHD",
        "disable_dash_legacy_packages": "false",
        "locale": "it",
        "market_code": "it"
    }

    ok = []
    ko = []

    for i, channel in enumerate(catalog["channels"], 1):
        languages = channel.get("labels", {}).get("languages", [])

        if not languages:
            ko.append((channel["title"], "lingua assente"))
            continue

        payload = {
            "audio_language": languages[0]["id"],
            "audio_quality": "2.0",
            "classification_id": 36,
            "content_id": channel["id"],
            "content_type": "live_channels",
            "device_serial": "not implemented",
            "player": "web:HLS-NONE:NONE",
            "strict_video_quality": False,
            "subtitle_language": "MIS",
            "video_type": "stream"
        }

        try:
            response = session.post(
                base,
                params=params,
                json=payload,
                timeout=20
            )

            data = response.json()
            infos = data.get("data", {}).get("stream_infos", [])
            url = infos[0].get("url") if infos else None

            if url:
                ok.append({
                    "id": channel["id"],
                    "title": channel["title"],
                    "url": url
                })
                print(
                    f"{i}/{len(catalog['channels'])} OK  "
                    f"{channel['title']}",
                    flush=True
                )
            else:
                error = data.get(
                    "errors",
                    data.get("error", "stream assente")
                )
                ko.append((channel["title"], str(error)[:160]))
                print(
                    f"{i}/{len(catalog['channels'])} NO  "
                    f"{channel['title']}: {str(error)[:160]}",
                    flush=True
                )

        except Exception as e:
            ko.append((channel["title"], str(e)))
            print(
                f"{i}/{len(catalog['channels'])} ERRORE "
                f"{channel['title']}: {e}",
                flush=True
            )

        time.sleep(0.3)

    with open(STREAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"available": ok, "unavailable": ko},
            f,
            ensure_ascii=False,
            indent=2
        )

    print(f"\nSTREAM DISPONIBILI: {len(ok)}", flush=True)
    print(f"NON DISPONIBILI: {len(ko)}", flush=True)
    print(f"File creato: {STREAMS_FILE}", flush=True)

    if not ok:
        raise RuntimeError("Nessuno stream Rakuten disponibile")


def generate_playlist():
    with open(CATALOG_FILE, encoding="utf-8") as f:
        catalog = json.load(f)

    with open(STREAMS_FILE, encoding="utf-8") as f:
        streams = json.load(f)

    stream_map = {
        channel["id"]: channel["url"]
        for channel in streams["available"]
    }

    lines = ["#EXTM3U"]

    for channel in catalog["channels"]:
        channel_id = channel["id"]
        url = stream_map.get(channel_id)

        if not url:
            continue

        title = str(channel.get("title", "")).replace('"', "'")
        category = str(
            channel.get("rakuten_category") or "Altri"
        ).replace('"', "'")

        images = channel.get("images") or {}
        logo = images.get("artwork_negative", "")
        number = channel.get("channel_number", "")

        lines.append(
            f'#EXTINF:-1 tvg-id="{channel_id}" '
            f'tvg-name="{title}" '
            f'tvg-logo="{logo}" '
            f'tvg-chno="{number}" '
            f'group-title="{category}",{title}'
        )
        lines.append(url)

    with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(
        f"\nPlaylist creata: {PLAYLIST_FILE} "
        f"({len(stream_map)} stream disponibili)",
        flush=True
    )


def main():
    get_catalog()
    get_streams()
    generate_playlist()


if __name__ == "__main__":
    main()
