import requests
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "Pluto@it.m3u"

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

ITALY_IP = "131.114.130.239"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Forwarded-For": ITALY_IP
}

session = requests.Session()
session.headers.update(HEADERS)

print("Connessione a Pluto TV...")

response = session.get(TOKEN_URL, timeout=30)
response.raise_for_status()

token = response.json().get("sessionToken")

if not token:
    raise RuntimeError("Token Pluto TV non ricevuto")

print("Token ricevuto.")
print("Scaricamento catalogo canali...")

response = session.get(
    CHANNELS_URL,
    headers={"Authorization": f"Bearer {token}"},
    timeout=30
)
response.raise_for_status()

channels = response.json().get("data", [])
channels.sort(key=lambda channel: channel.get("number", 99999))

print(f"Canali italiani trovati: {len(channels)}")
print()

available = []
unavailable = []

for index, channel in enumerate(channels, 1):
    name = channel.get("name", channel.get("slug", "Sconosciuto"))
    slug = channel.get("slug", "")
    channel_id = channel.get("id", "")

    if not slug or not channel_id:
        unavailable.append(name)
        print(f"{index}/{len(channels)} NO  {name} - Dati mancanti")
        continue

    images = channel.get("images", [])

    logo = next(
        (
            image.get("url")
            for image in images
            if image.get("type") == "colorLogoPNG"
        ),
        ""
    )

    if not logo:
        unavailable.append(name)
        print(f"{index}/{len(channels)} NO  {name} - Logo assente")
        continue

    number = channel.get("number", 0)

    available.append({
        "id": channel_id,
        "name": name,
        "number": number + 5000,
        "logo": logo,
        "url": (
            "https://app-philipsnovatek.pluto.tv/live-tv/watch/"
            + slug
        )
    })

    print(f"{index}/{len(channels)} OK  {name}")

if not available:
    raise RuntimeError("Nessun canale Pluto TV disponibile")

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")

    for channel in available:
        title = channel["name"].replace('"', "'")

        f.write(
            f'#EXTINF:-1 tvg-id="{channel["id"]}" '
            f'tvg-name="{title}" '
            f'tvg-logo="{channel["logo"]}" '
            f'tvg-chno="{channel["number"]}" '
            f'group-title="Pluto TV",{title}\n'
        )

        f.write(channel["url"] + "\n")

print()
print("COMPLETATO")
print(f"Canali disponibili: {len(available)}")
print(f"Canali non disponibili: {len(unavailable)}")
print(f"Playlist creata: {OUTPUT}")
