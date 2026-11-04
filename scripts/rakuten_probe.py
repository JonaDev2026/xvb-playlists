import requests

BASE = "https://gizmo.rakuten.tv/v3"

BASE_PARAMS = {
    "classification_id": 36,
    "device_identifier": "web",
    "device_stream_audio_quality": "2.0",
    "device_stream_hdr_type": "NONE",
    "device_stream_video_quality": "FHD",
    "disable_dash_legacy_packages": "false",
    "locale": "it",
    "market_code": "it"
}

BROWSER_HEADERS = {
    "Origin": "https://www.rakuten.tv",
    "Referer": "https://www.rakuten.tv/",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en,it-IT;q=0.9,it;q=0.8,en-US;q=0.7",
    "Content-Type": "application/json"
}

PLUGIN_HEADERS = {
    "Origin": "https://rakuten.tv",
    "Referer": "https://rakuten.tv/",
    "User-Agent": "Mozilla/5.0"
}


def main():
    session = requests.Session()
    session.headers.update(PLUGIN_HEADERS)

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
        (item for item in channels if item.get("labels", {}).get("languages")),
        None
    )

    if not channel:
        print("PROBE: nessun canale con lingua disponibile", flush=True)
        return

    language = channel["labels"]["languages"][0]["id"]
    print(
        f"PROBE CANALE: {channel.get('title')} | ID: {channel.get('id')} | LINGUA: {language}",
        flush=True
    )

    base_payload = {
        "audio_language": language,
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

    variants = [
        ("browser_headers", BROWSER_HEADERS, dict(base_payload)),
        ("browser_headers_serial_enigma2", BROWSER_HEADERS, {**base_payload, "device_serial": "enigma2"}),
        ("browser_headers_video_quality_body", BROWSER_HEADERS, {**base_payload, "device_stream_video_quality": "FHD"}),
        ("browser_headers_captions", BROWSER_HEADERS, {**base_payload, "support_closed_captions": True})
    ]

    for name, headers, payload in variants:
        try:
            result = requests.post(
                BASE + "/avod/streamings",
                headers=headers,
                params=BASE_PARAMS,
                json=payload,
                timeout=25
            )
            print(
                f"PROBE {name}: HTTP {result.status_code} | {result.text[:1500]}",
                flush=True
            )
        except Exception as error:
            print(f"PROBE {name}: {error}", flush=True)


if __name__ == "__main__":
    main()
