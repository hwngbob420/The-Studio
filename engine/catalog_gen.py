"""Generate vault_config/catalog_manifest.json from what really exists (recipes + moods + cameras + actions).
The showrunner reads ONLY this file (~600 tokens) to write a shotlist."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "vault_config" / "presets"


def main():
    actors = {}
    for f in sorted((CFG / "actors").glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        actors[r["id"]] = r["label"]
    sets = {}
    for f in sorted((CFG / "sets").glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        sets[r["id"]] = {"about": r["label"], "anchors": list(r["anchors"]), "moods": r["moods"]}
    src = (ROOT / "engine" / "actions_lib.py").read_text(encoding="utf-8")
    actions = sorted(set(re.findall(r'^    "(\w+)": dict\(loop', src, re.M)) | {"walk"})
    face = (ROOT / "engine" / "face_rig.py").read_text(encoding="utf-8")
    emotes = re.findall(r'^    "(\w+)":\s+\{', face.split("EMOTES = {")[1], re.M)
    cams = json.loads((CFG / "cameras" / "presets.json").read_text())
    cam_notes = {"OTS": "needs over+at actor ids", "CloseUp": "focus=actor, flip=-1 mirrors side",
                 "Wide/Medium/SlowDolly/Handheld/LowHero": "focus=[actors]"}
    man = {"actors": actors, "sets": sets, "actions": actions, "emotes": emotes, "moods": list(json.loads((CFG / "lighting/moods.json").read_text())),
           "cameras": list(cams), "camera_notes": cam_notes, "callouts": ["card", "icon", "stat", "bars", "kinetic", "lower"],
           "voices": ["Zira", "David"], "shot_schema": "see .claude/skills/shotlist-schema.md"}
    out = ROOT / "vault_config" / "catalog_manifest.json"
    out.write_text(json.dumps(man, indent=1), encoding="utf-8")
    print("[catalog] wrote", out)


if __name__ == "__main__":
    main()
