"""V2 stage compiler: episode_shotlist.json -> one staged .blend per shot (+ <shot>.meta.json for the UI-safe-zone check).
Usage: blender -b --python stage_compiler.py -- <episode_dir> [shot_id ...]
Every actor always runs: base layer (native idle / walk / sit) + upper-body acting layer + breathing/idle sway (in the base
clip) + procedural blinks (every 3-5 s) + eye-target tracking + Rhubarb lip-sync + emotes. No frozen poses."""
import json
import math
import random
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "vault_config" / "shaders"))
import actions_q  # noqa: E402,F401
import master_toon as toon  # noqa: E402
from actions_lib import fcurves_of  # noqa: E402
from studio_paths import script_args  # noqa: E402

VAULT = ROOT / "asset_vault"
CFG = ROOT / "vault_config" / "presets"
FPS = 60
MOODS = json.loads((CFG / "lighting" / "moods.json").read_text())
CAMS = json.loads((CFG / "cameras" / "presets.json").read_text())
ZONE_X = {"left_third": -0.62, "center": 0.0, "right_third": 0.62}   # target NDC x of the subject

# emote -> controls (brow/eye/mouth shape-key values 0..1). Names match ingest_actor.py shape keys.
EMOTES = {
    "neutral": {}, "deadpan": {"brow_down": 0.12},
    "happy": {"smile": 0.85, "squint": 0.25, "brow_up": 0.2}, "amused": {"smile": 0.7, "squint": 0.3, "brow_up": 0.15},
    "excited": {"smile": 1.0, "wide": 0.5, "brow_up": 0.6}, "sad": {"frown": 0.7, "brow_sad": 0.9},
    "angry": {"brow_angry": 1.0, "frown": 0.4}, "surprised": {"brow_up": 1.0, "wide": 1.0},
    "worried": {"brow_sad": 0.7, "frown": 0.3}, "smug": {"smile": 0.4, "brow_skeptic_L": 0.8, "squint": 0.2},
    "skeptical": {"brow_skeptic_L": 1.0, "smile": 0.1, "squint": 0.25}, "tired": {"brow_down": 0.3, "squint": 0.45, "frown": 0.25},
    "exhausted": {"brow_down": 0.5, "squint": 0.6, "frown": 0.3, "brow_sad": 0.3}, "thinking": {"brow_skeptic_L": 0.7, "brow_up": 0.15},
}
ALIASES = {"idle_breathe": "idle", "talk": "talk_calm"}


def fr(t):
    return int(round(t * FPS)) + 1


# ------------------------------------------------------------------ assembly
def load_set(set_id):
    bpy.ops.wm.open_mainfile(filepath=str(VAULT / "sets" / f"{set_id}.blend"))
    scn = bpy.context.scene
    scn.render.fps = FPS
    anchors = {o.name[7:]: o for o in bpy.data.objects if o.name.startswith("ANCHOR_")}
    meta = bpy.data.objects.get("SET_META")
    return scn, anchors, meta


def load_actor(actor_id, col):
    with bpy.data.libraries.load(str(VAULT / "actors" / f"{actor_id}.blend"), link=False) as (src, dst):
        dst.objects = list(src.objects)
    rig = None
    parts = {"eyes": {}, "mouth": None, "head": None}
    for o in dst.objects:
        if o is None:
            continue
        col.objects.link(o)
        if o.type == "ARMATURE":
            rig = o
        elif o.name.split(".")[-1] == "L" and "_Eye" in o.name:
            parts["eyes"]["L"] = o
        elif o.name.split(".")[-1] == "R" and "_Eye" in o.name:
            parts["eyes"]["R"] = o
        elif o.name.endswith("_Mouth"):
            parts["mouth"] = o
        elif o.name.endswith("_Head"):
            parts["head"] = o
    if rig.animation_data:
        rig.animation_data_clear()       # glTF import leaves one NLA track per source clip: clear them all
    return rig, parts


