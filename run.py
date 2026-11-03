from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
EPG = ROOT / "epg"
SCRIPTS_DIR = ROOT / "scripts"

OUTPUT.mkdir(parents=True, exist_ok=True)
EPG.mkdir(parents=True, exist_ok=True)

SCRIPTS = sorted(SCRIPTS_DIR.glob("*.py"))

for script in SCRIPTS:
    print(f"\n{'=' * 50}\nESEGUO: {script.name}\n{'=' * 50}", flush=True)

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT
    )

    if result.returncode != 0:
        print(f"\nERRORE: {script.name} (codice {result.returncode})")
    else:
        print(f"\nOK: {script.name}")

print("\nESECUZIONE COMPLETATA.")
