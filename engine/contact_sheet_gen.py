"""ONE contact_sheet.jpg the director reads instead of watching video (token-minimal Self-Review Gate).
V2: also draws translucent UI boxes (callouts, placed inside ui_safe_zone) + face circles on every still, and FAILS (exit 2)
when any callout would touch a face - so overlaps are fixed in JSON before a single frame is rendered.
Usage: python contact_sheet_gen.py <episode_dir> [--cols 3] [--pct 50]"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from studio_paths import run_blender  # noqa: E402
import ui_layout  # noqa: E402

WORKER = Path(__file__).resolve().parent / "render_worker.py"


def check_time(shot):
    cs = shot.get("callouts", [])
    t = cs[0]["t"] + 1.0 if cs else shot["dur"] * 0.5
    return min(max(t, 0.1), shot["dur"] - 0.1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_dir")
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--pct", type=int, default=50)
    a = ap.parse_args()
    ep_dir = Path(a.episode_dir).resolve()
    ep = json.loads((ep_dir / "episode_shotlist.json").read_text(encoding="utf-8"))
    shots = ep["shots"]
    stills = ep_dir / "cache" / "stills"
    specs = [f"{ep_dir / 'shots' / (s['id'] + '.blend')}@{check_time(s) / s['dur']:.4f}" for s in shots]
    run_blender(WORKER, ["still", stills, a.pct, *specs])
    k = a.pct / 100.0
    issues = []
    inputs, filters = [], []
    for i, s in enumerate(shots):
        meta = ui_layout.load_meta(ep_dir, s["id"])
        issues += ui_layout.check_shot(s, meta)
        inputs += ["-i", str(stills / f"{s['id']}.png")]
        t = check_time(s)
        chain = f"[{i}:v]"
        parts = []
        try:
            for c in ui_layout.layout(s):
                x0, y0, x1, y1 = c["box"]
                parts.append(f"drawbox=x={int(x0 * k)}:y={int(y0 * k)}:w={int((x1 - x0) * k)}:h={int((y1 - y0) * k)}:color=orange@0.35:t=fill")
                parts.append(f"drawbox=x={int(x0 * k)}:y={int(y0 * k)}:w={int((x1 - x0) * k)}:h={int((y1 - y0) * k)}:color=orange@0.95:t=3")
        except ValueError:
            pass
        for actor, faces in meta["faces"].items():
            f = min(faces, key=lambda r: abs(r[0] - t))
            _, cx, cy, r = f
            parts.append(f"drawbox=x={int((cx - r) * k)}:y={int((cy - r) * k)}:w={int(2 * r * k)}:h={int(2 * r * k)}:color=lime@0.9:t=2")
        parts.append(f"drawtext=text='{s['id']} {s.get('subject_zone', 'center')}/{s.get('ui_safe_zone', 'none')}':x=8:y=8:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.6")
        filters.append(chain + ",".join(parts) + f"[v{i}]")
    n = len(shots)
    layout = "|".join(f"{'+'.join(['w0'] * (i % a.cols)) or '0'}_{'+'.join(['h0'] * (i // a.cols)) or '0'}" for i in range(n))
    fc = ";".join(filters) + ";" + "".join(f"[v{i}]" for i in range(n)) + (f"xstack=inputs={n}:layout={layout}:fill=black[o]" if n > 1 else "null[o]")
    out = ep_dir / "contact_sheet.jpg"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc, "-map", "[o]", "-q:v", "3", str(out)],
                       capture_output=True, text=True)
    if r.returncode:   # drawtext may lack a font: retry without labels
        fc2 = fc.replace(",drawtext", ",null#drawtext")
        import re
        fc2 = re.sub(r",drawtext=[^\[;]*", "", fc)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc2, "-map", "[o]", "-q:v", "3", str(out)], check=True)
    print("[contact_sheet]", out)
    if issues:
        print("UI-SAFE-ZONE VIOLATIONS (fix the shotlist before rendering):")
        for i in issues:
            print("  -", i)
        sys.exit(2)
    print("[contact_sheet] UI safe-zone check: PASS")


if __name__ == "__main__":
    main()
