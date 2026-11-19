"""Compile episode_shotlist.json -> one fully staged .blend per shot (set + cast + acting + lipsync + camera + light).
Usage: blender -b --python stage_compiler.py -- <episode_dir> [shot_id ...]
The shotlist is the ONLY thing an AI director has to write (~1k tokens). Everything else is local & free."""
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "vault_config" / "shaders"))
import actions_lib  # noqa: E402
import face_rig  # noqa: E402
import master_toon as toon  # noqa: E402
from studio_paths import script_args  # noqa: E402

VAULT = ROOT / "asset_vault"
CFG = ROOT / "vault_config" / "presets"
FPS = 60
MOODS = json.loads((CFG / "lighting" / "moods.json").read_text())
CAMS = json.loads((CFG / "cameras" / "presets.json").read_text())


def fr(t):
    return int(round(t * FPS)) + 1


# ---------------------------------------------------------------- scene assembly
def load_set(set_id):
    bpy.ops.wm.open_mainfile(filepath=str(VAULT / "sets" / f"{set_id}.blend"))
    scn = bpy.context.scene
    scn.render.fps = FPS
    anchors = {o.name[7:]: o for o in bpy.data.objects if o.name.startswith("ANCHOR_")}
    return scn, anchors


def load_actor(actor_id, col):
    path = VAULT / "actors" / f"{actor_id}.blend"
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.objects = list(src.objects)
    rig = None
    for o in dst.objects:
        if o is None:
            continue
        col.objects.link(o)
        if o.type == "ARMATURE":
            rig = o
    return rig


def load_actions():
    with bpy.data.libraries.load(str(VAULT / "actions" / "library.blend"), link=False) as (src, dst):
        dst.actions = list(src.actions)


def head_height(rig):
    """Eye-line height in rig space (used for look-at, close-ups and OTS framing)."""
    return rig.data.bones["eye.L"].head_local.z


def anchor_pos(spec, anchors, actors):
    if isinstance(spec, str):
        if spec in anchors:
            return anchors[spec].matrix_world.translation.copy()
        if spec in actors:
            return actors[spec].matrix_world.translation.copy()
        raise KeyError(f"unknown anchor/actor '{spec}'")
    return Vector(spec)


def yaw_to(src, dst):
    d = dst - src
    return math.atan2(d.x, -d.y)   # actor forward is -Y


# ---------------------------------------------------------------- body acting (NLA)
def build_nla(rig, segs, dur, travel_speed):
    """segs: [(t_start, action_name)] ; strips alternate over two tracks and cross-fade."""
    ad = rig.animation_data_create()
    tracks = [ad.nla_tracks.new(), ad.nla_tracks.new()]
    fade = 0.25
    for i, (t0, name) in enumerate(segs):
        act = bpy.data.actions[name]
        t1 = segs[i + 1][0] if i + 1 < len(segs) else dur
        start = max(0.0, t0 - (fade if i else 0.0))
        length = act["length"] * FPS
        span = (t1 - start + fade) * FPS if i + 1 < len(segs) else (t1 - start) * FPS
        tr = tracks[i % 2]
        strip = tr.strips.new(f"{name}_{i}", fr(start), act)
        if hasattr(strip, "action_slot") and strip.action_slot is None and getattr(act, "slots", None):
            strip.action_slot = act.slots[0]
        strip.extrapolation = "HOLD" if i == 0 else "HOLD_FORWARD" if not act["loop"] else "NOTHING"
        if act["loop"]:
            strip.repeat = max(1.0, span / length)
        strip.blend_type = "REPLACE"
        if i:
            strip.blend_in = fade * FPS
        if name == "walk" and travel_speed:
            strip.scale = max(0.4, 1.25 / travel_speed)
            strip.repeat = max(1.0, span / (length * strip.scale))
    return ad


