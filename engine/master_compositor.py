"""Master compositor: Blender frames + GSAP motion callouts + broadcast subtitles + voice/SFX/BGM -> final 1080p60 MP4.
0 API tokens (FFmpeg + headless Chrome only).
Usage: python master_compositor.py <episode_dir> [--out output_final.mp4] [--no-overlay]
Shotlist extras it understands:
  shot.callouts : [{"t":1.2,"dur":2.6,"type":"card|icon|stat|bars|kinetic|lower","text":"..",...}]  (t relative to shot)
  cast[].lines  : [{"wav":"audio/x.wav","t":0.3,"text":"subtitle text"}]
  episode.audio : {"bgm":"auto"|"file.mp3"|null,"bgm_db":-24,"voice_db":0,"sfx_db":-12}"""
import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
FPS = 60


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        raise RuntimeError("cmd failed: " + " ".join(map(str, cmd[:6])) + "\n" + r.stderr[-1500:])
    return r


def wav_dur(p):
    with wave.open(str(p), "rb") as w:
        return w.getnframes() / w.getframerate()


def has_encoder(name):
    return name in run(["ffmpeg", "-hide_banner", "-encoders"]).stdout


def vcodec(quality):
    if has_encoder("h264_nvenc"):
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", str(quality), "-b:v", "0", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(quality - 2), "-pix_fmt", "yuv420p"]


def ass_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_ass(events, path):
    hdr = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n\n[V4+ Styles]\n"
           "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,"
           "StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
           "Style: Sub,Arial Rounded MT Bold,58,&H00FFFFFF,&H000000FF,&H00261B1B,&H99000000,-1,0,0,0,100,100,0,0,1,6,3,2,160,160,70,1\n\n"
           "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    lines = [f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Sub,,0,0,0,,{{\\fad(90,90)}}{t}" for s, e, t in events]
    Path(path).write_text(hdr + "\n".join(lines) + "\n", encoding="utf-8")


