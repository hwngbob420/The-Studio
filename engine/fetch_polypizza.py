"""Download a Poly Pizza model GLB by its model id (no login; page exposes the static CDN link).
Usage: python fetch_polypizza.py <model_id> [...]  ->  asset_vault/_polypizza/<id>.glb"""
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "asset_vault" / "_polypizza"
UA = {"User-Agent": "Mozilla/5.0 (TheStudio asset bootstrap)"}


def fetch(model_id):
    out = DEST / f"{model_id}.glb"
    if out.exists():
        return out
    html = urllib.request.urlopen(urllib.request.Request(f"https://poly.pizza/m/{model_id}", headers=UA), timeout=60).read().decode("utf-8", "replace")
    m = re.search(r"https://static\.poly\.pizza/([0-9a-f-]{36})\.glb", html)
    if not m:
        raise RuntimeError(f"no glb link on poly.pizza/m/{model_id}")
    DEST.mkdir(parents=True, exist_ok=True)
    out.write_bytes(urllib.request.urlopen(urllib.request.Request(m.group(0), headers=UA), timeout=120).read())
    return out


if __name__ == "__main__":
    for i in sys.argv[1:]:
        print(fetch(i))
