import gzip
from pathlib import Path
import requests
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "epg"
TEMP = ROOT / "temp"

SOURCES = [
    ("Pluto", "https://i.mjh.nz/PlutoTV/it.xml.gz", "xvb-Pluto.xml", True),
    ("Samsung TV Plus", "https://i.mjh.nz/SamsungTVPlus/it.xml", "xvb-SamTv.xml", False),
    ("EPGShare", "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz", "xvb-dvb-it.xml", True)
]

def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    TEMP.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "XVB-EPG/1.0"})
    failures = []

    for name, url, filename, compressed in SOURCES:
        print(f"\n{name}: scaricamento...", flush=True)
        temporary = TEMP / (filename + ".tmp")

        try:
            response = session.get(url, timeout=180)
            response.raise_for_status()
            data = gzip.decompress(response.content) if compressed else response.content
            root = ET.fromstring(data)

            if root.tag.split("}")[-1] != "tv":
                raise ValueError("Formato XMLTV non valido")

            channels = root.findall(".//channel")
            programmes = root.findall(".//programme")
            if not channels or not programmes:
                raise ValueError(f"XMLTV incompleto: {len(channels)} canali, {len(programmes)} programmi")

            temporary.write_bytes(data)
            ET.parse(temporary)
            temporary.replace(OUTPUT / filename)

            print(f"OK: {OUTPUT / filename}")
            print(f"Canali: {len(channels)} | Programmi: {len(programmes)} | Byte: {len(data):,}")

        except Exception as error:
            failures.append(f"{name}: {error}")
            temporary.unlink(missing_ok=True)
            print(f"ERRORE {name}: {error}", flush=True)

    if failures:
        raise RuntimeError("Aggiornamento EPG incompleto:\n" + "\n".join(failures))

    print("\nDOWNLOAD EPG TERMINATO")

if __name__ == "__main__":
    main()
