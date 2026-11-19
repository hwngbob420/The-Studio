"""Body-language action library. Runs inside Blender.
Poses are authored once, as direction vectors in armature space (forward = -Y, up = +Z, .L = +X), so every
MPFB actor (any age/size) shares the same actions. build_library() writes asset_vault/actions/library.blend.
Usage: blender -b --python actions_lib.py -- <actor.blend> <out_library.blend>"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

FPS = 60
SPINE = ["spine05", "spine04", "spine03", "spine02", "spine01"]
NECK = ["neck01", "neck02", "neck03"]
FINGERS = [f"finger{i}-{j}" for i in range(2, 6) for j in (1, 2, 3)]


def _upd():
    bpy.context.view_layer.update()


def reset_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.location = (0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
    _upd()


def aim(rig, name, direction):
    """Rotate pose bone so its Y axis points along direction (armature space); children follow."""
    pb = rig.pose.bones[name]
    cur = (pb.matrix.to_3x3() @ Vector((0, 1, 0))).normalized()
    q = cur.rotation_difference(Vector(direction).normalized())
    m = q.to_matrix().to_4x4() @ pb.matrix
    m.translation = pb.matrix.translation
    pb.matrix = m
    _upd()


def rotate_about_head(rig, name, euler_deg):
    """Rotate bone about its head in armature space (x=pitch fwd(+)/back, y=roll side, z=yaw left(+))."""
    pb = rig.pose.bones[name]
    r = Matrix.Rotation(math.radians(euler_deg[2]), 4, "Z") @ Matrix.Rotation(math.radians(euler_deg[1]), 4, "Y") \
        @ Matrix.Rotation(math.radians(euler_deg[0]), 4, "X")
    h = pb.head.copy()
    m = Matrix.Translation(h) @ r @ Matrix.Translation(-h) @ pb.matrix
    pb.matrix = m
    _upd()


def bend_chain(rig, names, euler_deg):
    """Spread an armature-space rotation across a bone chain."""
    n = len(names)
    per = [a / n for a in euler_deg]
    for nm in names:
        rotate_about_head(rig, nm, per)


def curl_hand(rig, side, amount):
    """amount 0..1 closes fingers (local X hinge); thumb handled lightly."""
    for f in FINGERS:
        pb = rig.pose.bones.get(f"{f}.{side}")
        if pb:
            pb.rotation_euler = (math.radians(75 * amount if f.endswith("-1") else 90 * amount), 0, 0)
    t = rig.pose.bones.get(f"finger1-1.{side}")
    if t:
        t.rotation_euler = (math.radians(25 * amount), 0, math.radians((-20 if side == "L" else 20) * amount))


def apply_pose(rig, p):
    """p keys: armL/armR=(upper_dir, fore_dir), legL/legR, spine=(x,y,z deg), neck, head, root=(dx,dy,dz),
    jaw (deg), curlL/curlR (0..1)."""
    reset_pose(rig)
    if "root" in p:
        rig.pose.bones["root"].location = Vector(p["root"])
        _upd()
    if "spine" in p:
        bend_chain(rig, SPINE, p["spine"])
    if "neck" in p:
        bend_chain(rig, NECK, p["neck"])
    if "head" in p:
        rotate_about_head(rig, "head", p["head"])
    for side in ("L", "R"):
        arm = p.get(f"arm{side}")
        if arm:
            aim(rig, f"upperarm01.{side}", arm[0])
            aim(rig, f"lowerarm01.{side}", arm[1])
        leg = p.get(f"leg{side}")
        if leg:
            aim(rig, f"upperleg01.{side}", leg[0])
            aim(rig, f"lowerleg01.{side}", leg[1])
            aim(rig, f"foot.{side}", leg[2] if len(leg) > 2 else (0, -1, -0.06))
        if f"curl{side}" in p:
            curl_hand(rig, side, p[f"curl{side}"])
    if "jaw" in p:
        rig.pose.bones["jaw"].rotation_euler = (math.radians(p["jaw"]), 0, 0)
    _upd()


def mirror(v):
    return (-v[0], v[1], v[2])


def sym(upper, fore, curl=0.25):
    """Same arm pose both sides."""
    return {"armL": (upper, fore), "armR": (mirror(upper), mirror(fore)), "curlL": curl, "curlR": curl}


# ---- pose vocabulary (armature space; arm dirs relative to a standing character facing -Y) ----
ARM_REST = ((0.35, -0.02, -1.0), (0.18, -0.30, -0.95))
LEG_STAND = ((0.06, 0, -1), (0.06, 0, -1))


def stand(**kw):
    p = {"legL": LEG_STAND + ((0, -1, -0.06),), "legR": (mirror(LEG_STAND[0]), mirror(LEG_STAND[1]), (0, -1, -0.06))}
    p.update(kw)
    return p


def A(**kw):
    return stand(**kw)


ACTIONS = {
    # name: dict(loop=bool, length=seconds, keys=[(t_seconds, pose_dict), ...])
    "idle_breathe": dict(loop=True, length=3.0, keys=[
        (0.0, A(**sym(*ARM_REST), spine=(0, 0, 0), head=(0, 0, 0), root=(0, 0, 0))),
        (1.5, A(**sym(*ARM_REST), spine=(-2.2, 1.2, 1.5), head=(1.5, 0, -3), root=(0, 0, 0.004))),
        (3.0, A(**sym(*ARM_REST), spine=(0, 0, 0), head=(0, 0, 0), root=(0, 0, 0))),
    ]),
    "talk_calm": dict(loop=True, length=4.0, keys=[
        (0.0, A(armL=((0.35, -0.1, -1), (0.35, -0.6, -0.6)), armR=((-0.35, -0.05, -1), (-0.2, -0.3, -0.95)),
                curlL=0.3, curlR=0.25, spine=(0, 0, 2), head=(0, 0, -2))),
        (1.0, A(armL=((0.45, -0.25, -0.9), (0.2, -0.85, -0.25)), armR=((-0.35, -0.05, -1), (-0.2, -0.3, -0.95)),
                curlL=0.1, curlR=0.25, spine=(-1, 0, -2), head=(3, 0, 3))),
        (2.0, A(armL=((0.4, -0.1, -1), (0.2, -0.4, -0.85)), armR=((-0.45, -0.2, -0.95), (-0.2, -0.8, -0.35)),
                curlL=0.25, curlR=0.1, spine=(0, 0, -2), head=(-2, 0, 2))),
        (3.0, A(armL=((0.4, -0.2, -0.95), (0.3, -0.7, -0.45)), armR=((-0.4, -0.15, -1), (-0.25, -0.5, -0.8)),
                curlL=0.2, curlR=0.2, spine=(-1, 0, 1), head=(2, 0, -3))),
        (4.0, A(armL=((0.35, -0.1, -1), (0.35, -0.6, -0.6)), armR=((-0.35, -0.05, -1), (-0.2, -0.3, -0.95)),
                curlL=0.3, curlR=0.25, spine=(0, 0, 2), head=(0, 0, -2))),
    ]),
    "talk_emphatic": dict(loop=True, length=3.0, keys=[
        (0.0, A(armL=((0.5, -0.3, -0.8), (0.1, -0.9, 0.1)), armR=((-0.5, -0.3, -0.8), (-0.1, -0.9, 0.1)),
                curlL=0.15, curlR=0.15, spine=(2, 0, 0), head=(-4, 0, 0), root=(0, 0, -0.01))),
        (0.5, A(armL=((0.7, -0.3, -0.4), (0.45, -0.7, 0.4)), armR=((-0.7, -0.3, -0.4), (-0.45, -0.7, 0.4)),
                curlL=0.05, curlR=0.05, spine=(-4, 0, 0), head=(5, 0, 0), root=(0, 0, 0.012))),
        (1.2, A(armL=((0.45, -0.1, -0.9), (0.2, -0.5, -0.8)), armR=((-0.6, -0.4, -0.7), (-0.3, -0.95, 0.15)),
                curlL=0.3, curlR=0.1, spine=(1, 0, -4), head=(-2, 0, 5))),
        (2.0, A(armL=((0.6, -0.4, -0.7), (0.3, -0.95, 0.15)), armR=((-0.45, -0.1, -0.9), (-0.2, -0.5, -0.8)),
                curlL=0.1, curlR=0.3, spine=(1, 0, 4), head=(-2, 0, -5))),
        (3.0, A(armL=((0.5, -0.3, -0.8), (0.1, -0.9, 0.1)), armR=((-0.5, -0.3, -0.8), (-0.1, -0.9, 0.1)),
                curlL=0.15, curlR=0.15, spine=(2, 0, 0), head=(-4, 0, 0), root=(0, 0, -0.01))),
    ]),
    "argue_point": dict(loop=True, length=2.4, keys=[
        (0.0, A(armL=((0.3, -0.2, -0.9), (0.15, -0.5, -0.8)), armR=((-0.55, -0.3, -0.7), (-0.2, -1.0, 0.1)),
                curlL=0.6, curlR=0.8, spine=(2, 0, 5), head=(0, 0, 8))),
        (0.4, A(armL=((0.3, -0.2, -0.9), (0.15, -0.5, -0.8)), armR=((-0.55, -0.3, -0.6), (-0.15, -1.0, 0.35)),
                curlL=0.6, curlR=0.85, spine=(-3, 0, 6), head=(5, 0, 8), root=(0, 0, 0.01))),
        (0.8, A(armL=((0.3, -0.2, -0.9), (0.15, -0.5, -0.8)), armR=((-0.55, -0.3, -0.7), (-0.2, -1.0, 0.0)),
                curlL=0.6, curlR=0.8, spine=(2, 0, 5), head=(-2, 0, 8))),
        (1.6, A(armL=((0.6, -0.3, -0.6), (0.35, -0.9, 0.2)), armR=((-0.55, -0.3, -0.7), (-0.2, -1.0, 0.0)),
                curlL=0.2, curlR=0.8, spine=(0, 0, 3), head=(2, 0, 5))),
        (2.4, A(armL=((0.3, -0.2, -0.9), (0.15, -0.5, -0.8)), armR=((-0.55, -0.3, -0.7), (-0.2, -1.0, 0.1)),
                curlL=0.6, curlR=0.8, spine=(2, 0, 5), head=(0, 0, 8))),
    ]),
    "surprised": dict(loop=False, length=1.6, keys=[
        (0.0, A(**sym(*ARM_REST), spine=(0, 0, 0), head=(0, 0, 0))),
        (0.18, A(**sym((0.85, -0.2, -0.3), (0.55, -0.7, 0.3), 0.0), spine=(-8, 0, 0), head=(-8, 0, 0), root=(0, 0.02, 0.02))),
        (0.9, A(**sym((0.75, -0.2, -0.45), (0.45, -0.75, 0.15), 0.1), spine=(-6, 0, 0), head=(-5, 0, 0), root=(0, 0.015, 0.01))),
        (1.6, A(**sym((0.7, -0.15, -0.5), (0.4, -0.7, 0.1), 0.1), spine=(-5, 0, 2), head=(-3, 0, 2), root=(0, 0.01, 0.005))),
    ]),
    "slump_tired": dict(loop=True, length=4.0, keys=[
        (0.0, A(**sym((0.25, 0.05, -1), (0.15, -0.1, -1), 0.4), spine=(18, 0, 0), neck=(10, 0, 0), head=(14, 0, 0), root=(0, -0.01, -0.03))),
        (2.0, A(**sym((0.25, 0.05, -1), (0.15, -0.1, -1), 0.4), spine=(21, 0, 2), neck=(12, 0, 0), head=(17, 0, 3), root=(0, -0.01, -0.045))),
        (4.0, A(**sym((0.25, 0.05, -1), (0.15, -0.1, -1), 0.4), spine=(18, 0, 0), neck=(10, 0, 0), head=(14, 0, 0), root=(0, -0.01, -0.03))),
    ]),
    "phone_scroll": dict(loop=True, length=3.0, keys=[
        (0.0, A(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.45, -0.25, -0.85), (0.35, -0.8, 0.45)),
                curlL=0.3, curlR=0.6, spine=(6, 0, 0), neck=(8, 0, 0), head=(14, 0, 0))),
        (1.0, A(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.45, -0.25, -0.85), (0.3, -0.8, 0.5)),
                curlL=0.3, curlR=0.62, spine=(7, 0, 0), neck=(9, 0, 0), head=(16, 0, -2))),
        (2.0, A(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.45, -0.25, -0.85), (0.35, -0.8, 0.4)),
                curlL=0.3, curlR=0.6, spine=(6, 0, 0), neck=(8, 0, 0), head=(13, 0, 2))),
        (3.0, A(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.45, -0.25, -0.85), (0.35, -0.8, 0.45)),
                curlL=0.3, curlR=0.6, spine=(6, 0, 0), neck=(8, 0, 0), head=(14, 0, 0))),
    ]),
    "think_chin": dict(loop=True, length=4.0, keys=[
        (0.0, A(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.2, -0.45, -0.8), (0.55, -0.7, 0.6)),
                curlL=0.3, curlR=0.5, spine=(2, 0, -3), head=(-3, 0, 8))),
        (2.0, A(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.2, -0.45, -0.8), (0.55, -0.7, 0.6)),
                curlL=0.3, curlR=0.5, spine=(3, 0, -3), head=(-6, 0, 10))),
        (4.0, A(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.2, -0.45, -0.8), (0.55, -0.7, 0.6)),
                curlL=0.3, curlR=0.5, spine=(2, 0, -3), head=(-3, 0, 8))),
    ]),
}


def _walk_key(ph):
    """Phase 0..1 of a walk cycle -> pose dict."""
    s = math.sin(2 * math.pi * ph)
    c = math.cos(2 * math.pi * ph)
    stride = 0.42
    legs = {}
    for side, sgn in (("L", 1), ("R", -1)):
        sw = s * sgn          # +: leg forward
        lift = max(0.0, c * sgn)   # knee lift while swinging forward
        up = (0.04 * (1 if side == "L" else -1), -stride * sw, -1.0)
        low = (0.04 * (1 if side == "L" else -1), -stride * sw * 0.4 + 0.15 * lift - 0.18 * max(0, -sw), -1.0 + 0.25 * lift)
        legs[f"leg{side}"] = (up, low, (0, -1, -0.06 + 0.25 * lift))
    arm = {}
    for side, sgn in (("L", 1), ("R", -1)):
        sw = -s * sgn
        base = (0.3 * sgn, -0.45 * sw, -1.0)
        arm[f"arm{side}"] = (base, (0.2 * sgn, -0.3 - 0.35 * max(0, sw), -0.95))
    p = dict(legs)
    p.update(arm)
    p.update(curlL=0.3, curlR=0.3, spine=(1, 0, 4 * s), head=(0, 0, -3 * s), root=(0, 0, -0.03 * abs(s)))
    return p


ACTIONS["walk"] = dict(loop=True, length=1.0, keys=[(i / 8.0, _walk_key(i / 8.0)) for i in range(9)])


def fcurves_of(act):
    """Action F-curves on both legacy (<=4.3) and layered/slotted (>=4.4) actions."""
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out += list(cb.fcurves)
    return out


def key_all(rig, frame):
    for pb in rig.pose.bones:
        pb.keyframe_insert("rotation_euler", frame=frame, group=pb.name)
        if pb.name == "root":
            pb.keyframe_insert("location", frame=frame, group=pb.name)


def author_action(rig, name, spec):
    rig.animation_data_create()
    act = bpy.data.actions.new(name)
    rig.animation_data.action = act
    for t, pose in spec["keys"]:
        apply_pose(rig, pose)
        for pb in rig.pose.bones:  # quaternion-free keying: bones aimed via matrix become euler through XYZ mode
            pb.rotation_mode = "XYZ"
        key_all(rig, int(round(t * FPS)) + 1)
    act["loop"] = spec["loop"]
    act["length"] = spec["length"]
    act.use_fake_user = True
    if spec["loop"]:  # smooth cyclic motion
        for fc in fcurves_of(act):
            fc.modifiers.new("CYCLES")
    rig.animation_data.action = None
    return act


def build_library(actor_blend, out_blend):
    bpy.ops.wm.open_mainfile(filepath=str(actor_blend))
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    for name, spec in ACTIONS.items():
        author_action(rig, name, spec)
        print("[actions_lib] authored", name)
    bpy.ops.object.mode_set(mode="OBJECT")
    # keep only actions in the library file: strip every datablock the actions do not need
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    print("[actions_lib] saved", out_blend)


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:]
    build_library(a[0], a[1])