def load_actions():
    with bpy.data.libraries.load(str(VAULT / "actions" / "library_q.blend"), link=False) as (src, dst):
        dst.actions = list(src.actions)


def eye_z(rig):
    return (rig.matrix_world @ rig.data.bones["Eye.L"].head_local).z - rig.matrix_world.translation.z


def head_pos(rig):
    return rig.matrix_world @ rig.data.bones["Eye.L"].head_local.lerp(rig.data.bones["Eye.R"].head_local, 0.5)


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
    return math.atan2(d.x, -d.y)      # actor forward is -Y


# ------------------------------------------------------------------ body acting (layered NLA)
def _strip(track, name, act, start_f, span_f, loop, scale, blend_in=0, blend_out=0, extrap="NOTHING"):
    st = track.strips.new(name, start_f, act)
    if hasattr(st, "action_slot") and st.action_slot is None and getattr(act, "slots", None):
        st.action_slot = act.slots[0]
    natural = max(act.frame_range[1] - act.frame_range[0], 1.0)
    st.scale = scale
    if loop:
        st.repeat = max(1.0, span_f / (natural * scale))
    st.blend_type = "REPLACE"
    st.extrapolation = extrap
    st.blend_in, st.blend_out = blend_in, blend_out
    return st


def build_nla(rig, cast, dur, travel_speed, sitting):
    ad = rig.animation_data_create()
    segs = cast.get("actions") or [[0.0, cast.get("action", "idle")]]
    segs = [(float(t), ALIASES.get(n, n)) for t, n in segs]
    base_segs, up_segs = [], []
    for t, n in segs:
        act = bpy.data.actions[n]
        (up_segs if act.get("upper_only", True) else base_segs).append((t, n))
    if not base_segs:
        base_segs = [(0.0, "sit_idle" if sitting else ("walk" if travel_speed else "idle"))]
    if sitting and all(n not in ("sit_idle", "sit_talk") for _, n in base_segs):
        base_segs = [(0.0, "sit_idle")]
    fade = 0.25
    for layer, group in (("base", base_segs), ("up", up_segs)):
        tracks = [ad.nla_tracks.new(), ad.nla_tracks.new()]
        for tr in tracks:
            tr.name = layer
        for i, (t0, name) in enumerate(group):
            act = bpy.data.actions[name]
            if layer == "base" and name == "walk" and not travel_speed:
                name, act = "idle", bpy.data.actions["idle"]
            t1 = group[i + 1][0] if i + 1 < len(group) else dur
            if layer == "up" and not act["loop"]:
                t1 = min(dur, t0 + act["length"])
            start = max(0.0, t0 - (fade if i else 0.0))
            span = (t1 - start + (fade if i + 1 < len(group) else 0)) * FPS
            natural = max(act.frame_range[1] - act.frame_range[0], 1.0)
            scale = act["length"] * FPS / natural
            if name == "walk" and travel_speed:
                scale = max(0.6, min(1.8, scale * 1.35 / max(travel_speed, 0.3)))
            first = i == 0
            _strip(tracks[i % 2], f"{layer}_{name}_{i}", act, fr(start), span, bool(act["loop"]), scale,
                   blend_in=0 if first else fade * FPS, blend_out=0 if layer == "base" else fade * FPS,
                   extrap="HOLD" if (first and layer == "base") else "NOTHING")
    return ad


