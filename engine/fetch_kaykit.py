"""Download CC0 KayKit packs (stylized buildings, furniture, restaurant props) from the official GitHub repos.
Usage: python fetch_kaykit.py [pack ...]   packs: city_builder furniture restaurant  (default: all)
Files land in asset_vault/_kaykit/<pack>/{gltf,texture}/ ; stdlib only."""
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "asset_vault" / "_kaykit"
PACKS = {
    "city_builder": ("KayKit-City-Builder-Bits-1.0", "kaykit_city_builder_bits"),
    "furniture": ("KayKit-Furniture-Bits-1.0", "kaykit_furniture_bits"),
    "restaurant": ("KayKit-Restaurant-Bits-1.0", "kaykit_restaurant_bits"),
    "nature": ("KayKit-Medieval-Hexagon-Pack-1.0", "kaykit_medieval_hexagon_pack"),   # trees, hills, rocks, clouds
}
ONLY = {"nature": ("gltf/decoration/nature/", "gltf/tiles/base/", "gltf/tiles/", "texture")}
UA = {"User-Agent": "TheStudio/2.0"}


def _get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()


def fetch_pack(key):
    repo, addon = PACKS[key]
    tree = json.loads(_get(f"https://api.github.com/repos/KayKit-Game-Assets/{repo}/git/trees/main?recursive=1"))["tree"]
    base = f"addons/{addon}/Assets/"
    want = [t["path"] for t in tree if t["type"] == "blob" and t["path"].startswith(base)
            and (t["path"][len(base):].startswith(("gltf/", "texture/", "textures/")))
            and (key not in ONLY or any(k in t["path"] for k in ONLY[key]))]
    out = DEST / key

    def dl(p):
        dst = out / p[len(base):]
        if dst.exists():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(_get(f"https://raw.githubusercontent.com/KayKit-Game-Assets/{repo}/main/{p.replace(' ', '%20')}"))

    with ThreadPoolExecutor(8) as ex:
        list(ex.map(dl, want))
    return out


def model(pack, name):
    """Path of a KayKit glTF by pack + base name (e.g. model('city_builder','building_A'))."""
    hits = list((DEST / pack / "gltf").rglob(f"{name}.gltf")) if (DEST / pack / "gltf").exists() else []
    if not hits:
        fetch_pack(pack)
        hits = list((DEST / pack / "gltf").rglob(f"{name}.gltf"))
    if not hits:
        raise FileNotFoundError(f"{pack}/{name}")
    return hits[0]


if __name__ == "__main__":
    for k in (sys.argv[1:] or PACKS):
        print(k, fetch_pack(k))
