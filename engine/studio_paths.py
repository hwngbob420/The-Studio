"""Shared paths + tool discovery. Pure stdlib so it imports inside and outside Blender."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "asset_vault"
CONFIG = ROOT / "vault_config"
TOOLS = ROOT / "tools"
PRODUCTIONS = ROOT / "productions"


def find_blender() -> str:
    env = os.environ.get("BLENDER_EXE")
    if env and Path(env).exists():
        return env
    which = shutil.which("blender")
    if which:
        return which
    cands = []
    bf = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Blender Foundation"
    if bf.exists():
        cands += sorted(bf.glob("Blender */blender.exe"), reverse=True)
    cands += [Path("/Applications/Blender.app/Contents/MacOS/Blender"), Path("/usr/bin/blender")]
    for c in cands:
        if c.exists():
            return str(c)
    raise SystemExit("Blender not found. Install Blender 4.2+ or set BLENDER_EXE.")


def find_rhubarb() -> str:
    exe = "rhubarb.exe" if sys.platform == "win32" else "rhubarb"
    hits = list(TOOLS.glob(f"**/{exe}"))
    if hits:
        return str(hits[0])
    w = shutil.which("rhubarb")
    if w:
        return w
    raise SystemExit("Rhubarb missing. Run: python bootstrap_studio.py")


def run_blender(script, args=(), background=True, extra=()):
    """Run a script inside headless Blender. Args after '--' are read with script_args()."""
    cmd = [find_blender()]
    if background:
        cmd.append("-b")
    cmd += list(extra) + ["--python", str(script), "--", *map(str, args)]
    return subprocess.run(cmd, check=False)


def script_args():
    """Arguments passed after '--' (use inside Blender scripts)."""
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