# ------------------------------------------------------------------ face
def face_timeline(rig, parts, cast, dur, line_cues, seed, cam_obj, actors, focus_key):
    """Keyframe emotes, blinks, visemes and eye tracking. Returns [(t, head_world_pos)] samples for the UI check."""
    scn = bpy.context.scene
    rnd = random.Random(seed)
    head, mouth, eyes = parts["head"], parts["mouth"], parts["eyes"]
    emotes = sorted(cast.get("emotes") or [[0.0, cast.get("emote", "neutral")]], key=lambda e: e[0])
    keyed = {}
    for ob in [head, mouth, eyes.get("L"), eyes.get("R")]:
        if ob is not None and ob.data.shape_keys:
            keyed[ob.name] = ob.data.shape_keys.key_blocks

    def emote_vals(t):
        cur, prev, t_ch = emotes[0][1], emotes[0][1], -9
        for te, nm in emotes:
            if te <= t:
                prev, cur, t_ch = cur, nm, te
        k = min(1.0, max(0.0, (t - t_ch) / 0.3))
        out = {}
        for nm, w in ((prev, 1 - k), (cur, k)):
            for ctrl, v in EMOTES.get(nm, {}).items():
                out[ctrl] = out.get(ctrl, 0) + v * w
        return out

    blinks, t = [], rnd.uniform(0.8, 2.2)
    while t < dur:
        blinks.append(t)
        t += rnd.uniform(3.0, 5.0)

    def blink_at(t):
        for b in blinks:
            d = t - b
            if 0 <= d <= 0.18:
                return 1.0 - abs(d - 0.09) / 0.09
        return 0.0

    cue_list = sorted((t0 + s, t0 + e, v) for t0, cues in line_cues for s, e, v in cues)

    def viseme_at(t):
        for s, e, v in cue_list:
            if s <= t < e:
                return v
        return "X"

    times = {round(x * 0.1, 3) for x in range(int(dur * 10) + 1)}
    for s, e, v in cue_list:
        times.update([round(s, 3), round(max(s, e - 0.02), 3)])
    for b in blinks:
        times.update([round(b, 3), round(b + 0.09, 3), round(b + 0.18, 3)])
    for te, _ in emotes:
        times.update([round(te, 3), round(te + 0.3, 3)])
    eye_t = [round(x * 0.25, 3) for x in range(int(dur * 4) + 1)]
    times = sorted(x for x in (times | set(eye_t)) if 0 <= x <= dur)

    look = cast.get("look", "cam")
    last, records = {}, []
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    for t in times:
        f = fr(t)
        scn.frame_set(f)
        ev = emote_vals(t)
        vis = viseme_at(t)
        for obn, kb in keyed.items():
            for k in kb:
                if k.name == "Basis":
                    continue
                v = 0.0
                if obn.endswith("_Mouth"):
                    if k.name in ("smile", "frown", "smirk"):
                        v = min(1.0, ev.get(k.name, 0.0))
                    elif k.name == vis:
                        v = 1.0
                elif "_Eye" in obn:
                    v = blink_at(t) if k.name == "blink" else min(1.0, ev.get(k.name, 0.0))
                else:
                    v = min(1.0, ev.get(k.name, 0.0))
                if abs(last.get((obn, k.name), -1) - v) > 1e-3 or t in (0.0, dur):
                    k.value = v
                    k.keyframe_insert("value", frame=f)
                    last[(obn, k.name)] = v
        tgt = None
        if look == "cam":
            tgt = cam_obj.matrix_world.translation.copy()
        elif isinstance(look, list):
            tgt = Vector(look)
        elif look in actors:
            tgt = head_pos(actors[look])
        if tgt is not None:
            for s in ("L", "R"):
                eb = rig.pose.bones[f"Eye.{s}"]
                eb.rotation_mode = "QUATERNION"
                eb.rotation_quaternion = (1, 0, 0, 0)
                bpy.context.view_layer.update()
                ew = rig.matrix_world @ eb.head
                d_arm = rig.matrix_world.to_3x3().inverted() @ (tgt - ew)
                cur = (eb.matrix.to_3x3() @ Vector((0, 1, 0))).normalized()
                q = cur.rotation_difference(d_arm.normalized())
                if q.angle > math.radians(32):
                    q = q.__class__((1, 0, 0, 0)).slerp(q, math.radians(32) / q.angle)
                m = q.to_matrix().to_4x4() @ eb.matrix
                m.translation = eb.matrix.translation
                eb.matrix = m
                bpy.context.view_layer.update()
        for s in ("L", "R"):
            rig.pose.bones[f"Eye.{s}"].keyframe_insert("rotation_quaternion", frame=f, group="eyes")
        if abs(t * 2 - round(t * 2)) < 1e-6:
            records.append((t, head_pos(rig)))
        focus_key(t, f)
    bpy.ops.object.mode_set(mode="OBJECT")
    return records


