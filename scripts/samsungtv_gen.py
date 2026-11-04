import requests
import gzip
import json
import time
import os
from urllib.parse import urljoin, urlparse

SOURCE = "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/SamsungTVPlus/.channels.json.gz"
BASE = "https://jmp2.uk/stvp-"

OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "output",
    "SamTV+@it.m3u"
)

BLACKLIST = [
    "ITBA1500001R6",
    "IT4000061Q",
    "IT3200004WU",
    "IT700005C9",
    "IT4000089R"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://www.samsungtvplus.com",
    "Referer": "https://www.samsungtvplus.com/"
}

# Funzione per mappare i generi/categorie originali in massimo 5 macro-categorie
def map_category(genre_or_name):
    val = (genre_or_name or "").lower()
    
    if any(k in val for k in ["doc", "nature", "history", "documentari", "scienza", "natura", "storia", "wild", "planet", "fact"]):
        return "Documentari"
    elif any(k in val for k in ["news", "notizie", "meteo", "weather", "informazione", "euronews", "cnn"]):
        return "News"
    elif any(k in val for k in ["sport", "motor", "golf", "calcio", "tennis", "racing", "extreme", "fitness", "outdoor"]):
        return "Sport"
    elif any(k in val for k in ["film", "movie", "cinema", "serie", "series", "drama", "action", "thriller", "comedy", "western", "romance", "crime"]):
        return "Cinema"
    else:
        # Intrattenimento raccoglie tutto il resto (Kids, Music, Lifestyle, Food, Reality, ecc.)
        return "Intrattenimento"

session = requests.Session()
session.headers.update(HEADERS)

print("Scaricamento database Samsung TV Plus...")

r = session.get(SOURCE, timeout=60)
r.raise_for_status()

database = json.loads(gzip.decompress(r.content).decode("utf-8"))

channels = database["regions"]["it"]["channels"]

channels = [
    {**value, "id": channel_id}
    for channel_id, value in channels.items()
]

channels.sort(key=lambda x: x.get("chno", 9999))

available = []
unavailable = []

print(f"Canali italiani trovati: {len(channels)}")
print()

for index, channel in enumerate(channels, 1):
    channel_id = channel["id"]
    name = channel.get("name", channel_id)

    if channel_id in BLACKLIST:
        unavailable.append(name)
        print(f"{index}/{len(channels)} NO  {name} - Blacklist")
        continue

    if channel.get("license_url"):
        unavailable.append(name)
        print(f"{index}/{len(channels)} NO  {name} - DRM")
        continue

    try:
        response = session.get(
            BASE + channel_id,
            allow_redirects=False,
            timeout=20
        )

        stream_url = response.headers.get("Location")

        if stream_url:
            stream_url = urljoin(BASE + channel_id, stream_url)

        if not stream_url:
            raise Exception("Redirect senza URL")

        host = urlparse(stream_url).hostname or ""

        if "pluto.tv" in host:
            unavailable.append(name)
            print(f"{index}/{len(channels)} NO  {name} - Pluto TV")
            continue

        if response.status_code not in (301, 302, 303, 307, 308):
            raise Exception(f"HTTP {response.status_code}")

        logo = channel.get("logo", "")
        if logo:
            logo = "https://wsrv.nl/?url=" + logo + "&w=300&h=300"

        # Determinazione del group-title (categoria)
        raw_genre = channel.get("genre") or channel.get("category") or name
        group_title = map_category(raw_genre)

        available.append({
            "id": channel_id,
            "name": name,
            "lcn": channel.get("chno", ""),
            "logo": logo,
            "group": group_title,
            "url": stream_url
        })

        print(f"{index}/{len(channels)} OK  {name} [{group_title}]")

    except Exception as e:
        unavailable.append(name)
        print(f"{index}/{len(channels)} ERRORE {name}: {e}")

    time.sleep(0.1)

if not available:
    raise RuntimeError("Nessuno stream Samsung disponibile")

# Assicurati che la cartella di destinazione esista
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")

    for channel in available:
        title = channel["name"].replace('"', "'")

        f.write(
            f'#EXTINF:-1 tvg-id="{channel["id"]}" '
            f'tvg-name="{title}" '
            f'tvg-logo="{channel["logo"]}" '
            f'tvg-chno="{channel["lcn"]}" '
            f'group-title="{channel["group"]}",{title}\n'
        )
        f.write(channel["url"] + "\n")

print()
print("COMPLETATO")
print(f"Canali disponibili: {len(available)}")
print(f"Canali non disponibili: {len(unavailable)}")
print(f"Playlist creata: {OUTPUT}")