def synth_audio(cache, total):
    """Procedural BGM pad + callout 'pop' SFX, generated with FFmpeg (no downloads, royalty-free by construction)."""
    bgm = cache / "bgm_auto.wav"
    if not bgm.exists():
        chords = [(220.0, 277.18, 329.63), (174.61, 220.0, 261.63), (196.0, 246.94, 293.66), (164.81, 207.65, 246.94)]
        seg = 4.0
        n = int(total // seg) + 2
        parts = []
        for i in range(n):
            f = chords[i % 4]
            expr = "+".join(f"0.18*sin(2*PI*{x}*t)+0.07*sin(2*PI*{x * 2}*t)" for x in f)
            out = cache / f"_pad{i % 4}.wav"
            if not out.exists():
                run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                     f"aevalsrc='({expr})*(0.55+0.45*sin(2*PI*0.25*t))':s=44100:d={seg}", "-af",
                     f"lowpass=f=1800,afade=t=in:d=0.6,afade=t=out:st={seg - 0.8}:d=0.8", str(out)])
            parts.append(out)
        lst = cache / "_pads.txt"
        lst.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts))
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-t", str(total + 1), str(bgm)])
    pop = cache / "pop.wav"
    if not pop.exists():
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
             "aevalsrc='0.8*sin(2*PI*(520+1800*t)*t)*exp(-14*t)':s=44100:d=0.22", str(pop)])
    return bgm, pop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_dir")
    ap.add_argument("--out", default="output_final.mp4")
    ap.add_argument("--no-overlay", action="store_true")
    ap.add_argument("--quality", type=int, default=19)
    a = ap.parse_args()
    ep_dir = Path(a.episode_dir).resolve()
    ep = json.loads((ep_dir / "episode_shotlist.json").read_text(encoding="utf-8"))
    cache = ep_dir / "cache"
    cache.mkdir(exist_ok=True)

    # 1. frames -> per-shot clips, then lossless concat
    clips, t_shot, starts = [], 0.0, {}
    for s in ep["shots"]:
        fdir = ep_dir / "render" / s["id"]
        clip = cache / f"{s['id']}.mp4"
        if not clip.exists():
            run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(fdir / "f_%04d.png"),
                 *vcodec(a.quality - 3), "-r", str(FPS), str(clip)])
        clips.append(clip)
        starts[s["id"]] = t_shot
        t_shot += int(round(s["dur"] * FPS)) / FPS
    total = t_shot
    lst = cache / "shots.txt"
    lst.write_text("\n".join(f"file '{c.as_posix()}'" for c in clips))
    base = cache / "base.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(base)])

    # 2. collect callouts, subtitles, voice
    callouts, subs, voices = [], [], []
    k = 0
    for s in ep["shots"]:
        try:
            import ui_layout
            cs = ui_layout.layout(s) if "ui_safe_zone" in s else s.get("callouts", [])   # V2 contract; V1 shotlists keep x,y
        except ValueError as exc:
            raise SystemExit(f"UI contract error: {exc}")
        for c in cs:
            k += 1
            c = {kk: vv for kk, vv in c.items() if kk not in ("box", "w", "h")} if "ui_safe_zone" in s else c
            callouts.append({**c, "id": f"c{k:02d}", "abs": starts[s["id"]] + c["t"]})
        for cast in s["cast"]:
            for ln in cast.get("lines") or ([{"wav": cast["line"]}] if cast.get("line") else []):
                if isinstance(ln, str):
                    ln = {"wav": ln}
                wav = ep_dir / ln["wav"]
                t0 = starts[s["id"]] + ln.get("t", 0.0)
                voices.append((wav, t0))
                if ln.get("text") and s.get("subs", True):
                    subs.append((t0, t0 + wav_dur(wav) + 0.15, ln["text"]))

    # 3. overlay frames (HTML5 + GSAP in headless Chrome)
    ov_dir = ep_dir / "overlay"
    if callouts and not a.no_overlay:
        spec = cache / "callouts.json"
        spec.write_text(json.dumps([{k_: v for k_, v in c.items() if k_ != "abs"} for c in callouts]))
        todo = [c for c in callouts if not (ov_dir / c["id"] / f"f_{int(round(c.get('dur', 3) * FPS)):05d}.png").exists()]
        if todo:
            spec.write_text(json.dumps([{k_: v for k_, v in c.items() if k_ != "abs"} for c in todo]))
            r = subprocess.run(["node", str(ROOT / "engine" / "motion_render.js"), str(spec), str(ov_dir), str(FPS)],
                               capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError("motion_render failed:\n" + r.stderr[-1200:])

    # 4. audio
    audio_cfg = ep.get("audio", {"bgm": "auto"})
    bgm, pop = synth_audio(cache, total)
    ain, afilt, labels = [], [], []
    idx = 1  # input 0 is video
    inputs = ["-i", str(base)]
    for wav, t0 in voices:
        inputs += ["-i", str(wav)]
        ms = int(t0 * 1000)
        afilt.append(f"[{idx}:a]adelay={ms}|{ms},volume={audio_cfg.get('voice_db', 0)}dB[a{idx}]")
        labels.append(f"[a{idx}]")
        idx += 1
    if audio_cfg.get("bgm", "auto"):
        src = bgm if audio_cfg.get("bgm", "auto") == "auto" else ep_dir / audio_cfg["bgm"]
        inputs += ["-i", str(src)]
        afilt.append(f"[{idx}:a]atrim=0:{total},volume={audio_cfg.get('bgm_db', -22)}dB,afade=t=in:d=1,afade=t=out:st={max(total - 1.5, 0)}:d=1.5[a{idx}]")
        labels.append(f"[a{idx}]")
        idx += 1
    for c in callouts:
        inputs += ["-i", str(pop)]
        ms = int(c["abs"] * 1000)
        afilt.append(f"[{idx}:a]adelay={ms}|{ms},volume={audio_cfg.get('sfx_db', -10)}dB[a{idx}]")
        labels.append(f"[a{idx}]")
        idx += 1
    afilt.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0,alimiter=limit=0.95[aout]")

    # 5. video graph: overlays + subtitles
    vfilt, cur = [], "[0:v]"
    ov_inputs = []
    for i, c in enumerate(callouts):
        if a.no_overlay:
            break
        inputs += ["-framerate", str(FPS), "-i", str(ov_dir / c["id"] / "f_%05d.png")]
        ov_inputs.append((idx, c))
        idx += 1
    for n, (ii, c) in enumerate(ov_inputs):
        nxt = f"[v{n}]"
        vfilt.append(f"[{ii}:v]format=rgba,setpts=PTS+{c['abs']:.3f}/TB[o{n}]")
        vfilt.append(f"{cur}[o{n}]overlay=eof_action=pass:format=auto{nxt}")
        cur = nxt
    if subs:
        ass = ep_dir / "subs.ass"
        write_ass(subs, ass)
        vfilt.append(f"{cur}ass=subs.ass[vout]")
    else:
        vfilt.append(f"{cur}null[vout]")
    out = ep_dir / a.out
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(vfilt + afilt),
           "-map", "[vout]", "-map", "[aout]", *vcodec(a.quality), "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
           "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)]
    run(cmd, cwd=str(ep_dir))
    print(f"[master_compositor] {out}  ({total:.1f}s, {len(callouts)} callouts, {len(subs)} subtitles, {len(voices)} voice lines)")


if __name__ == "__main__":
    main()
