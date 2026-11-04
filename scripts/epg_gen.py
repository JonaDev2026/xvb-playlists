import gzip
from pathlib import Path
import requests
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "epg"
OUTPUT.mkdir(parents=True, exist_ok=True)

SOURCES = [
    (
        "Pluto",
        "https://i.mjh.nz/PlutoTV/it.xml.gz",
        "xvb-Pluto.xml",
        True
    ),
    (
        "Samsung TV Plus",
        "https://i.mjh.nz/SamsungTVPlus/it.xml",
        "xvb-SamTv.xml",
        False
    ),
    (
        "EPGShare",
        "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz",
        "xvb-dvb-it.xml",
        True
    )
]

session = requests.Session()
session.headers.update({
    "User-Agent": "XVB-EPG/1.0"
})

for name, url, filename, compressed in SOURCES:
    print(f"\n{name}: scaricamento...", flush=True)

    try:
        response = session.get(url, timeout=180)
        response.raise_for_status()

        data = response.content

        if compressed:
            data = gzip.decompress(data)

        root = ET.fromstring(data)

        if root.tag.split("}")[-1] != "tv":
            raise ValueError("Formato XMLTV non valido")

        destination = OUTPUT / filename
        temporary = OUTPUT / (filename + ".tmp")

        temporary.write_bytes(data)
        temporary.replace(destination)

        print(f"OK: {destination}")
        print(f"Dimensione: {len(data):,} byte")

    except Exception as error:
        print(f"ERRORE {name}: {error}")

print("\nDOWNLOAD EPG TERMINATO")
