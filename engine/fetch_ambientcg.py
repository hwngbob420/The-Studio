"""Download CC0 PBR textures from AmbientCG (1K JPG) and Poly Haven HDRIs (1k) into asset_vault/_pbr and _hdri.
Usage: python fetch_ambientcg.py Grass004 Asphalt031 ...  |  python fetch_ambientcg.py --hdri <polyhaven_hdri_id>"""
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "TheStudio/2.0"}


def _get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180).read()


def pbr(asset_id):
    """-> dir with <id>_1K-JPG_Color.jpg (+Normal/Roughness)."""
    out = ROOT / "asset_vault" / "_pbr" / asset_id
    if list(out.glob("*Color.jpg")):
        return out
    info = json.loads(_get(f"https://ambientcg.com/api/v2/full_json?id={asset_id}&include=downloadData"))
    dl = info["foundAssets"][0]["downloadFolders"]["default"]["downloadFiletypeCategories"]["zip"]["downloads"]
    url = next(d["fullDownloadPath"] for d in dl if d["attribute"] == "1K-JPG")
    out.mkdir(parents=True, exist_ok=True)
    zipfile.ZipFile(io.BytesIO(_get(url))).extractall(out)
    return out


def color_map(asset_id):
    return next(pbr(asset_id).glob("*Color.jpg"))


def hdri(hdri_id, res="1k"):
    out = ROOT / "asset_vault" / "_hdri" / f"{hdri_id}_{res}.hdr"
    if out.exists():
        return out
    files = json.loads(_get(f"https://api.polyhaven.com/files/{hdri_id}"))
    url = files["hdri"][res]["hdr"]["url"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(_get(url))
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--hdri":
        for h in a[1:]:
            print(hdri(h))
    else:
        for t in a:
            print(pbr(t))
