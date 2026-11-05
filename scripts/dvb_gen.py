
import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TEMP = ROOT / "temp"
OUTPUT = ROOT / "output"

MASTER_URL = "https://raw.githubusercontent.com/Free-TV/IPTV/refs/heads/master/playlists/playlist_italy.m3u8"

MASTER_FILE = TEMP / "playlist_italy.m3u8"
LOGOS_FILE = DATA / "loghi.json"
PLAYLIST_FILE = OUTPUT / "DVB@it.m3u"

EPG_IDS = {
    "Rai1.it",
    "Rai2.it",
    "Rai3.it",
    "Rete.4.it",
    "Canale.5.it",
    "Italia.1.it",
    "LA7.HD.it",
    "TV8.HD.it",
    "Nove.it",
    "20.it",
    "Rai4.it",
    "Iris.it",
    "Rai5.it",
    "RaiMovie.it",
    "RaiPremium.it",
    "cielo.it",
    "27.Twentyseven.it",
    "La.5.it",
    "Real.Time.it",
    "QVC.it",
    "Food.Network.it",
    "Cine34.it",
    "Focus.it",
    "RTL.102.5.HD.it",
    "Discovery.Channel.it",
    "Giallo.TV.it",
    "Top.Crime.it",
    "Boing.it",
    "RaiGulp.it",
    "RaiYoyo.it",
    "Cartoonito.it",
    "Super!.it",
    "RaiNews24.it",
    "Italia.2.it",
    "Sky.TG24.it",
    "TGCom.it",
    "DMAX.it",
    "RaiStoria.it",
    "Mediaset.Extra.it",
    "HGTV.it",
    "RaiScuola.it",
    "RaiSport.it",
    "Motor.Trend.it"
}

CHANNEL_ORDER = [
    "Rai1.it",
    "Rai2.it",
    "Rai3.it",
    "Rete.4.it",
    "Canale.5.it",
    "Italia.1.it",
    "LA7.HD.it",
    "TV8.HD.it",
    "Nove.it",
    "20.it",
    "Rai4.it",
    "Iris.it",
    "Rai5.it",
    "RaiMovie.it",
    "RaiPremium.it",
    "cielo.it",
    "27.Twentyseven.it",
    "TV2000.va",
    "LA7.Cinema.it",
    "La.5.it",
    "Real.Time.it",
    "QVC.it",
    "Food.Network.it",
    "Cine34.it",
    "Focus.it",
    "RTL.102.5.HD.it",
    "Discovery.Channel.it",
    "Giallo.TV.it",
    "Top.Crime.it",
    "Boing.it",
    "RaiGulp.it",
    "RaiYoyo.it",
    "Cartoonito.it",
    "Super!.it",
    "RaiNews24.it",
    "Italia.2.it",
    "Sky.TG24.it",
    "TGCom.it",
    "DMAX.it",
    "RaiStoria.it",
    "Mediaset.Extra.it",
    "HGTV.it",
    "RaiScuola.it",
    "RaiSport.it",
    "Motor.Trend.it",
    "Sportitalia.it",
    "TravelTV.it",
    "DonnaTV.it",
    "SuperTennis.it",
    "AlmaTV.it",
    "Radio105TV.it",
    "R101TV.it",
    "DeejayTV.it",
    "RadioItaliaTV.it",
    "KissKissTV.it",
    "RaiRadio2Visual.it",
    "RTL1025Traffic.it",
    "Manga.it",
    "Radio24TV.it",
    "BeJoyKids.it",
    "GamberoRosso.it",
    "RadioFrecciaTV.it",
    "RDSSocialTV.it",
    "RadioZetaTV.it",
    "RadioTVSerieA.it"
]

CATEGORIES = {
    "RAI": {
        "Rai1.it", "Rai2.it", "Rai3.it", "Rai4.it", "Rai5.it",
        "RaiMovie.it", "RaiPremium.it", "RaiGulp.it", "RaiYoyo.it",
        "RaiNews24.it", "RaiStoria.it", "RaiScuola.it",
        "RaiSport.it", "RaiRadio2Visual.it"
    },
    "Mediaset": {
        "Rete.4.it", "Canale.5.it", "Italia.1.it", "20.it",
        "Iris.it", "27.Twentyseven.it", "La.5.it", "Cine34.it",
        "Focus.it", "Top.Crime.it", "Boing.it", "Cartoonito.it",
        "Italia.2.it", "TGCom.it", "Mediaset.Extra.it",
        "Radio105TV.it", "R101TV.it"
    },
    "Warner Bros. Discovery": {
        "Nove.it", "Real.Time.it", "Food.Network.it",
        "Discovery.Channel.it", "Giallo.TV.it", "DMAX.it",
        "HGTV.it", "Motor.Trend.it"
    },
    "Sky": {
        "TV8.HD.it", "cielo.it", "Sky.TG24.it"
    },
    "La7": {
        "LA7.HD.it", "LA7.Cinema.it"
    }
}