# ---------------------------------------------------------------- face: emotes, blinks, lipsync, eyes
def face_timeline(rig, cast, shot, dur, line_cues, seed, cam_obj, others):
    scn = bpy.context.scene
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    ad = rig.animation_data
    act = bpy.data.actions.new(f"{rig.name}_face")
    ad.action = act
    if hasattr(ad, "action_slot") and ad.action_slot is None and getattr(act, "slots", None):
        pass

    emotes = cast.get("emotes") or [[0.0, cast.get("emote", "neutral")]]
    emotes = sorted(emotes, key=lambda e: e[0])
    rnd = random.Random(seed)

    def emote_at(t):
        """-> (name_a, name_b, mix) cross-fading 0.3 s around changes."""
        cur = emotes[0][1]
        prev = cur
        t_ch = -9
        for te, name in emotes:
            if te <= t:
                prev, cur, t_ch = cur, name, te
        k = min(1.0, max(0.0, (t - t_ch) / 0.3))
        return prev, cur, k

    # blink schedule
    blinks = []
    t = rnd.uniform(0.6, 1.8)
    while t < dur:
        blinks.append(t)
        t += rnd.uniform(2.4, 4.8)

    def blink_at(t):
        for b in blinks:
            d = t - b
            if 0 <= d <= 0.16:
                return 1.0 - abs(d - 0.08) / 0.08
        return 0.0

    cue_list = []
    for t0, cues in line_cues:
        for s, e, v in cues:
            cue_list.append((t0 + s, t0 + e, v))
    cue_list.sort()

    def viseme_at(t):
        for s, e, v in cue_list:
            if s <= t < e:
                return v
        return "X"

    # key sampling: every cue boundary + 0.1s grid for emotes/blinks
    times = set(round(x * 0.1, 3) for x in range(int(dur * 10) + 1))
    for s, e, v in cue_list:
        times.add(round(s, 3))
        times.add(round(max(s, e - 0.02), 3))
    for b in blinks:
        times.update([round(b, 3), round(b + 0.08, 3), round(b + 0.16, 3)])
    for te, _ in emotes:
        times.update([round(te, 3), round(te + 0.3, 3)])
    times = sorted(x for x in times if 0 <= x <= dur)

    def apply_at(t):
        pa, pb, k = emote_at(t)
        face_rig.apply_face(rig, pa, viseme_at(t), blink_at(t), emote_k=1 - k, viseme_k=0.9)
        # blend second emote on top (additive on the same controls)
        if pb != pa and k > 0:
            ctrl = face_rig.EMOTES.get(pb, {})
            offs = face_rig.bone_offsets(rig, {c: v * k for c, v in ctrl.items()})
            for nm, v in offs.items():
                rig.pose.bones[nm].location = rig.pose.bones[nm].location + v

    look = cast.get("look", "cam")
    eye_samples = [round(x * 0.25, 3) for x in range(int(dur * 4) + 1)]

    for t in sorted(set(times) | set(eye_samples)):
        scn.frame_set(fr(t))
        apply_at(t)
        face_rig.key_face(rig, fr(t))
        # eyes follow the look target (computed against the evaluated body pose at this frame)
        tgt = None
        if look == "cam":
            tgt = cam_obj.matrix_world.translation.copy()
        elif isinstance(look, list):
            tgt = Vector(look)
        elif look in others:
            tgt = others[look].matrix_world @ Vector((0, 0, head_height(others[look])))
        if tgt is not None:
            for s in ("L", "R"):
                eb = rig.pose.bones[f"eye.{s}"]
                eb.rotation_mode = "XYZ"
                eb.rotation_euler = (0, 0, 0)
                bpy.context.view_layer.update()
                ew = rig.matrix_world @ eb.head
                d_arm = (rig.matrix_world.to_3x3().inverted() @ (tgt - ew))
                cur = (eb.matrix.to_3x3() @ Vector((0, 1, 0))).normalized()
                q = cur.rotation_difference(d_arm.normalized())
                ang = q.angle
                if ang > math.radians(35):   # clamp eye turn
                    q = q.__class__((1, 0, 0, 0)).slerp(q, math.radians(35) / ang)
                m = q.to_matrix().to_4x4() @ eb.matrix
                m.translation = eb.matrix.translation
                eb.matrix = m
                bpy.context.view_layer.update()
        for s in ("L", "R"):
            rig.pose.bones[f"eye.{s}"].keyframe_insert("rotation_euler", frame=fr(t), group="face")
    bpy.ops.object.mode_set(mode="OBJECT")
    # smooth, non-robotic interpolation on face curves; Bezier default stays for body
    for fc in actions_lib.fcurves_of(act):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"


