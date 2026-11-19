"""Download CC0 Poly Haven models (glTF + textures, 1k) into asset_vault/_polyhaven/<id>/. Stdlib only.
Usage: python fetch_polyhaven.py id [id ...]   (or import fetch(ids))"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "asset_vault" / "_polyhaven"
UA = {"User-Agent": "TheStudio/1.0 (asset bootstrap)"}


def _get(url, as_json=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    return json.loads(data) if as_json else data


def fetch(asset_id, res="1k"):
    out = DEST / asset_id
    gltf_path = out / f"{asset_id}_{res}.gltf"
    if gltf_path.exists():
        return gltf_path
    files = _get(f"https://api.polyhaven.com/files/{asset_id}", as_json=True)
    entry = files["gltf"][res]["gltf"]
    out.mkdir(parents=True, exist_ok=True)
    gltf_path.write_bytes(_get(entry["url"]))
    for rel, meta in entry.get("include", {}).items():
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(_get(meta["url"]))
    return gltf_path


if __name__ == "__main__":
    for a in sys.argv[1:]:
        print(fetch(a))
