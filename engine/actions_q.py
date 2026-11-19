"""V2 body-language library for the shared Quaternius 62-bone rig (also the target of Mixamo retargeting).
  * LOCOMOTION / IDLE come from the rig's own authored clips (Idle_Neutral, Walk, Run, Wave...) - real keyframed motion.
  * UPPER-BODY acting (talk/argue/think/...) is authored here from direction vectors, keyed ONLY on arms/spine/head/hands
    so it layers on top of idle/walk in the NLA (legs keep their natural weight shift) - no frozen poses.
  * SIT / seated acting: full-body poses with a seat offset.
Run: blender -b --python actions_q.py -- <actor.blend> <out_library.blend>"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from actions_lib import fcurves_of  # noqa: E402

FPS = 60
SPINE = ["Abdomen", "Torso", "Chest"]
NECK = ["Neck"]
FINGERS = [f"{f}{i}" for f in ("Index", "Middle", "Ring", "Pinky") for i in (1, 2, 3)]
UPPER_BONES = (["Shoulder", "UpperArm", "LowerArm", "Wrist"] + FINGERS + ["Thumb1", "Thumb2", "Thumb3"])


def _upd():
    bpy.context.view_layer.update()


def side_bones(rig, base):
    return [b for b in (f"{base}.L", f"{base}.R") if b in rig.pose.bones]


def reset_pose(rig, only=None):
    for pb in rig.pose.bones:
        if only is not None and not only(pb.name):
            continue
        pb.rotation_mode = "QUATERNION"     # the rig's native clips are quaternion; stay compatible when layering
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)
    _upd()


def aim(rig, name, direction):
    pb = rig.pose.bones[name]
    cur = (pb.matrix.to_3x3() @ Vector((0, 1, 0))).normalized()
    q = cur.rotation_difference(Vector(direction).normalized())
    m = q.to_matrix().to_4x4() @ pb.matrix
    m.translation = pb.matrix.translation
    pb.matrix = m
    _upd()


def rotate_about_head(rig, name, euler_deg):
    pb = rig.pose.bones[name]
    r = (Matrix.Rotation(math.radians(euler_deg[2]), 4, "Z") @ Matrix.Rotation(math.radians(euler_deg[1]), 4, "Y")
         @ Matrix.Rotation(math.radians(euler_deg[0]), 4, "X"))
    h = pb.head.copy()
    pb.matrix = Matrix.Translation(h) @ r @ Matrix.Translation(-h) @ pb.matrix
    _upd()


def bend_chain(rig, names, euler_deg):
    n = len(names)
    for nm in names:
        rotate_about_head(rig, nm, [a / n for a in euler_deg])


def shift_bone(rig, name, delta):
    pb = rig.pose.bones[name]
    m = pb.matrix.copy()
    m.translation += Vector(delta)
    pb.matrix = m
    _upd()


def curl_hand(rig, side, amount):
    """Close the fingers about the armature Y axis (palm-relative because the axis is converted to bone space)."""
    sgn = 1 if side == "L" else -1
    for f in FINGERS:
        nm = f"{f}.{side}"
        if nm not in rig.pose.bones:
            continue
        b = rig.data.bones[nm]
        axis = b.matrix_local.to_3x3().inverted() @ Vector((0, sgn, 0))
        ang = math.radians((70 if f.endswith("1") else 85) * amount)
        rig.pose.bones[nm].rotation_quaternion = Quaternion(axis.normalized(), ang)
    for nm, k in ((f"Thumb1.{side}", 25), (f"Thumb2.{side}", 30)):
        if nm in rig.pose.bones:
            b = rig.data.bones[nm]
            axis = b.matrix_local.to_3x3().inverted() @ Vector((0, sgn, 0))
            rig.pose.bones[nm].rotation_quaternion = Quaternion(axis.normalized(), math.radians(k * amount))


def mirror(v):
    return (-v[0], v[1], v[2])


def sym(upper, fore, curl=0.25):
    return {"armL": (upper, fore), "armR": (mirror(upper), mirror(fore)), "curlL": curl, "curlR": curl}


def apply_pose(rig, p, upper_only=True):
    """p: armL/armR=(upper_dir, fore_dir), spine/neck/head (deg), hips=(dx,dy,dz m), curlL/curlR, legL/legR."""
    reset_pose(rig, None if not upper_only else (lambda n: n.split(".")[0] in UPPER_BONES + SPINE + NECK + ["Head"]))
    if "hips" in p:
        shift_bone(rig, "Body", p["hips"])
    if "spine" in p:
        bend_chain(rig, SPINE, p["spine"])
    if "neck" in p:
        bend_chain(rig, NECK, p["neck"])
    if "head" in p:
        rotate_about_head(rig, "Head", p["head"])
    for s in ("L", "R"):
        arm = p.get(f"arm{s}")
        if arm:
            aim(rig, f"UpperArm.{s}", arm[0])
            aim(rig, f"LowerArm.{s}", arm[1])
        leg = p.get(f"leg{s}")
        if leg:
            aim(rig, f"UpperLeg.{s}", leg[0])
            aim(rig, f"LowerLeg.{s}", leg[1])
            aim(rig, f"Foot.{s}", leg[2] if len(leg) > 2 else (0, -1, -0.05))
        if f"curl{s}" in p:
            curl_hand(rig, s, p[f"curl{s}"])
    _upd()


REST_ARM = ((0.30, -0.02, -1.0), (0.14, -0.28, -0.95))


def S(upper, fore, curl=0.3):
    return sym(upper, fore, curl)


T = {}  # action name -> dict(loop, length, keys=[(t, pose)])
T["talk_calm"] = dict(loop=True, length=4.0, keys=[
    (0.0, dict(armL=((0.35, -0.12, -1), (0.40, -0.65, -0.55)), armR=((-0.30, -0.04, -1), (-0.14, -0.25, -0.95)), curlL=0.3, curlR=0.3, spine=(0, 0, 2), head=(0, 0, -2))),
    (1.0, dict(armL=((0.50, -0.30, -0.85), (0.20, -0.90, -0.20)), armR=((-0.30, -0.04, -1), (-0.14, -0.25, -0.95)), curlL=0.1, curlR=0.3, spine=(-1, 0, -2), head=(3, 0, 3))),
    (2.0, dict(armL=((0.40, -0.10, -1), (0.20, -0.42, -0.85)), armR=((-0.50, -0.25, -0.85), (-0.22, -0.88, -0.30)), curlL=0.3, curlR=0.1, spine=(0, 0, -2), head=(-2, 0, 2))),
    (3.0, dict(armL=((0.45, -0.20, -0.95), (0.32, -0.75, -0.40)), armR=((-0.40, -0.12, -1), (-0.25, -0.50, -0.80)), curlL=0.2, curlR=0.2, spine=(-1, 0, 1), head=(2, 0, -3))),
    (4.0, dict(armL=((0.35, -0.12, -1), (0.40, -0.65, -0.55)), armR=((-0.30, -0.04, -1), (-0.14, -0.25, -0.95)), curlL=0.3, curlR=0.3, spine=(0, 0, 2), head=(0, 0, -2))),
])
T["talk_emphatic"] = dict(loop=True, length=3.0, keys=[
    (0.0, dict(armL=((0.55, -0.30, -0.80), (0.10, -0.95, 0.10)), armR=((-0.55, -0.30, -0.80), (-0.10, -0.95, 0.10)), curlL=0.15, curlR=0.15, spine=(2, 0, 0), head=(-4, 0, 0))),
    (0.5, dict(armL=((0.75, -0.30, -0.40), (0.50, -0.75, 0.40)), armR=((-0.75, -0.30, -0.40), (-0.50, -0.75, 0.40)), curlL=0.05, curlR=0.05, spine=(-4, 0, 0), head=(5, 0, 0))),
    (1.2, dict(armL=((0.50, -0.10, -0.90), (0.20, -0.50, -0.80)), armR=((-0.65, -0.40, -0.70), (-0.30, -0.95, 0.15)), curlL=0.3, curlR=0.1, spine=(1, 0, -4), head=(-2, 0, 5))),
    (2.0, dict(armL=((0.65, -0.40, -0.70), (0.30, -0.95, 0.15)), armR=((-0.50, -0.10, -0.90), (-0.20, -0.50, -0.80)), curlL=0.1, curlR=0.3, spine=(1, 0, 4), head=(-2, 0, -5))),
    (3.0, dict(armL=((0.55, -0.30, -0.80), (0.10, -0.95, 0.10)), armR=((-0.55, -0.30, -0.80), (-0.10, -0.95, 0.10)), curlL=0.15, curlR=0.15, spine=(2, 0, 0), head=(-4, 0, 0))),
])
T["argue_point"] = dict(loop=True, length=2.4, keys=[
    (0.0, dict(armL=((0.35, -0.2, -0.9), (0.18, -0.5, -0.8)), armR=((-0.60, -0.30, -0.70), (-0.20, -1.0, 0.10)), curlL=0.6, curlR=0.85, spine=(2, 0, 5), head=(0, 0, 8))),
    (0.4, dict(armL=((0.35, -0.2, -0.9), (0.18, -0.5, -0.8)), armR=((-0.60, -0.30, -0.60), (-0.15, -1.0, 0.35)), curlL=0.6, curlR=0.9, spine=(-3, 0, 6), head=(5, 0, 8))),
    (0.8, dict(armL=((0.35, -0.2, -0.9), (0.18, -0.5, -0.8)), armR=((-0.60, -0.30, -0.70), (-0.20, -1.0, 0.0)), curlL=0.6, curlR=0.85, spine=(2, 0, 5), head=(-2, 0, 8))),
    (1.6, dict(armL=((0.60, -0.3, -0.6), (0.35, -0.9, 0.2)), armR=((-0.60, -0.30, -0.70), (-0.20, -1.0, 0.0)), curlL=0.2, curlR=0.85, spine=(0, 0, 3), head=(2, 0, 5))),
    (2.4, dict(armL=((0.35, -0.2, -0.9), (0.18, -0.5, -0.8)), armR=((-0.60, -0.30, -0.70), (-0.20, -1.0, 0.10)), curlL=0.6, curlR=0.85, spine=(2, 0, 5), head=(0, 0, 8))),
])
T["surprised"] = dict(loop=False, length=1.6, keys=[
    (0.0, dict(**S(*REST_ARM), spine=(0, 0, 0), head=(0, 0, 0))),
    (0.18, dict(**S((0.85, -0.2, -0.3), (0.55, -0.7, 0.3), 0.0), spine=(-8, 0, 0), head=(-8, 0, 0), hips=(0, 0.02, 0.01))),
    (0.9, dict(**S((0.75, -0.2, -0.45), (0.45, -0.75, 0.15), 0.1), spine=(-6, 0, 0), head=(-5, 0, 0))),
    (1.6, dict(**S((0.70, -0.15, -0.5), (0.40, -0.7, 0.1), 0.1), spine=(-5, 0, 2), head=(-3, 0, 2))),
])
T["slump_tired"] = dict(loop=True, length=4.0, keys=[
    (0.0, dict(**S((0.22, 0.05, -1), (0.12, -0.1, -1), 0.4), spine=(16, 0, 0), neck=(10, 0, 0), head=(14, 0, 0), hips=(0, 0, -0.012))),
    (2.0, dict(**S((0.22, 0.05, -1), (0.12, -0.1, -1), 0.4), spine=(20, 0, 2), neck=(12, 0, 0), head=(17, 0, 3), hips=(0, 0, -0.02))),
    (4.0, dict(**S((0.22, 0.05, -1), (0.12, -0.1, -1), 0.4), spine=(16, 0, 0), neck=(10, 0, 0), head=(14, 0, 0), hips=(0, 0, -0.012))),
])
T["phone_scroll"] = dict(loop=True, length=3.0, keys=[
    (0.0, dict(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.45, -0.25, -0.85), (0.35, -0.8, 0.45)), curlL=0.3, curlR=0.6, spine=(6, 0, 0), neck=(8, 0, 0), head=(14, 0, 0))),
    (1.0, dict(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.45, -0.25, -0.85), (0.3, -0.8, 0.5)), curlL=0.3, curlR=0.62, spine=(7, 0, 0), neck=(9, 0, 0), head=(16, 0, -2))),
    (2.0, dict(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.45, -0.25, -0.85), (0.35, -0.8, 0.4)), curlL=0.3, curlR=0.6, spine=(6, 0, 0), neck=(8, 0, 0), head=(13, 0, 2))),
    (3.0, dict(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.45, -0.25, -0.85), (0.35, -0.8, 0.45)), curlL=0.3, curlR=0.6, spine=(6, 0, 0), neck=(8, 0, 0), head=(14, 0, 0))),
])
T["think_chin"] = dict(loop=True, length=4.0, keys=[
    (0.0, dict(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.25, -0.45, -0.8), (0.60, -0.75, 0.55)), curlL=0.3, curlR=0.5, spine=(2, 0, -3), head=(-3, 0, 8))),
    (2.0, dict(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.25, -0.45, -0.8), (0.60, -0.75, 0.55)), curlL=0.3, curlR=0.5, spine=(3, 0, -3), head=(-6, 0, 10))),
    (4.0, dict(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.25, -0.45, -0.8), (0.60, -0.75, 0.55)), curlL=0.3, curlR=0.5, spine=(2, 0, -3), head=(-3, 0, 8))),
])
T["drink_coffee"] = dict(loop=True, length=5.0, keys=[
    (0.0, dict(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.30, -0.35, -0.90), (-0.05, -0.90, -0.15)), curlL=0.3, curlR=0.8, spine=(1, 0, 0), head=(0, 0, 0))),
    (1.5, dict(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.25, -0.55, -0.55), (0.20, -0.45, 0.85)), curlL=0.3, curlR=0.8, spine=(2, 0, 0), head=(-8, 0, 0))),
    (3.0, dict(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.25, -0.55, -0.55), (0.20, -0.45, 0.85)), curlL=0.3, curlR=0.8, spine=(2, 0, 0), head=(-9, 0, 0))),
    (4.2, dict(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.30, -0.35, -0.90), (-0.05, -0.90, -0.15)), curlL=0.3, curlR=0.8, spine=(1, 0, 0), head=(0, 0, 0))),
    (5.0, dict(armL=((0.3, -0.1, -1), (0.2, -0.3, -0.95)), armR=((-0.30, -0.35, -0.90), (-0.05, -0.90, -0.15)), curlL=0.3, curlR=0.8, spine=(1, 0, 0), head=(0, 0, 0))),
])
T["shrug"] = dict(loop=False, length=1.8, keys=[
    (0.0, dict(**S(*REST_ARM), spine=(0, 0, 0), head=(0, 0, 0))),
    (0.35, dict(**S((0.55, -0.1, -0.75), (0.45, -0.65, 0.05), 0.0), spine=(-1, 0, 0), head=(0, 0, 8), hips=(0, 0, 0.0))),
    (1.1, dict(**S((0.55, -0.1, -0.75), (0.45, -0.65, 0.05), 0.0), spine=(-1, 0, 0), head=(0, 0, -6))),
    (1.8, dict(**S(*REST_ARM), spine=(0, 0, 0), head=(0, 0, 0))),
])
T["laugh"] = dict(loop=True, length=1.2, keys=[
    (0.0, dict(**S((0.35, -0.1, -0.95), (0.25, -0.45, -0.8), 0.3), spine=(-6, 0, 0), head=(-10, 0, 0), hips=(0, 0, 0.004))),
    (0.15, dict(**S((0.35, -0.1, -0.95), (0.25, -0.45, -0.8), 0.3), spine=(-2, 0, 0), head=(-4, 0, 0), hips=(0, 0, -0.006))),
    (0.30, dict(**S((0.35, -0.1, -0.95), (0.25, -0.45, -0.8), 0.3), spine=(-6, 0, 0), head=(-10, 0, 0), hips=(0, 0, 0.004))),
    (0.45, dict(**S((0.35, -0.1, -0.95), (0.25, -0.45, -0.8), 0.3), spine=(-2, 0, 0), head=(-4, 0, 0), hips=(0, 0, -0.006))),
    (0.6, dict(**S((0.35, -0.1, -0.95), (0.25, -0.45, -0.8), 0.3), spine=(-6, 0, 0), head=(-10, 0, 0), hips=(0, 0, 0.004))),
    (1.2, dict(**S((0.35, -0.1, -0.95), (0.25, -0.45, -0.8), 0.3), spine=(-6, 0, 0), head=(-10, 0, 0), hips=(0, 0, 0.004))),
])
T["cross_arms"] = dict(loop=True, length=4.0, keys=[
    (0.0, dict(armL=((0.18, -0.55, -0.80), (-0.55, -0.80, -0.10)), armR=((-0.18, -0.55, -0.80), (0.55, -0.80, -0.10)), curlL=0.6, curlR=0.6, spine=(0, 0, 0), head=(0, 0, 3))),
    (2.0, dict(armL=((0.18, -0.55, -0.80), (-0.55, -0.80, -0.10)), armR=((-0.18, -0.55, -0.80), (0.55, -0.80, -0.10)), curlL=0.6, curlR=0.6, spine=(-1, 0, 1), head=(0, 0, -3))),
    (4.0, dict(armL=((0.18, -0.55, -0.80), (-0.55, -0.80, -0.10)), armR=((-0.18, -0.55, -0.80), (0.55, -0.80, -0.10)), curlL=0.6, curlR=0.6, spine=(0, 0, 0), head=(0, 0, 3))),
])
# seated: full-body (legs bent, hips lowered to the seat) - upper body relaxed, hands on knees
T["sit_idle"] = dict(loop=True, length=4.0, upper_only=False, keys=[
    (0.0, dict(legL=((0.08, -0.95, -0.25), (0.05, -0.1, -1)), legR=((-0.08, -0.95, -0.25), (-0.05, -0.1, -1)),
               armL=((0.25, -0.2, -0.95), (0.10, -0.75, -0.55)), armR=((-0.25, -0.2, -0.95), (-0.10, -0.75, -0.55)), curlL=0.4, curlR=0.4,
               spine=(4, 0, 0), head=(0, 0, 0), hips=(0, 0.12, -0.30))),
    (2.0, dict(legL=((0.08, -0.95, -0.25), (0.05, -0.1, -1)), legR=((-0.08, -0.95, -0.25), (-0.05, -0.1, -1)),
               armL=((0.25, -0.2, -0.95), (0.10, -0.75, -0.55)), armR=((-0.25, -0.2, -0.95), (-0.10, -0.75, -0.55)), curlL=0.4, curlR=0.4,
               spine=(6, 0, 1), head=(2, 0, 3), hips=(0, 0.12, -0.305))),
    (4.0, dict(legL=((0.08, -0.95, -0.25), (0.05, -0.1, -1)), legR=((-0.08, -0.95, -0.25), (-0.05, -0.1, -1)),
               armL=((0.25, -0.2, -0.95), (0.10, -0.75, -0.55)), armR=((-0.25, -0.2, -0.95), (-0.10, -0.75, -0.55)), curlL=0.4, curlR=0.4,
               spine=(4, 0, 0), head=(0, 0, 0), hips=(0, 0.12, -0.30))),
])
T["sit_talk"] = dict(loop=True, length=3.0, upper_only=False, keys=[
    (0.0, dict(legL=((0.08, -0.95, -0.25), (0.05, -0.1, -1)), legR=((-0.08, -0.95, -0.25), (-0.05, -0.1, -1)),
               armL=((0.40, -0.25, -0.85), (0.35, -0.85, -0.25)), armR=((-0.25, -0.2, -0.95), (-0.10, -0.75, -0.55)), curlL=0.2, curlR=0.4,
               spine=(2, 0, 3), head=(2, 0, -2), hips=(0, 0.12, -0.30))),
    (1.5, dict(legL=((0.08, -0.95, -0.25), (0.05, -0.1, -1)), legR=((-0.08, -0.95, -0.25), (-0.05, -0.1, -1)),
               armL=((0.50, -0.30, -0.75), (0.20, -0.95, -0.05)), armR=((-0.30, -0.2, -0.95), (-0.15, -0.8, -0.45)), curlL=0.1, curlR=0.4,
               spine=(0, 0, -3), head=(-2, 0, 3), hips=(0, 0.12, -0.30))),
    (3.0, dict(legL=((0.08, -0.95, -0.25), (0.05, -0.1, -1)), legR=((-0.08, -0.95, -0.25), (-0.05, -0.1, -1)),
               armL=((0.40, -0.25, -0.85), (0.35, -0.85, -0.25)), armR=((-0.25, -0.2, -0.95), (-0.10, -0.75, -0.55)), curlL=0.2, curlR=0.4,
               spine=(2, 0, 3), head=(2, 0, -2), hips=(0, 0.12, -0.30))),
])


def is_upper(n):
    return n.split(".")[0] in UPPER_BONES + SPINE + NECK + ["Head"]


def key_bones(rig, frame, upper_only, hips):
    for pb in rig.pose.bones:
        if upper_only and not is_upper(pb.name) and pb.name != "Body":
            continue
        if pb.name == "Body":
            if hips:      # only own the hips when the action actually moves them (else keep idle/walk hip motion)
                pb.keyframe_insert("location", frame=frame, group=pb.name)
            continue
        pb.keyframe_insert("rotation_quaternion", frame=frame, group=pb.name)


def author(rig, name, spec):
    up = spec.get("upper_only", True)
    hips = (not up) or any("hips" in pose for _, pose in spec["keys"])
    rig.animation_data_create()
    act = bpy.data.actions.new(name)
    rig.animation_data.action = act
    for t, pose in spec["keys"]:
        apply_pose(rig, pose, upper_only=up)
        # Body 'hips' offset is realised by matrix shift; read it back as local location for keying
        key_bones(rig, int(round(t * FPS)) + 1, up, hips)
    act["loop"] = spec["loop"]
    act["length"] = spec["length"]
    act["upper_only"] = up
    act.use_fake_user = True
    if spec["loop"]:
        for fc in fcurves_of(act):
            fc.modifiers.new("CYCLES")
    rig.animation_data.action = None
    return act


def adopt_native_clips():
    """Keep the rig's own authored clips under friendly names."""
    keep = {"Idle_Neutral": "idle", "Idle": "idle_alt", "Walk": "walk", "Run": "run", "Wave": "wave", "Interact": "interact"}
    for act in list(bpy.data.actions):
        short = act.name.split("|")[-1]
        if short in keep:
            act.name = keep[short]
            act["loop"] = short in ("Idle_Neutral", "Idle", "Walk", "Run")
            act["length"] = max((act.frame_range[1] - act.frame_range[0]) / 24.0, 0.5)   # imported at the 24 fps default
            act["native"] = True
            act["upper_only"] = False
            act.use_fake_user = True
            if act["loop"]:
                for fc in fcurves_of(act):
                    if not any(m.type == "CYCLES" for m in fc.modifiers):
                        fc.modifiers.new("CYCLES")
        elif act.name not in T:
            bpy.data.actions.remove(act)


def build_library(actor_blend, out_blend):
    bpy.ops.wm.open_mainfile(filepath=str(actor_blend))
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    adopt_native_clips()
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    rig.animation_data_create()
    rig.animation_data.action = None
    for name, spec in T.items():
        author(rig, name, spec)
        print("[actions_q] authored", name)
    bpy.ops.object.mode_set(mode="OBJECT")
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    print("[actions_q] saved", out_blend, sorted(a.name for a in bpy.data.actions))


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:]
    build_library(a[0], a[1])