# ------------------------------------------------------------------ camera / light / framing
def make_camera(scn, shot, actors, dur):
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
    focus = bpy.data.objects.new("FocusTarget", None)      # DoF focus sits on the active speaker's eyes
    scn.collection.objects.link(focus)
    speaker = shot["cam"].get("speaker") or shot.get("speaker")
    kind = spec["kind"]
    if kind == "frame":
        vfov = 2 * math.atan((36 * 9 / 16 / 2) / spec["lens"])
        need_h = max(spec["frame_h"], (spread + 1.3) * 9 / 16)
        if shot.get("subject_zone", "center") != "center" and len(names) > 1:     # group must fit inside ~55% of the frame
            need_h = max(need_h, (spread / 0.5 + 1.2) * 9 / 16)
        dist = max(spec.get("min_dist", 1.5), need_h / 2 / math.tan(vfov / 2))
        az = math.radians(spec["az"])
        tgt.location = center + Vector((0, 0, spec["target_h"]))
        co.location = center + Vector((math.sin(az) * dist, -math.cos(az) * dist, spec["height"]))
        fa = actors[speaker] if speaker in actors else actors[names[0]]
    elif kind == "ots":
        a, b = actors[spec["over"]], actors[spec["at"]]
        pa, pb = a.matrix_world.translation, b.matrix_world.translation
        fwd = (pb - pa).normalized()
        side = Vector((-fwd.y, fwd.x, 0))
        co.location = pa - fwd * spec["back"] + side * spec["side"] * spec.get("flip", 1) + Vector((0, 0, eye_z(a) + spec["up"]))
        tgt.location = pb + Vector((0, 0, eye_z(b) - 0.03))
        fa = b
    else:
        a = actors[names[0]]
        pa = a.matrix_world.translation
        yaw = a.rotation_euler.z
        fwd = Vector((math.sin(yaw), -math.cos(yaw), 0))
        side = Vector((-fwd.y, fwd.x, 0))
        ez = eye_z(a)
        co.location = pa + fwd * spec["dist"] + side * spec["side"] * spec.get("flip", 1) + Vector((0, 0, ez + 0.02))
        tgt.location = pa + Vector((0, 0, ez - 0.02))
        fa = a
    cl = focus.constraints.new("COPY_LOCATION")
    cl.target = fa
    cl.subtarget = "Eye.L"
    con = co.constraints.new("TRACK_TO")
    con.target = tgt
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    cam.dof.focus_object = focus if spec["fstop"] < 6 else tgt
    push = spec.get("push", 0)
    if push:
        v = (tgt.location - co.location).normalized()
        co.keyframe_insert("location", frame=1)
        co.location = co.location + v * push
        co.keyframe_insert("location", frame=fr(dur))
        co.location = co.location - v * push
        for fc in fcurves_of(co.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    shake = spec.get("shake", 0)
    if shake:
        for axis in range(3):
            co.keyframe_insert("location", index=axis, frame=1)
            co.keyframe_insert("location", index=axis, frame=fr(dur))
        for fc in fcurves_of(co.animation_data.action):
            m = fc.modifiers.new("NOISE")
            m.scale, m.strength, m.phase = 48, 0.03 * shake, random.random() * 100
    return co, tgt, center, names


def apply_subject_zone(scn, co, shot, actors, names):
    """Lens-shift the subject (focus actors' heads) onto the declared rule-of-thirds zone."""
    zone = shot.get("subject_zone", "center")
    tx = ZONE_X[zone] * (0.5 if len(names) > 1 else 1.0) * (0.55 if shot['cam'].get('preset') == 'CloseUp' else 1.0)      # groups are centred in the 2/3 band that excludes the UI third
    scn.frame_set(1)
    bpy.context.view_layer.update()
    pts = [head_pos(actors[n]) for n in names]
    c = sum(pts, Vector()) / len(pts)
    ndc = world_to_camera_view(scn, co, c)
    cur = ndc.x * 2 - 1
    co.data.shift_x = (cur - tx) / 2.0
    return [cur, tx]


def make_lights(scn, shot, co, center, meta):
    mood = MOODS[shot.get("mood", "day")]
    hd = json.loads(meta["hdri"]) if meta and "hdri" in meta else {}
    hdr = VAULT / "_hdri" / f"{hd.get(shot.get('mood', 'day'), 'kloofendal_48d_partly_cloudy_puresky')}_1k.hdr"
    toon.hdri_world(hdr, mood["world"]["strength"], tint=tuple(mood["world"]["tint"]) if "tint" in mood["world"] else None,
                    rotation_deg=shot.get("hdri_rot", 0.0))
    scn.view_settings.exposure = mood.get("exposure", 0.0)
    h = math.atan2((center - co.location).x, (center - co.location).y)

    def sun(name, elev, rz, color, energy, angle=2.2):
        ld = bpy.data.lights.new(name, "SUN")
        ld.color, ld.energy, ld.angle = color, energy, math.radians(angle)
        ld.use_shadow = True
        o = bpy.data.objects.new(name, ld)
        scn.collection.objects.link(o)
        o.rotation_euler = (math.radians(90 - elev), 0, rz)
        return o

    k, r = mood["key"], mood["rim"]
    sun("Key", k["elev"], math.radians(k["az"]) - h, k["color"], k["energy"])
    sun("Rim", r["elev"], -(h + math.radians(150)), r["color"], r["energy"], angle=1.5)
    fl = bpy.data.lights.new("Fill", "AREA")
    fl.color = mood.get("fill", {}).get("color", (0.8, 0.88, 1.0))
    fl.energy = mood.get("fill", {}).get("energy", 220)
    fl.size = 4.0
    fo = bpy.data.objects.new("Fill", fl)
    fo.location = co.location + Vector((1.8, 0.4, 1.2))
    tgt = bpy.data.objects.new("LightTarget", None)
    tgt.location = center + Vector((0, 0, 1.2))
    scn.collection.objects.link(tgt)
    fc = fo.constraints.new("TRACK_TO")
    fc.target, fc.track_axis, fc.up_axis = tgt, "TRACK_NEGATIVE_Z", "UP_Y"
    scn.collection.objects.link(fo)
    if "practical" in mood:
        pl = bpy.data.lights.new("Practical", "POINT")
        pl.color, pl.energy, pl.shadow_soft_size = mood["practical"]["color"], mood["practical"]["energy"], 0.3
        po = bpy.data.objects.new("Practical", pl)
        po.location = center + Vector((0.8, 0.5, 2.0))
        scn.collection.objects.link(po)


def add_contact_shadow(rig, col, size=0.9):
    """Soft grounded blob under every actor (flat radial-gradient decal that follows the rig)."""
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, radius=size / 2, segments=32)
    me = bpy.data.meshes.new("blob")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(f"{rig.name}_contact", me)
    col.objects.link(ob)
    ob.parent = rig
    ob.location = (0, 0.02, 0.012)
    ob.visible_shadow = False
    m = bpy.data.materials.new("contact_blob")
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial")
    tc = t.nodes.new("ShaderNodeTexCoord")
    mp = t.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / (size / 2),) * 3
    ln = t.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    inv = t.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    sm = t.nodes.new("ShaderNodeMath")
    sm.operation = "MULTIPLY"
    sm.use_clamp = True
    sm.inputs[1].default_value = 0.6
    tr = t.nodes.new("ShaderNodeBsdfTransparent")
    bl = t.nodes.new("ShaderNodeEmission")
    bl.inputs["Color"].default_value = (0.02, 0.015, 0.04, 1)
    mix = t.nodes.new("ShaderNodeMixShader")
    t.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    t.links.new(mp.outputs[0], ln.inputs[0])
    t.links.new(ln.outputs["Value"], inv.inputs[1])
    t.links.new(inv.outputs[0], sm.inputs[0])
    t.links.new(sm.outputs[0], mix.inputs["Fac"])
    t.links.new(tr.outputs[0], mix.inputs[1])
    t.links.new(bl.outputs[0], mix.inputs[2])
    t.links.new(mix.outputs[0], out.inputs[0])
    m.surface_render_method = "DITHERED"
    ob.data.materials.append(m)


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
    for attr, val in (("use_shadows", True), ("shadow_ray_count", 2), ("shadow_step_count", 8), ("use_raytracing", False),
                      ("use_fast_gi", True), ("fast_gi_method", "AMBIENT_OCCLUSION_ONLY"), ("fast_gi_distance", 0.6),
                      ("fast_gi_quality", 0.5), ("use_volumetric_shadows", False)):
        try:
            setattr(scn.eevee, attr, val)
        except Exception as exc:
            print("[stage_compiler] eevee", attr, exc)
    scn.render.film_transparent = False


