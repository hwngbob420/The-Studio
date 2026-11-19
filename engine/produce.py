"""One-command episode pipeline.  python engine/produce.py <episode_dir> [--stage all|voice|compile|sheet|render|final]
voice   : synthesize `say` lines (offline SAPI) -> wav (skip if you supply your own wav)
compile : shotlist -> staged .blend per shot (Blender headless)
sheet   : contact_sheet.jpg  <- the ONE image the director reviews
render  : local GPU render (parallel workers, resumable)
final   : callouts + subtitles + audio + FFmpeg master -> output_final.mp4"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from studio_paths import run_blender  # noqa: E402


def voice(ep_dir):
    from lipsync_runner import tts
    p = ep_dir / "episode_shotlist.json"
    ep = json.loads(p.read_text(encoding="utf-8"))
    n = 0
    for s in ep["shots"]:
        for c in s["cast"]:
            for i, ln in enumerate(c.get("lines", [])):
                if "say" in ln:
                    ln.setdefault("wav", f"audio/{s['id']}_{c['actor']}_{i}.wav")
                    ln.setdefault("text", ln["say"])
                    wav = ep_dir / ln["wav"]
                    if not wav.exists():
                        d = tts(ln["say"], wav, ln.get("voice", "Zira"), ln.get("rate", 0))
                        n += 1
                        print(f"[voice] {wav.name} {d:.2f}s")
    p.write_text(json.dumps(ep, indent=1), encoding="utf-8")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_dir")
    ap.add_argument("--stage", default="all")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--shots", nargs="*", default=[])
    a = ap.parse_args()
    ep_dir = Path(a.episode_dir).resolve()
    st = a.stage
    py = sys.executable
    if st in ("all", "voice"):
        voice(ep_dir)
    if st in ("all", "compile"):
        run_blender(HERE / "stage_compiler.py", [ep_dir, *a.shots])
    if st in ("all", "sheet"):
        subprocess.run([py, "-I", str(HERE / "contact_sheet_gen.py"), str(ep_dir)], check=True)
    if st in ("all", "render"):
        subprocess.run([py, "-I", str(HERE / "gpu_renderer.py"), str(ep_dir), *a.shots, "--workers", str(a.workers)], check=True)
    if st in ("all", "final"):
        subprocess.run([py, "-I", str(HERE / "master_compositor.py"), str(ep_dir)], check=True)


if __name__ == "__main__":
    main()