# ---------------------------------------------------------------- camera + light
def world_point(rig, local_z):
    return rig.matrix_world @ Vector((0, 0, local_z))


def make_camera(scn, shot, actors, anchors, dur):
    spec = dict(CAMS[shot["cam"].get("preset", "Medium")])
    spec.update({k: v for k, v in shot["cam"].items() if k != "preset"})
    names = shot["cam"].get("focus") or list(actors)
    names = [names] if isinstance(names, str) else names
    pts = [actors[n].matrix_world.translation.copy() for n in names]
    center = sum(pts, Vector()) / len(pts)
    spread = max([(p - center).length * 2 for p in pts] + [0.8])
    cam = bpy.data.cameras.new("cam")
    cam.lens = spec["lens"]
    cam.sensor_width = 36
    cam.dof.use_dof = True
    cam.dof.aperture_fstop = spec["fstop"]
    co = bpy.data.objects.new("cam", cam)
    scn.collection.objects.link(co)
    scn.camera = co
    tgt = bpy.data.objects.new("CamTarget", None)
    scn.collection.objects.link(tgt)

    kind = spec["kind"]
    if kind == "frame":
        vfov = 2 * math.atan((36 * 9 / 16 / 2) / spec["lens"])
        need_h = max(spec["frame_h"], (spread + 1.2) * 9 / 16)
        dist = max(spec.get("min_dist", 1.5), need_h / 2 / math.tan(vfov / 2))
        az = math.radians(spec["az"])
        look_h = spec["target_h"]
        tgt.location = center + Vector((0, 0, look_h))
        co.location = center + Vector((math.sin(az) * dist, -math.cos(az) * dist, spec["height"]))
    elif kind == "ots":
        a, b = actors[shot["cam"]["over"]], actors[shot["cam"]["at"]]
        pa = a.matrix_world.translation
        pb = b.matrix_world.translation
        fwd = (pb - pa).normalized()
        side = Vector((-fwd.y, fwd.x, 0))
        hz = head_height(a)
        co.location = pa - fwd * spec["back"] + side * spec["side"] * shot["cam"].get("flip", 1) + Vector((0, 0, hz + spec["up"]))
        tgt.location = pb + Vector((0, 0, head_height(b) - 0.03))
    else:  # close
        a = actors[shot["cam"]["focus"] if isinstance(shot["cam"].get("focus"), str) else shot["cam"]["focus"][0]]
        pa = a.matrix_world.translation
        yaw = a.rotation_euler.z
        fwd = Vector((math.sin(yaw), -math.cos(yaw), 0))     # character facing
        side = Vector((-fwd.y, fwd.x, 0))
        hz = head_height(a)
        co.location = pa + fwd * spec["dist"] + side * spec["side"] * shot["cam"].get("flip", 1) + Vector((0, 0, hz + 0.03))
        tgt.location = pa + Vector((0, 0, hz - 0.02))
    # target follows a moving subject when requested (copies the chest bone position, keeps height offset)
    if shot["cam"].get("follow"):
        rig = actors[shot["cam"]["follow"]]
        cl = tgt.constraints.new("COPY_LOCATION")
        cl.target = rig
        cl.subtarget = "spine01"
        cl.use_offset = False
    con = co.constraints.new("TRACK_TO")
    con.target = tgt
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    cam.dof.focus_object = tgt

    # moves
    push = spec.get("push", 0)
    if push:
        f0, f1 = 1, fr(dur)
        v = (tgt.location - co.location).normalized()
        co.keyframe_insert("location", frame=f0)
        co.location = co.location + v * push
        co.keyframe_insert("location", frame=f1)
        co.location = co.location - v * push
        for fc in actions_lib.fcurves_of(co.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    drift = spec.get("drift")
    if drift:  # lateral truck
        f0, f1 = 1, fr(dur)
        side = Vector((1, 0, 0))
        co.keyframe_insert("location", frame=f0)
        co.location = co.location + side * drift
        co.keyframe_insert("location", frame=f1)
        co.location = co.location - side * drift
    shake = spec.get("shake", 0)
    if shake:
        cam.shift_x = 0.0
        for axis, scale, amp in ((0, 55, 0.02), (1, 71, 0.015), (2, 63, 0.012)):
            co.keyframe_insert("location", index=axis, frame=1)
            co.keyframe_insert("location", index=axis, frame=fr(dur))
        for fc in actions_lib.fcurves_of(co.animation_data.action):
            m = fc.modifiers.new("NOISE")
            m.scale = 48
            m.strength = 0.03 * shake
            m.phase = random.random() * 100
    return co, tgt


def make_lights(scn, shot, co, center):
    mood = MOODS[shot.get("mood", "day")]
    toon.setup_world(tuple(mood["world"]["color"]), mood["world"]["strength"])
    scn.view_settings.exposure = mood.get("exposure", 0.0)
    cam_yaw = math.atan2((center - co.location).x, -(center - co.location).y)  # heading camera->subject (0 = looking +Y)

    def sun(name, elev, az_world, color, energy):
        ld = bpy.data.lights.new(name, "SUN")
        ld.color = color
        ld.energy = energy
        ld.angle = math.radians(2.5)
        o = bpy.data.objects.new(name, ld)
        scn.collection.objects.link(o)
        # sun shines along its local -Z; place so light arrives from azimuth az_world at elevation elev
        o.rotation_euler = (math.radians(90 - elev), 0, az_world)   # az_world = CCW yaw of the travel direction
        return o

    k, r = mood["key"], mood["rim"]
    # azimuth measured from the camera: negative = light from camera-left. cam looks along heading h.
    h = math.atan2((center - co.location).x, (center - co.location).y)   # clockwise-from-+Y heading, cam -> subject
    sun("Key", k["elev"], math.radians(k["az"]) - h, k["color"], k["energy"])           # az<0: light from camera-left
    sun("Rim", r["elev"], -(h + math.radians(150)), r["color"], r["energy"])            # from behind, travels to camera
    if "practical" in mood:
        pl = bpy.data.lights.new("Practical", "POINT")
        pl.color = mood["practical"]["color"]
        pl.energy = mood["practical"]["energy"]
        pl.shadow_soft_size = 0.3
        po = bpy.data.objects.new("Practical", pl)
        po.location = co.location + Vector((0.6, 0.4, 0.9))
        scn.collection.objects.link(po)


# ---------------------------------------------------------------- shot compile
def render_settings(scn, res, samples):
    scn.render.engine = "BLENDER_EEVEE"
    scn.render.resolution_x, scn.render.resolution_y = res
    scn.render.resolution_percentage = 100
    scn.render.fps = FPS
    scn.render.image_settings.file_format = "PNG"
    scn.render.image_settings.color_mode = "RGB"
    scn.render.image_settings.compression = 15
    scn.view_settings.view_transform = "Standard"
    scn.view_settings.look = "None"
    scn.eevee.taa_render_samples = samples
    for attr, val in (("use_shadows", True), ("shadow_ray_count", 1), ("shadow_step_count", 6),
                      ("use_raytracing", False), ("use_fast_gi", False), ("use_gtao", False),
                      ("use_volumetric_shadows", False)):
        if hasattr(scn.eevee, attr):
            try:
                setattr(scn.eevee, attr, val)
            except Exception:
                pass
    scn.render.film_transparent = False


def compile_shot(ep, shot, ep_dir):
    from lipsync_runner import cues as get_cues
    scn, anchors = load_set(shot["set"])
    load_actions()
    col = bpy.data.collections.new("CAST")
    scn.collection.children.link(col)
    dur = shot["dur"]
    scn.frame_start, scn.frame_end = 1, fr(dur) - 1 if fr(dur) > 1 else 1
    actors = {}
    for c in shot["cast"]:
        rig = load_actor(c["actor"], col)
        actors[c["actor"]] = rig
        rig.rotation_mode = "XYZ"
        pos = anchor_pos(c["at"], anchors, {})
        rig.location = pos
    # facing
    for c in shot["cast"]:
        rig = actors[c["actor"]]
        tgt = c.get("face")
        if tgt:
            p = anchor_pos(tgt, anchors, actors)
            rig.rotation_euler.z = yaw_to(rig.location, p)
        elif "rot" in c:
            rig.rotation_euler.z = math.radians(c["rot"])
    bpy.context.view_layer.update()

    # root motion
    travel = {}
    for c in shot["cast"]:
        rig = actors[c["actor"]]
        path = c.get("path")
        if not path:
            continue
        pts = [(0.0, rig.location.copy())] + [(p["t"], anchor_pos(p["to"], anchors, actors)) for p in path]
        speeds = []
        for (ta, a), (tb, b) in zip(pts, pts[1:]):
            speeds.append((b - a).length / max(tb - ta, 1e-3))
        travel[c["actor"]] = max(speeds)
        for (tt, p) in pts:
            rig.location = p
            rig.keyframe_insert("location", frame=fr(tt))
        for (ta, a), (tb, b) in zip(pts, pts[1:]):
            if (b - a).length > 0.05:
                rig.rotation_euler.z = yaw_to(a, b)
                rig.keyframe_insert("rotation_euler", index=2, frame=fr(ta))
                rig.keyframe_insert("rotation_euler", index=2, frame=fr(tb) - 1)
        if c.get("face"):
            fp = anchor_pos(c["face"], anchors, actors)
            rig.rotation_euler.z = yaw_to(pts[-1][1], fp)
            rig.keyframe_insert("rotation_euler", index=2, frame=fr(pts[-1][0]) + 6)
        for fc in actions_lib.fcurves_of(rig.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR" if fc.data_path == "location" else "BEZIER"
        # animation_data.action holds root-motion keys; move them to an NLA-safe place
        root_act = rig.animation_data.action
        rig.animation_data.action = None
        tr = rig.animation_data.nla_tracks.new()
        tr.name = "root_motion"
        st = tr.strips.new("root", 1, root_act)
        if hasattr(st, "action_slot") and st.action_slot is None and getattr(root_act, "slots", None):
            st.action_slot = root_act.slots[0]
        st.blend_type = "COMBINE"
        st.extrapolation = "HOLD"

    # body acting
    for c in shot["cast"]:
        rig = actors[c["actor"]]
        segs = c.get("actions") or [[0.0, c.get("action", "idle_breathe")]]
        build_nla(rig, [(s[0], s[1]) for s in segs], dur, travel.get(c["actor"]))

    # camera
    co, tgt = make_camera(scn, shot, actors, anchors, dur)

    # voice
    cast_cues = {}
    for c in shot["cast"]:
        lines = c.get("lines") or ([c["line"]] if c.get("line") else [])
        lc = []
        for ln in lines:
            wav = ep_dir / ln["wav"] if isinstance(ln, dict) else ep_dir / ln
            t0 = ln.get("t", 0.0) if isinstance(ln, dict) else 0.0
            lc.append((t0, [tuple(x) for x in get_cues(wav, ln.get("text") if isinstance(ln, dict) else None)]))
        cast_cues[c["actor"]] = lc

    # face
    for i, c in enumerate(shot["cast"]):
        rig = actors[c["actor"]]
        face_timeline(rig, c, shot, dur, cast_cues[c["actor"]], seed=hash(shot["id"] + c["actor"]) % 9973,
                      cam_obj=co, others=actors)

    center = sum((r.matrix_world.translation for r in actors.values()), Vector()) / len(actors)
    make_lights(scn, shot, co, center)
    render_settings(scn, tuple(ep["res"]), ep.get("samples", 12))
    scn.frame_set(1)
    out = ep_dir / "shots" / f"{shot['id']}.blend"
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print("[stage_compiler] compiled", shot["id"], "->", out)


def main():
    a = script_args()
    ep_dir = Path(a[0])
    ep = json.loads((ep_dir / "episode_shotlist.json").read_text(encoding="utf-8"))
    only = set(a[1:])
    for shot in ep["shots"]:
        if only and shot["id"] not in only:
            continue
        compile_shot(ep, shot, ep_dir)


main()