# ------------------------------------------------------------------ shot
def compile_shot(ep, shot, ep_dir):
    from lipsync_runner import cues as get_cues
    scn, anchors, meta = load_set(shot["set"])
    load_actions()
    col = bpy.data.collections.new("CAST")
    scn.collection.children.link(col)
    dur = shot["dur"]
    scn.frame_start, scn.frame_end = 1, fr(dur) - 1
    actors, parts = {}, {}
    for c in shot["cast"]:
        rig, pt = load_actor(c["actor"], col)
        actors[c["actor"]], parts[c["actor"]] = rig, pt
        rig.rotation_mode = "XYZ"
        rig.location = anchor_pos(c["at"], anchors, {})
    for c in shot["cast"]:
        rig = actors[c["actor"]]
        if c.get("face"):
            rig.rotation_euler.z = yaw_to(rig.location, anchor_pos(c["face"], anchors, actors))
        elif "rot" in c:
            rig.rotation_euler.z = math.radians(c["rot"])
        add_contact_shadow(rig, col)
    bpy.context.view_layer.update()
    sitting, travel = {}, {}
    for c in shot["cast"]:
        a = c["at"]
        sitting[c["actor"]] = isinstance(a, str) and a in anchors and anchors[a].get("kind") == "sitting"
    for c in shot["cast"]:
        rig = actors[c["actor"]]
        path = c.get("path")
        if not path:
            continue
        pts = [(0.0, rig.location.copy())] + [(p["t"], anchor_pos(p["to"], anchors, actors)) for p in path]
        travel[c["actor"]] = max((b - a).length / max(tb - ta, 1e-3) for (ta, a), (tb, b) in zip(pts, pts[1:]))
        rig.animation_data_create()
        for (tt, p) in pts:
            rig.location = p
            rig.keyframe_insert("location", frame=fr(tt))
        for (ta, a), (tb, b) in zip(pts, pts[1:]):
            if (b - a).length > 0.05:
                rig.rotation_euler.z = yaw_to(a, b)
                rig.keyframe_insert("rotation_euler", index=2, frame=fr(ta))
                rig.keyframe_insert("rotation_euler", index=2, frame=fr(tb) - 1)
        if c.get("face"):
            rig.rotation_euler.z = yaw_to(pts[-1][1], anchor_pos(c["face"], anchors, actors))
            rig.keyframe_insert("rotation_euler", index=2, frame=fr(pts[-1][0]) + 8)
        act = rig.animation_data.action
        for fc in fcurves_of(act):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR" if fc.data_path == "location" else "BEZIER"
        rig.animation_data.action = None
        tr = rig.animation_data.nla_tracks.new()
        tr.name = "root_motion"
        st = tr.strips.new("root", 1, act)
        if hasattr(st, "action_slot") and st.action_slot is None and getattr(act, "slots", None):
            st.action_slot = act.slots[0]
        st.blend_type, st.extrapolation = "COMBINE", "HOLD"
    for c in shot["cast"]:
        build_nla(actors[c["actor"]], c, dur, travel.get(c["actor"]), sitting[c["actor"]])
    allv = json.loads((CFG / "actor_variants.json").read_text())
    for c in shot["cast"]:
        v = next((x for x in allv["variants"] if x["id"] == c["actor"]), None)
        if v:
            k = v["height"] / 1.83
            actors[c["actor"]].scale = (k, k, k)
    bpy.context.view_layer.update()

    co, tgt, center, focus_names = make_camera(scn, shot, actors, dur)
    mover = any(n in travel for n in focus_names) and shot["cam"].get("preset", "Medium") in ("Wide", "Medium", "SlowDolly", "Handheld")
    base_tgt = tgt.location.copy()
    zone_info = apply_subject_zone(scn, co, shot, actors, focus_names)

    def focus_key(t, f):
        if mover and abs(t * 4 - round(t * 4)) < 1e-6:
            c_ = sum((actors[n].matrix_world.translation for n in focus_names), Vector()) / len(focus_names)
            tgt.location = Vector((c_.x, c_.y, base_tgt.z))
            tgt.keyframe_insert("location", frame=f)

    cast_cues = {}
    for c in shot["cast"]:
        lines = c.get("lines") or ([c["line"]] if c.get("line") else [])
        lc = []
        for ln in lines:
            ln = ln if isinstance(ln, dict) else {"wav": ln}
            lc.append((ln.get("t", 0.0), [tuple(x) for x in get_cues(ep_dir / ln["wav"], ln.get("text"))]))
        cast_cues[c["actor"]] = lc
    meta_out = {"shot": shot["id"], "res": ep["res"], "subject_zone": shot.get("subject_zone", "center"),
                "ui_safe_zone": shot.get("ui_safe_zone", "none"), "zone_shift": zone_info, "faces": {}}
    recs_all = {}
    for i, c in enumerate(shot["cast"]):
        recs_all[c["actor"]] = face_timeline(actors[c["actor"]], parts[c["actor"]], c, dur, cast_cues[c["actor"]],
                                             seed=sum(map(ord, shot["id"] + c["actor"])) % 9973, cam_obj=co, actors=actors,
                                             focus_key=focus_key if i == 0 else (lambda t, f: None))
    res = ep["res"]
    for name, recs in recs_all.items():
        out = []
        for t, _ in recs:
            scn.frame_set(fr(t))
            bpy.context.view_layer.update()
            hp = head_pos(actors[name])
            n = world_to_camera_view(scn, co, hp)
            n2 = world_to_camera_view(scn, co, hp + co.matrix_world.to_3x3() @ Vector((0.17, 0.0, 0)))
            out.append([round(t, 2), round(n.x * res[0]), round((1 - n.y) * res[1]), round(abs(n2.x - n.x) * res[0] * 1.35)])
        meta_out["faces"][name] = out
    center = sum((r.matrix_world.translation for r in actors.values()), Vector()) / len(actors)
    make_lights(scn, shot, co, center, meta)
    render_settings(scn, tuple(ep["res"]), ep.get("samples", 8))
    scn.frame_set(1)
    out = ep_dir / "shots" / f"{shot['id']}.blend"
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    (ep_dir / "shots" / f"{shot['id']}.meta.json").write_text(json.dumps(meta_out))
    print("[stage_compiler] compiled", shot["id"], "->", out)


def main():
    a = script_args()
    ep_dir = Path(a[0])
    ep = json.loads((ep_dir / "episode_shotlist.json").read_text(encoding="utf-8"))
    only = set(a[1:])
    for shot in ep["shots"]:
        if not only or shot["id"] in only:
            compile_shot(ep, shot, ep_dir)


main()
