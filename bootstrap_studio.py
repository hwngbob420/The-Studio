"""THE STUDIO V2 bootstrap: one command prepares a fresh machine.   python bootstrap_studio.py [--doctor]
Downloads (all CC0 unless noted, no logins): Quaternius characters via Poly Pizza, KayKit city/furniture/nature packs (GitHub),
Poly Haven props + HDRIs, AmbientCG PBR textures, Rhubarb lip-sync, GSAP + playwright-core.
Then builds: actors (actor_variants.json) -> asset_vault/actors, sets (presets/sets/*.json) -> asset_vault/sets,
the body-language library -> asset_vault/actions/library_q.blend, and vault_config/catalog_manifest.json."""
import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "engine"))
from studio_paths import find_blender, run_blender  # noqa: E402

DL = ROOT / "asset_vault" / "_downloads"
RHUBARB = {"win32": "Windows", "linux": "Linux", "darwin": "macOS"}
ACCESSORY_MODELS = ["54cOZNS04L", "j3xPyO1mvt", "p5QgQxkMBE"]   # mug, glasses x2 (Poly Pizza, CC0)
HDRIS = ["kloofendal_48d_partly_cloudy_puresky", "belfast_sunset_puresky", "cobblestone_street_night", "clarens_midday"]
PBR = ["Grass004", "Asphalt031", "WoodFloor041", "PavingStones070", "PaintedPlaster017", "Concrete034"]


def check():
    print("== toolchain ==")
    print("blender:", find_blender())
    for tool in ("ffmpeg", "node", "git"):
        print(f"{tool}:", shutil.which(tool) or "MISSING")
    try:
        print("gpu:", subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip())
    except Exception:
        print("gpu: nvidia-smi not found (EEVEE uses whatever GPU Blender finds)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doctor", action="store_true")
    a = ap.parse_args()
    check()
    if a.doctor:
        return
    import fetch_ambientcg as ac
    import fetch_kaykit as kk
    import fetch_polypizza as pp
    var = json.loads((ROOT / "vault_config/presets/actor_variants.json").read_text(encoding="utf-8"))
    print("== characters (Quaternius CC0 via Poly Pizza) ==")
    for b in var["bases"].values():
        pp.fetch(b["poly_pizza"])
    for m in ACCESSORY_MODELS:
        pp.fetch(m)
    print("== KayKit packs ==")
    for k in kk.PACKS:
        kk.fetch_pack(k)
    print("== AmbientCG PBR + Poly Haven HDRI ==")
    for t in PBR:
        ac.pbr(t)
    for h in HDRIS:
        ac.hdri(h)
    print("== Rhubarb ==")
    plat = RHUBARB.get(sys.platform, "Linux")
    import urllib.request
    rz = DL / "rhubarb.zip"
    DL.mkdir(parents=True, exist_ok=True)
    if not rz.exists():
        urllib.request.urlretrieve(f"https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.14.0/Rhubarb-Lip-Sync-1.14.0-{plat}.zip", rz)
    if not list((ROOT / "tools" / "rhubarb").glob("**/rhubarb*")):
        zipfile.ZipFile(rz).extractall(ROOT / "tools" / "rhubarb")
    nd = ROOT / "tools" / "node"
    nd.mkdir(parents=True, exist_ok=True)
    (nd / "package.json").write_text('{"name":"studio-tools","private":true}')
    subprocess.run(["npm", "i", "gsap@3.12.5", "playwright-core@1.49.0", "--no-audit", "--no-fund"], cwd=nd, check=False, shell=(sys.platform == "win32"))
    print("== build vault ==")
    for v in var["variants"]:
        run_blender(ROOT / "engine/ingest_actor.py", [v["id"]])
    for rec in sorted((ROOT / "vault_config/presets/sets").glob("*.json")):
        run_blender(ROOT / "engine/build_set_v2.py", [rec])
    first = ROOT / "asset_vault/actors" / f"{var['variants'][0]['id']}.blend"
    run_blender(ROOT / "engine/actions_q.py", [first, ROOT / "asset_vault/actions/library_q.blend"])
    (ROOT / "asset_vault" / "mixamo_inbox").mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-I", str(ROOT / "engine/catalog_gen.py")], check=True)
    print("THE STUDIO V2 is ready. Try: python engine/produce.py productions/showcase_v2")


if __name__ == "__main__":
    main()
