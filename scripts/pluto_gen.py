
import re
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output" / "Pluto@it.m3u"
TEMP = ROOT / "temp"

MASTER_URL = "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/it_pluto.m3u"

TOKEN_URL = (
    "https://boot.pluto.tv/v4/start"
    "?appName=web"
    "&appVersion=9.15.0-eb7e53f132160fea7492a1ba2db9044b730c24cc"
    "&clientID=1634bc91-acf1-40f2-ada1-c731446c0afb"
    "&clientModelNumber=1.0.0"
)

CHANNELS_URL = (
    "https://service-channels.clusters.pluto.tv/v2/guide/channels"
    "?channelIds=&offset=0&limit=1000&sort=number%3Aasc"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Forwarded-For": "131.114.130.239"
}

CATEGORIES = {
    "Cinema": [
        "cinema", "film", "movie", "movies", "western", "horror",
        "thriller", "action", "commedia", "drama", "crime",
        "romance", "fantascienza", "sci-fi"
    ],
    "Intrattenimento": [
        "show", "entertainment", "reality", "comedy", "tv",
        "serie", "series", "talent", "game", "varietà"
    ],
    "Sport": [
        "sport", "calcio", "football", "racing", "motors",
        "wrestling", "fight", "tennis", "fitness"
    ],
    "News": [
        "news", "notizie", "tg", "informazione", "breaking"
    ],
    "Documentari": [
        "documentary", "documentaries", "documentario",
        "documentari", "history", "storia", "nature",
        "natura", "science", "scienza", "wild"
    ],
    "Bambini": [
        "kids", "junior", "cartoon", "cartoons", "anime",
        "children", "bambini", "ragazzi"
    ],
    "Musica": [
        "music", "musica", "concert", "concerti", "mtv"
    ],
    "Lifestyle": [
        "cucina", "cooking", "food", "travel", "viaggi",
        "lifestyle", "casa", "home", "fashion", "moda"
    ]
}

def get_category(name):
    name = name.lower()

    for category, keywords in CATEGORIES.items():
        if any(keyword in name for keyword in keywords):
            return category

    return "Intrattenimento"

def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    print("Download master iptv-org...")
    response = session.get(MASTER_URL, timeout=30)
    response.raise_for_status()
    master = response.text

    print("Accesso API Pluto...")
    response = session.get(TOKEN_URL, timeout=30)
    response.raise_for_status()
    token = response.json()["sessionToken"]

    headers = {
        **HEADERS,
        "Authorization": f"Bearer {token}"
    }

    response = session.get(CHANNELS_URL, headers=headers, timeout=30)
    response.raise_for_status()
    channels = response.json().get("data", [])

    by_id = {
        str(channel["id"]).lower(): channel
        for channel in channels
        if channel.get("id")
    }

    output = ["#EXTM3U"]
    total = 0
    logos = 0
    categories = {}

    lines = master.splitlines()

    for i, line in enumerate(lines):
        if not line.startswith("#EXTINF:"):
            continue

        stream = ""
        for candidate in lines[i + 1:]:
            candidate = candidate.strip()
            if candidate and not candidate.startswith("#"):
                stream = candidate
                break

        if not stream:
            continue

        match = re.search(r"plu-([a-f0-9]+)", stream, re.IGNORECASE)
        if not match:
            continue

        channel = by_id.get(match.group(1).lower())

        logo = ""
        if channel:
            for image in channel.get("images", []):
                if image.get("type") == "colorLogoPNG" and image.get("url"):
                    logo = image["url"]
                    break

        name_match = re.search(r",(.+)$", line)
        name = name_match.group(1).strip() if name_match else ""

        category = get_category(name)
        categories[category] = categories.get(category, 0) + 1

        entry = re.sub(r'\s+tvg-logo="[^"]*"', "", line)
        entry = re.sub(r'\s+tvg-chno="[^"]*"', "", entry)
        entry = re.sub(r'\s+group-title="[^"]*"', "", entry)

        attributes = []

        if logo:
            attributes.append(f'tvg-logo="{logo}"')
            logos += 1

        number = channel.get("number") if channel else None
        if number is not None:
            try:
                attributes.append(f'tvg-chno="{int(float(number)) + 5000}"')
            except (ValueError, TypeError):
                pass

        attributes.append(f'group-title="{category}"')

        entry = entry.replace(
            "#EXTINF:-1",
            "#EXTINF:-1 " + " ".join(attributes),
            1
        )

        output.extend([entry, stream])
        total += 1

    if total < 20:
        raise RuntimeError(f"Playlist Pluto incompleta: solo {total} canali")

    streams = [output[i + 1] for i in range(1, len(output), 2)]
    if len(streams) != len(set(streams)):
        raise RuntimeError("Playlist Pluto: URL duplicati")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    TEMP.mkdir(parents=True, exist_ok=True)
    temporary = TEMP / "Pluto@it.m3u.tmp"
    temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)

    print()
    print(f"Canali: {total}")
    print(f"Loghi: {logos}")
    print(f"Senza logo: {total - logos}")
    print("Categorie:")

    for category, count in sorted(categories.items()):
        print(f"  {category}: {count}")

    print(f"\nOutput: {OUTPUT}")

if __name__ == "__main__":
    main()

