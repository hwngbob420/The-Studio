"""Rule-of-thirds UI SAFE-ZONE contract (pure Python, shared by contact_sheet_gen.py and master_compositor.py).
A shot declares  subject_zone: left_third|center|right_third   and   ui_safe_zone: right_third|top_left|none.
The compiler lens-shifts the subject into subject_zone; this module places every callout INSIDE ui_safe_zone (no x,y in the
shotlist) and verifies that no callout box ever touches an actor's face circle (from <shot>.meta.json)."""
import json
from pathlib import Path

W, H = 1920, 1080
ZONES = {"right_third": (1300, 100, 1870, 940), "top_left": (70, 60, 1010, 340), "none": None}
LOWER = (96, 760, 900, 930)          # lower-third name strap (bottom-left), x0,y0,x1,y1


def kinetic_size(c, zone_w=None):
    """Font size that fits the text inside the UI zone width (no clipping at the frame edge)."""
    zw = zone_w or (ZONES["right_third"][2] - ZONES["right_third"][0] - 20)
    return int(min(c.get("size", 150), zw / (len(c["text"]) * 0.84)))


def size_of(c):
    t = c.get("type")
    if t == "card":
        return (c.get("w", 640) + 20, 150 + 70 * max(1, len(c.get("text", "")) // 12 + 1) + (50 if c.get("sub") else 0))
    if t == "icon":
        return (160, 160)
    if t == "stat":
        return (560, 330)
    if t == "bars":
        return (c.get("w", 640) + 40, 120 + 70 * len(c.get("data", [])))
    if t == "kinetic":
        s = kinetic_size(c)
        return (int(len(c["text"]) * s * 0.84), int(s * 1.35))
    if t == "lower":
        return (LOWER[2] - LOWER[0], LOWER[3] - LOWER[1])
    return (400, 200)


def layout(shot):
    """-> [{**callout, x, y, w, h, box:(x0,y0,x1,y1)}] placed inside the shot's ui_safe_zone, stacked when they overlap in time."""
    zone = ZONES.get(shot.get("ui_safe_zone", "none"))
    placed = []
    for c in sorted(shot.get("callouts", []), key=lambda c: c["t"]):
        w, h = size_of(c)
        if c["type"] == "lower":
            box = LOWER
        else:
            if zone is None:
                raise ValueError(f"shot {shot['id']}: callout '{c['type']}' but ui_safe_zone is 'none'")
            x0, y0, x1, y1 = zone
            x, y = x0, y0
            # stack below any time-overlapping callout already placed in this zone
            for p in placed:
                if p["type"] == "lower":
                    continue
                if p["t"] < c["t"] + c.get("dur", 3) and c["t"] < p["t"] + p.get("dur", 3):
                    y = max(y, p["box"][3] + 24) if abs(p["box"][0] - x) < w else y
            # icons hug the right edge of the zone
            if c["type"] == "icon":
                x = x1 - w
            if c["type"] in ("card", "stat", "bars") and (x1 - x0) > w:
                x = x0 + ((x1 - x0) - w) // 2
            if c["type"] == "kinetic":
                c = {**c, "size": kinetic_size(c, x1 - x0 - 10)}
                w, h = size_of(c)
            box = (x, y, x + w, y + h)
            if box[3] > y1 + 40:
                raise ValueError(f"shot {shot['id']}: callouts overflow ui_safe_zone '{shot['ui_safe_zone']}'")
        placed.append({**c, "x": box[0], "y": box[1], "w": box[2] - box[0], "h": box[3] - box[1], "box": box})
    return placed


def overlaps(box, face):
    """Rect vs circle (face = [t,cx,cy,r])."""
    x0, y0, x1, y1 = box
    _, cx, cy, r = face
    nx, ny = min(max(cx, x0), x1), min(max(cy, y0), y1)
    return (nx - cx) ** 2 + (ny - cy) ** 2 < (r * 1.0) ** 2


def check_shot(shot, meta):
    """-> list of human-readable violations (empty = pass)."""
    issues = []
    try:
        placed = layout(shot)
    except ValueError as e:
        return [str(e)]
    for c in placed:
        t0, t1 = c["t"], c["t"] + c.get("dur", 3)
        for actor, faces in meta["faces"].items():
            for f in faces:
                if t0 - 0.5 <= f[0] <= t1 + 0.5 and overlaps(c["box"], f):
                    issues.append(f"{shot['id']}: {c['type']} '{c.get('text', c.get('icon', ''))}' overlaps {actor}'s face at t={f[0]}")
                    break
    zone = shot.get("subject_zone", "center")
    for actor, faces in meta["faces"].items():
        for f in faces:
            if shot.get("ui_safe_zone") == "right_third" and f[1] > ZONES["right_third"][0] - 20 and any(
                    c["type"] != "lower" for c in placed):
                issues.append(f"{shot['id']}: {actor}'s face is inside the right-third UI zone at t={f[0]} (subject_zone={zone})")
                break
    return issues


def load_meta(ep_dir, shot_id):
    return json.loads((Path(ep_dir) / "shots" / f"{shot_id}.meta.json").read_text())
