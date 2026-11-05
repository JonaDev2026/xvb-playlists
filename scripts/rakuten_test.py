import json
from pathlib import Path

import requests

BASE = "https://gizmo.rakuten.tv/v3"
PARAMS = {
    "classification_id": 36,
    "device_identifier": "web",
    "locale": "it",
    "market_code": "it"
}
STREAM_PARAMS = {
    "classification_id": 36,
    "device_identifier": "web",
    "device_stream_audio_quality": "2.0",
    "device_stream_hdr_type": "NONE",
    "device_stream_video_quality": "FHD",
    "disable_dash_legacy_packages": "false",
    "locale": "it",
    "market_code": "it"
}
HEADERS = {
    "Origin": "https://rakuten.tv",
    "Referer": "https://rakuten.tv/",
    "User-Agent": "Mozilla/5.0"
}
OUTPUT = Path("rakuten-test.m3u")
LIMIT = 3


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    response = session.get(
        BASE + "/live_channels",
        params={**PARAMS, "page": 1, "per_page": 50},
        timeout=30
    )
    response.raise_for_status()
    channels = response.json().get("data", [])[:LIMIT]

    print(f"Canali selezionati per il test: {len(channels)}", flush=True)

    lines = ["#EXTM3U"]
    available = 0

    for index, channel in enumerate(channels, 1):
        title = channel.get("title", channel.get("id", "Sconosciuto"))
        languages = channel.get("labels", {}).get("languages", [])

        if not languages:
            print(f"\n{index}/{len(channels)} {title}: lingua assente", flush=True)
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

        print(f"\n--- TEST {index}/{len(channels)}: {title} ---", flush=True)
        print("Payload:", json.dumps(payload, ensure_ascii=False), flush=True)

        try:
            result = session.post(
                BASE + "/avod/streamings",
                params=STREAM_PARAMS,
                json=payload,
                timeout=20
            )

            print(f"HTTP: {result.status_code}", flush=True)

            if not result.ok:
                print("Risposta Rakuten:", result.text, flush=True)
                continue

            data = result.json()
            infos = data.get("data", {}).get("stream_infos", [])
            stream_url = infos[0].get("url") if infos else None

            if not stream_url:
                print("Risposta Rakuten:", result.text, flush=True)
                continue

            images = channel.get("images") or {}
            logo = images.get("artwork_negative", "")
            title_safe = str(title).replace('"', "'")
            lines.append(
                f'#EXTINF:-1 tvg-id="{channel["id"]}" '
                f'tvg-name="{title_safe}" tvg-logo="{logo}",{title_safe}'
            )
            lines.append(stream_url)
            available += 1
            print("STREAM OK", flush=True)

        except requests.RequestException as error:
            print(f"ERRORE HTTP: {error}", flush=True)
            if getattr(error, "response", None) is not None:
                print("Risposta Rakuten:", error.response.text, flush=True)
        except (ValueError, KeyError, IndexError) as error:
            print(f"ERRORE RISPOSTA: {error}", flush=True)

    if available:
        OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nPlaylist di test creata: {OUTPUT} ({available} canali)", flush=True)
    else:
        print("\nNessuno stream disponibile: nessuna playlist creata.", flush=True)

    print(f"\nTEST COMPLETATO: {available}/{len(channels)} stream", flush=True)


if __name__ == "__main__":
    main()
