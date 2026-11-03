#!/usr/bin/env python3
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://gizmo.rakuten.tv/v3"
CLASSIFICATION_ID = 36
LOCALE = "it"
HEADERS = {
    "Origin": "https://www.rakuten.tv",
    "Referer": "https://www.rakuten.tv/",
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
}
PARAMS = {
    "classification_id": CLASSIFICATION_ID,
    "device_identifier": "web",
    "locale": LOCALE,
    "market_code": LOCALE,
}
OUT = Path("output")
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def get_json(path, params=None):
    response = SESSION.get(BASE + path, params=params or PARAMS, timeout=30)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and data.get("errors"):
        raise RuntimeError(f"Rakuten API error on {path}: {data['errors']}")
    return data


def get_channels():
    channels = []
    page = 1
    while True:
        params = dict(PARAMS, page=page, per_page=50)
        payload = get_json("/live_channels", params)
        batch = payload.get("data") or []
        if not batch:
            break
        channels.extend(batch)
        if len(batch) < 50:
            break
        page += 1
    if not channels:
        raise RuntimeError("Rakuten returned no live channels")
    return channels


def get_categories():
    payload = get_json("/live_channel_categories")
    result = {}
    for category in payload.get("data") or []:
        name = category.get("name") or category.get("title") or "Altri"
        for channel_id in category.get("live_channels") or []:
            result[channel_id] = name
    return result


def get_stream(channel):
    languages = (channel.get("labels") or {}).get("languages") or []
    if not languages or not languages[0].get("id"):
        return ""
    audio_language = languages[0]["id"]
    query = dict(
        PARAMS,
        device_stream_audio_quality="2.0",
        device_stream_hdr_type="NONE",
        device_stream_video_quality="FHD",
        disable_dash_legacy_packages="false",
    )
    body = {
        "audio_language": audio_language,
        "audio_quality": "2.0",
        "classification_id": CLASSIFICATION_ID,
        "content_id": channel["id"],
        "content_type": "live_channels",
        "device_serial": "not implemented",
        "player": "web:HLS-NONE:NONE",
        "strict_video_quality": False,
        "subtitle_language": "MIS",
        "video_type": "stream",
    }
    for attempt in range(3):
        try:
            response = SESSION.post(BASE + "/avod/streamings", params=query, json=body, timeout=30)
            if response.status_code == 422:
                print(
                    f"Rakuten 422 per {channel.get('id')}: {response.text[:500]}",
                    file=sys.stderr,
                    flush=True,
                )
                return ""
            response.raise_for_status()
            payload = response.json()
            infos = (payload.get("data") or {}).get("stream_infos") or []
            url = next((item.get("url") for item in infos if item.get("url")), "")
            if url:
                return url.split(".m3u8", 1)[0] + ".m3u8" if ".m3u8" in url else url
            return ""
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return ""


def clean(value):
    return re.sub(r'[\\r\\n"]+', " ", str(value or "")).strip()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    categories = get_categories()
    raw_channels = get_channels()
    output = []
    lines = ["#EXTM3U"]

    raw_channels.sort(key=lambda c: (int(c.get("channel_number") or 99999), clean(c.get("title"))))
    for index, channel in enumerate(raw_channels, 1):
        channel_id = channel.get("id")
        if not channel_id:
            continue
        title = clean(channel.get("title")) or channel_id
        category = categories.get(channel_id, "Altri")
        number = channel.get("channel_number")
        images = channel.get("images") or {}
        logo = images.get("artwork_negative") or images.get("artwork") or ""
        try:
            stream_url = get_stream(channel)
        except requests.RequestException as exc:
            print(f"Errore stream {channel_id}: {exc}", file=sys.stderr, flush=True)
            stream_url = ""
        item = {
            "id": channel_id,
            "numerical_id": channel.get("numerical_id"),
            "channel_number": number,
            "title": title,
            "category": category,
            "logo": logo,
            "url": stream_url,
            "language_ids": [
                lang.get("id") for lang in ((channel.get("labels") or {}).get("languages") or [])
                if lang.get("id")
            ],
        }
        output.append(item)
        if stream_url:
            attrs = [
                f'tvg-id="{clean(channel_id)}"',
                f'tvg-name="{title}"',
                f'tvg-logo="{clean(logo)}"',
                f'tvg-chno="{clean(number)}"',
                f'group-title="{category}"',
            ]
            lines.append(f"#EXTINF:-1 {' '.join(attrs)},{title}")
            lines.append(stream_url)
        print(f"[{index}/{len(raw_channels)}] {title}: {'OK' if stream_url else 'stream non disponibile'}", flush=True)

    available = sum(bool(item["url"]) for item in output)
    if available == 0:
        raise RuntimeError("No playable streams returned; output files were not updated")

    document = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "country": "it",
        "total_channels": len(output),
        "available_streams": available,
        "channels": output,
    }
    (OUT / "rakuten_it.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT / "rakuten_it.m3u").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Creati {OUT / 'rakuten_it.m3u'} e {OUT / 'rakuten_it.json'}")
    print(f"Canali: {len(output)} | stream disponibili: {available}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        sys.exit(1)