def download_master():
    response = requests.get(MASTER_URL, timeout=60)
    response.raise_for_status()
    MASTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    MASTER_FILE.write_bytes(response.content)
    return response.text

def parse_master(content):
    channels = {}
    lines = content.splitlines()

    for index, line in enumerate(lines):
        if not line.startswith("#EXTINF:"):
            continue

        match = re.search(r'tvg-id="([^"]+)"', line)

        if not match:
            continue

        tvg_id = match.group(1)
        stream = None

        for next_line in lines[index + 1:]:
            value = next_line.strip()

            if value and not value.startswith("#"):
                stream = value
                break

        if not stream:
            continue

        channels.setdefault(tvg_id, []).append({
            "info": line,
            "url": stream,
            "is_g": "Ⓖ" in line
        })

    return channels

def set_attribute(info, name, value):
    pattern = rf'\s+{re.escape(name)}="[^"]*"'
    info = re.sub(pattern, "", info)

    if value:
        info = info.replace(
            "#EXTINF:-1",
            f'#EXTINF:-1 {name}="{value}"',
            1
        )

    return info

def get_category(tvg_id):
    for category, ids in CATEGORIES.items():
        if tvg_id in ids:
            return category

    return "Altri"

def main():
    DATA.mkdir(exist_ok=True)
    TEMP.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)

    unexpected = [path.name for path in DATA.iterdir() if path.name != "loghi.json"]
    if unexpected:
        raise RuntimeError(f"La cartella data deve contenere solo loghi.json: {unexpected}")

    if not LOGOS_FILE.exists():
        raise FileNotFoundError(LOGOS_FILE)

    print("Scaricamento playlist master...")
    master_content = download_master()

    with open(LOGOS_FILE, encoding="utf-8") as file:
        logos = json.load(file)

    if not isinstance(logos, dict):
        raise ValueError("loghi.json deve contenere un oggetto JSON")

    master_channels = parse_master(master_content)
    if not master_channels:
        raise RuntimeError("La playlist master DVB non contiene canali validi")

    result = []
    missing = []
    counts = {}

    for tvg_id in CHANNEL_ORDER:
        if tvg_id not in EPG_IDS:
            continue

        variants = master_channels.get(tvg_id)

        if not variants:
            missing.append(tvg_id)
            continue

        standard = [channel for channel in variants if not channel["is_g"]]
        selected = standard[0] if standard else variants[0]

        info = selected["info"]

        logo = logos.get(tvg_id)
        if logo:
            info = set_attribute(info, "tvg-logo", logo)

        category = get_category(tvg_id)
        info = set_attribute(info, "group-title", category)

        result.extend([info, selected["url"]])
        counts[category] = counts.get(category, 0) + 1

    channel_count = len(result) // 2
    if channel_count < 30:
        raise RuntimeError(f"Playlist DVB incompleta: solo {channel_count} canali")

    temporary = TEMP / "DVB@it.m3u.tmp"
    with open(temporary, "w", encoding="utf-8") as file:
        file.write("#EXTM3U\n")
        file.write("\n".join(result))
        file.write("\n")
    temporary.replace(PLAYLIST_FILE)

    print()
    print("Canali creati:", len(result) // 2)
    print("Loghi personalizzati:", sum(1 for tvg_id in CHANNEL_ORDER if tvg_id in EPG_IDS and tvg_id in logos and tvg_id in master_channels))
    print("Categorie:")

    for category, count in counts.items():
        print(f"  {category}: {count}")

    if missing:
        print("ID presenti nell'array ma assenti dal master:")
        for tvg_id in missing:
            print(" ", tvg_id)

    print("Playlist:", PLAYLIST_FILE)

if __name__ == "__main__":
    main()
