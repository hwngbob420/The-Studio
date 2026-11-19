"""Voice + lip-sync. 0 API tokens.
  tts(text, wav, voice)        -> offline Windows SAPI voice (placeholder voice; drop in any real .wav instead)
  cues(wav, text=None)         -> Rhubarb mouth cues [(start, end, 'A'..'X')], cached next to the wav as .cues.json
CLI: python lipsync_runner.py say "Hello there" out.wav [Zira|David]   |   python lipsync_runner.py cues in.wav"""
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from studio_paths import find_rhubarb  # noqa: E402


def tts(text, wav_path, voice="Zira", rate=0):
    wav_path = Path(wav_path)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    ps = (
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$v=$s.GetInstalledVoices()|?{{$_.VoiceInfo.Name -like '*{voice}*'}}|select -First 1;"
        "if($v){$s.SelectVoice($v.VoiceInfo.Name)};"
        f"$s.Rate={int(rate)};"
        f"$s.SetOutputToWaveFile('{wav_path}');"
        "$s.Speak([IO.File]::ReadAllText($env:STUDIO_TTS_TEXT));$s.Dispose()"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(text)
        txt = f.name
    import os
    env = dict(os.environ, STUDIO_TTS_TEXT=txt)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, env=env)
    Path(txt).unlink(missing_ok=True)
    return duration(wav_path)


def duration(wav_path):
    with wave.open(str(wav_path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def cues(wav_path, text=None, force=False):
    wav_path = Path(wav_path)
    cache = wav_path.with_suffix(".cues.json")
    if cache.exists() and not force:
        return json.loads(cache.read_text())
    tmp_json = wav_path.with_suffix(".rhubarb.json")
    cmd = [find_rhubarb(), "-f", "json", "--extendedShapes", "GHX", "-o", str(tmp_json), str(wav_path)]
    if text:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(text)
            dlg = f.name
        cmd += ["-d", dlg]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"rhubarb failed: {out.stderr[-400:]}")
    data = json.loads(tmp_json.read_text())["mouthCues"]
    tmp_json.unlink(missing_ok=True)
    res = [(c["start"], c["end"], c["value"]) for c in data]
    cache.write_text(json.dumps(res))
    return res


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "say":
        print(round(tts(a[1], a[2], a[3] if len(a) > 3 else "Zira"), 2), "s")
    elif a[0] == "cues":
        print(cues(a[1])[:8])
