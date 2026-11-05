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
    "locale": "it",
    "market_code": "it"
}
HEADERS = {
    "Origin": "https://www.rakuten.tv",
    "Referer": "https://www.rakuten.tv/",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0",
    "Accept": "application/json, text/plain, */*"
}
OUTPUT = Path("temp/rakuten-test.m3u")
LIMIT = 3

VARIANTS = [
    ("not implemented", "false"),
    ("enigma2", "false"),
    ("not implemented", False),
    ("enigma2", False)
]


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    response = session.get(
        BASE + "/live_channels",
        params={**PARAMS, "page": 1, "per_page": LIMIT},
        timeout=(15, 30)
    )
    response.raise_for_status()
    channels = response.json().get("data", [])[:LIMIT]

    if not channels:
        raise RuntimeError("Rakuten non ha restituito canali per il test")

    print(f"Canali selezionati: {len(channels)}", flush=True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["#EXTM3U"]
    successful = 0

    for index, channel in enumerate(channels, 1):
        title = channel.get("title") or channel.get("id", "Sconosciuto")
        languages = channel.get("labels", {}).get("languages", [])

        print(f"\n--- CANALE {index}/{len(channels)}: {title} ---", flush=True)

        if not languages:
            print("SKIP: lingua assente", flush=True)
            continue

        success = False

        for variant_index, (device_serial, disable_dash) in enumerate(VARIANTS, 1):
            payload = {
                "audio_language": languages[0]["id"],
                "audio_quality": "2.0",
                "classification_id": 36,
                "content_id": channel["id"],
                "content_type": "live_channels",
                "device_serial": device_serial,
                "player": "web:HLS-NONE:NONE",
                "strict_video_quality": False,
                "subtitle_language": "MIS",
                "video_type": "stream"
            }
            params = {
                **STREAM_PARAMS,
                "disable_dash_legacy_packages": disable_dash
            }

            print(
                f"Tentativo {variant_index}/4: device_serial={device_serial}, "
                f"disable_dash_legacy_packages={disable_dash!r}",
                flush=True
            )

            try:
                result = session.post(
                    BASE + "/avod/streamings",
                    params=params,
                    json=payload,
                    timeout=(15, 30)
                )
                print(f"HTTP {result.status_code}", flush=True)

                if not result.ok:
                    print(f"Risposta: {result.text[:1200]}", flush=True)
                    continue

                data = result.json()
                infos = data.get("data", {}).get("stream_infos", [])
                stream_url = infos[0].get("url") if infos else None

                if not stream_url:
                    print(f"Stream assente: {result.text[:1200]}", flush=True)
                    continue

                images = channel.get("images") or {}
                logo = images.get("artwork_negative", "")
                safe_title = str(title).replace('"', "'")
                safe_logo = str(logo).replace('"', "'")
                channel_id = str(channel.get("id", "")).replace('"', "'")

                lines.append(
                    f'#EXTINF:-1 tvg-id="{channel_id}" '
                    f'tvg-name="{safe_title}" tvg-logo="{safe_logo}",{safe_title}'
                )
                lines.append(stream_url)
                successful += 1
                success = True
                print("STREAM OK", flush=True)
                break

            except requests.RequestException as error:
                print(f"ERRORE HTTP: {error}", flush=True)
                if getattr(error, "response", None) is not None:
                    print(f"Risposta: {error.response.text[:1200]}", flush=True)

        if not success:
            print("NESSUNA VARIANTE HA FUNZIONATO", flush=True)

    if successful:
        OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nPlaylist test: {OUTPUT} ({successful} canali)", flush=True)
    else:
        print("\nNessuno stream disponibile: playlist non creata.", flush=True)

    print(f"\nRISULTATO: {successful}/{len(channels)} canali", flush=True)


if __name__ == "__main__":
    main()
