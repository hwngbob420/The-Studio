"""THE STUDIO bootstrap: one command prepares a fresh machine.   python bootstrap_studio.py [--skip-assets] [--doctor]
Installs/downloads (all open-source, CC0 where assets): MPFB2 extension, MakeHuman CC0 asset packs, Rhubarb lip-sync,
node tools (GSAP + playwright-core), Poly Haven props; then builds actors/sets/actions and the catalog manifest."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "engine"))
from studio_paths import find_blender, run_blender  # noqa: E402

MPFB_URL = "https://extensions.blender.org/download/sha256:c075b3e9b94b8e5556a5f03f4653602d02ea306de08126e8f55ed6dee28a2dad/add-on-mpfb-v2.0.18.zip"
MPFB_SHA = "c075b3e9b94b8e5556a5f03f4653602d02ea306de08126e8f55ed6dee28a2dad"
RHUBARB = {"win32": "Windows", "linux": "Linux", "darwin": "macOS"}
PACKS = ["makehuman_system_assets", "shirts01", "pants01", "shoes01", "suits01"]
DL = ROOT / "asset_vault" / "_downloads"


def get(url, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return dst
    print("  downloading", url.split("/")[-1])
    req = urllib.request.Request(url, headers={"User-Agent": "TheStudio/1.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f)
    return dst


def check():
    print("== toolchain ==")
    print("blender:", find_blender())
    for tool in ("ffmpeg", "node", "git"):
        print(f"{tool}:", shutil.which(tool) or "MISSING")
    try:
        print("gpu:", subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip())
    except Exception:
        print("gpu: nvidia-smi not found")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-assets", action="store_true")
    ap.add_argument("--doctor", action="store_true")
    a = ap.parse_args()
    check()
    if a.doctor:
        return
    blender = find_blender()
    # 1 MPFB2
    z = get(MPFB_URL, DL / "mpfb.zip")
    assert hashlib.sha256(z.read_bytes()).hexdigest() == MPFB_SHA, "MPFB checksum mismatch"
    subprocess.run([blender, "-b", "--command", "extension", "install-file", "-r", "user_default", "--enable", str(z)], check=False)
    # 2 MakeHuman CC0 packs -> MPFB user data
    udata = subprocess.run([blender, "-b", "--python-expr",
                            "from bl_ext.user_default.mpfb.services.locationservice import LocationService as L;print('UDATA='+L.get_user_data())"],
                           capture_output=True, text=True).stdout
    udata = Path(next(l for l in udata.splitlines() if l.startswith("UDATA=")).split("=", 1)[1])
    if not (udata / "hair").exists():
        for p in PACKS:
            f = get(f"https://files.makehumancommunity.org/asset_packs/{p}/{p}_cc0.zip", DL / f"{p}.zip")
            zipfile.ZipFile(f).extractall(udata)
    # 3 Rhubarb
    plat = RHUBARB.get(sys.platform, "Linux")
    rz = get(f"https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.14.0/Rhubarb-Lip-Sync-1.14.0-{plat}.zip", DL / "rhubarb.zip")
    if not list((ROOT / "tools" / "rhubarb").glob("**/rhubarb*")):
        zipfile.ZipFile(rz).extractall(ROOT / "tools" / "rhubarb")
    # 4 node tools
    nd = ROOT / "tools" / "node"
    nd.mkdir(parents=True, exist_ok=True)
    (nd / "package.json").write_text('{"name":"studio-tools","private":true}')
    subprocess.run(["npm", "i", "gsap@3.12.5", "playwright-core@1.49.0", "--no-audit", "--no-fund"], cwd=nd, check=False, shell=(sys.platform == "win32"))
    # 5 build vault
    for rec in sorted((ROOT / "vault_config/presets/actors").glob("*.json")):
        run_blender(ROOT / "engine/build_actor.py", [rec])
    for rec in sorted((ROOT / "vault_config/presets/sets").glob("*.json")):
        run_blender(ROOT / "engine/build_set.py", [rec])
    actors = sorted((ROOT / "asset_vault/actors").glob("*.blend"))
    run_blender(ROOT / "engine/actions_lib.py", [actors[0], ROOT / "asset_vault/actions/library.blend"])
    subprocess.run([sys.executable, "-I", str(ROOT / "engine/catalog_gen.py")], check=True)
    print("THE STUDIO is ready. Try: python engine/produce.py productions/showcase_v1")


if __name__ == "__main__":
    main()
