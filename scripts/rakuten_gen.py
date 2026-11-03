import time
from pathlib import Path

import requests

BASE = "https://gizmo.rakuten.tv/v3"
OUTPUT = Path(__file__).resolve().parent.parent / "output" / "Rakuten@it.m3u"

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


def get_catalog(session):
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

    for channel in channels.values():
        channel["rakuten_category"] = category_map.get(
            channel["id"], ""
        )

    print(f"\nCOMPLETATO: {len(channels)} canali", flush=True)

    return list(channels.values())


def get_streams(session, channels):
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

    available = {}
    error_body_logged = False

    for i, channel in enumerate(channels, 1):
        languages = channel.get("labels", {}).get("languages", [])

        if not languages:
            print(
                f"{i}/{len(channels)} NO  "
                f"{channel['title']}: lingua assente",
                flush=True
            )
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
            if response.status_code >= 400 and not error_body_logged:
                print(
                    f"RISPOSTA RAKUTEN {response.status_code}: "
                    f"{response.text[:1500]}",
                    flush=True
                )
                error_body_logged = True

            response.raise_for_status()

            data = response.json()
            infos = data.get("data", {}).get("stream_infos", [])
            url = infos[0].get("url") if infos else None

            if url:
                available[channel["id"]] = url

                print(
                    f"{i}/{len(channels)} OK  "
                    f"{channel['title']}",
                    flush=True
                )
            else:
                error = data.get(
                    "errors",
                    data.get("error", "stream assente")
                )

                print(
                    f"{i}/{len(channels)} NO  "
                    f"{channel['title']}: {str(error)[:160]}",
                    flush=True
                )

        except Exception as e:
            print(
                f"{i}/{len(channels)} ERRORE "
                f"{channel['title']}: {e}",
                flush=True
            )

        time.sleep(0.3)

    print(f"\nSTREAM DISPONIBILI: {len(available)}", flush=True)
    print(
        f"NON DISPONIBILI: {len(channels) - len(available)}",
        flush=True
    )

    if not available:
        raise RuntimeError("Nessuno stream Rakuten disponibile")

    return available


def generate_playlist(channels, streams):
    lines = ["#EXTM3U"]

    for channel in channels:
        channel_id = channel["id"]
        url = streams.get(channel_id)

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

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(
        f"\nPlaylist creata: {OUTPUT} "
        f"({len(streams)} stream disponibili)",
        flush=True
    )


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    channels = get_catalog(session)
    streams = get_streams(session, channels)
    generate_playlist(channels, streams)


if __name__ == "__main__":
    main()
