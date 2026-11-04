import requests
import time

BASE = "https://gizmo.rakuten.tv/v3"

HEADERS = {
    "Origin": "https://rakuten.tv",
    "Referer": "https://rakuten.tv/",
    "User-Agent": "Mozilla/5.0"
}

BASE_PARAMS = {
    "classification_id": 36,
    "device_identifier": "web",
    "device_stream_audio_quality": "2.0",
    "device_stream_hdr_type": "NONE",
    "device_stream_video_quality": "FHD",
    "locale": "it",
    "market_code": "it"
}


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    catalog_params = {
        "classification_id": 36,
        "device_identifier": "web",
        "locale": "it",
        "market_code": "it",
        "page": 1,
        "per_page": 50
    }

    response = session.get(
        BASE + "/live_channels",
        params=catalog_params,
        timeout=30
    )
    response.raise_for_status()

    channels = response.json().get("data", [])
    channel = next(
        (
            item for item in channels
            if item.get("labels", {}).get("languages")
        ),
        None
    )

    if not channel:
        print("PROBE: nessun canale con lingua disponibile", flush=True)
        return

    language = channel["labels"]["languages"][0]["id"]
    print(
        f"PROBE CANALE: {channel.get('title')} | "
        f"ID: {channel.get('id')} | LINGUA: {language}",
        flush=True
    )

    variants = [
        ("attuale", "not implemented", "false"),
        ("boolean_false", "not implemented", False),
        ("serial_enigma2", "enigma2", "false"),
        ("enigma2_boolean_false", "enigma2", False)
    ]

    for name, serial, disable_dash in variants:
        params = {
            **BASE_PARAMS,
            "disable_dash_legacy_packages": disable_dash
        }

        payload = {
            "audio_language": language,
            "audio_quality": "2.0",
            "classification_id": 36,
            "content_id": channel["id"],
            "content_type": "live_channels",
            "device_serial": serial,
            "player": "web:HLS-NONE:NONE",
            "strict_video_quality": False,
            "subtitle_language": "MIS",
            "video_type": "stream"
        }

        try:
            result = session.post(
                BASE + "/avod/streamings",
                params=params,
                json=payload,
                timeout=25
            )
            print(
                f"PROBE {name}: HTTP {result.status_code} | "
                f"{result.text[:1200]}",
                flush=True
            )
        except Exception as error:
            print(f"PROBE {name}: {error}", flush=True)

        time.sleep(0.5)


if __name__ == "__main__":
    main()
