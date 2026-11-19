"""Face acting for MPFB 'default' rigs: emotes, blinks, Rhubarb visemes. Runs inside Blender.
Every control is a small armature-space offset (metres, +Z up, -Y toward the viewer, +X = character's left)
converted to each bone's local rest frame, so one definition fits every actor (any age/size)."""
import math

from mathutils import Vector

L, R = "L", "R"

# bone -> armature-space delta for a unit-strength control. {s} is replaced by L / R, sx = +1/-1 outward.
CONTROLS = {
    "brow_up":       {"oculi01.{s}": (0, 0, 0.009), "oculi02.{s}": (0, 0, 0.009)},
    "brow_down":     {"oculi01.{s}": (0, 0, -0.007), "oculi02.{s}": (0, 0, -0.005)},
    "brow_inner_up": {"oculi01.{s}": (0, 0, 0.010), "oculi02.{s}": (0, 0, -0.002)},
    "brow_angry":    {"oculi01.{s}": (-0.003, 0, -0.009), "oculi02.{s}": (0, 0, 0.002)},
    "blink":         {"orbicularis03.{s}": (0, 0, -0.0075), "orbicularis04.{s}": (0, 0, 0.0035)},
    "lids_wide":     {"orbicularis03.{s}": (0, 0, 0.0045), "orbicularis04.{s}": (0, 0, -0.0025)},
    "smile":         {"levator05.{s}": (0.003, 0, 0.006), "risorius03.{s}": (0.006, 0, 0.004),
                      "oris06.{s}": (0.004, 0, 0.004), "oris04.{s}": (0.002, 0, 0.003)},
    "frown":         {"levator05.{s}": (-0.001, 0, -0.004), "risorius03.{s}": (-0.002, 0, -0.006),
                      "oris06.{s}": (-0.002, 0, -0.004)},
    "cheek_squint":  {"orbicularis04.{s}": (0, 0, 0.005), "levator06.{s}": (0, 0, 0.004)},
}
# controls applied to both sides get mirrored (x delta flips sign on the R side)

# jaw angle + lip shaping per Rhubarb viseme: (jaw_deg, lip_corner_in (pucker 0..1), lip_corner_out (wide 0..1))
VISEMES = {
    "X": (0.0, 0.0, 0.0),    # idle / closed
    "A": (0.0, 0.0, 0.0),    # M B P (lips pressed)
    "B": (6.0, 0.0, 0.5),    # slightly open, teeth (K S T EE)
    "C": (15.0, 0.0, 0.2),   # open (EH AE)
    "D": (24.0, 0.0, 0.1),   # wide open (AA)
    "E": (13.0, 0.7, 0.0),    # rounded (AO ER)
    "F": (6.0, 1.0, 0.0),    # puckered (UW OW W)
    "G": (4.0, 0.0, 0.3),    # F V
    "H": (14.0, 0.0, 0.1),    # L
}

EMOTES = {
    "neutral":   {},
    "happy":     {"smile": 0.9, "cheek_squint": 0.5, "brow_up": 0.15},
    "sad":       {"frown": 0.8, "brow_inner_up": 0.9},
    "angry":     {"brow_angry": 1.0, "frown": 0.35, "lids_wide": 0.1},
    "surprised": {"brow_up": 1.0, "lids_wide": 1.0},
    "worried":   {"brow_inner_up": 0.7, "frown": 0.3},
    "smug":      {"smile": 0.4, "brow_up": 0.2, "cheek_squint": 0.3},
    "tired":     {"brow_down": 0.3, "frown": 0.25, "blink": 0.35},
    "thinking":  {"brow_up": 0.3, "brow_inner_up": 0.2},
}

_cache = {}


def _local_delta(rig, bone_name, delta):
    b = rig.data.bones[bone_name]
    return b.matrix_local.to_3x3().inverted() @ Vector(delta)


def bone_offsets(rig, controls):
    """controls: {control_name: strength} -> {bone_name: local Vector} summed over both sides."""
    out = {}
    for ctrl, k in controls.items():
        if abs(k) < 1e-4:
            continue
        for tmpl, delta in CONTROLS[ctrl].items():
            for side, sx in ((L, 1), (R, -1)):
                name = tmpl.format(s=side)
                if name not in rig.data.bones:
                    continue
                d = (delta[0] * sx * k, delta[1] * k, delta[2] * k)
                v = _local_delta(rig, name, d)
                out[name] = out.get(name, Vector()) + v
    return out


def viseme_pose(rig, viseme, intensity=1.0):
    jaw, pucker, wide = VISEMES.get(viseme, VISEMES["X"])
    ctrl = {}
    off = {}
    jb = rig.pose.bones["jaw"]
    # jaw: rotate about its local X; sign chosen so tail swings down/back (verified in test render)
    jaw_rot = (math.radians(jaw * intensity), 0, 0)
    for side, sx in ((L, 1), (R, -1)):
        for nm, d in ((f"oris06.{side}", (-0.004 * pucker * sx + 0.004 * wide * sx, -0.003 * pucker, 0)),
                      (f"oris04.{side}", (-0.003 * pucker * sx + 0.003 * wide * sx, -0.002 * pucker, 0.0015 * wide))):
            if nm in rig.data.bones:
                off[nm] = _local_delta(rig, nm, d)
    return jaw_rot, off


def apply_face(rig, emote=None, viseme="X", blink=0.0, emote_k=1.0, viseme_k=1.0):
    """Set the face pose at the current frame (no keying). Returns list of keyed-property targets."""
    ctrl = {}
    for k, v in EMOTES.get(emote or "neutral", {}).items():
        ctrl[k] = ctrl.get(k, 0) + v * emote_k
    if blink > 0:
        ctrl["blink"] = max(ctrl.get("blink", 0), blink)
    offs = bone_offsets(rig, ctrl)
    jaw_rot, voffs = viseme_pose(rig, viseme, viseme_k)
    for nm, v in voffs.items():
        offs[nm] = offs.get(nm, Vector()) + v
    touched = set(offs)
    for pb in rig.pose.bones:
        if pb.name.startswith(("oculi", "orbicularis", "levator", "risorius", "oris", "temporalis")):
            pb.location = offs.get(pb.name, Vector())
    jb = rig.pose.bones["jaw"]
    jb.rotation_mode = "XYZ"
    jb.rotation_euler = jaw_rot
    return touched


FACE_ANIM_BONES = ("oculi", "orbicularis", "levator", "risorius", "oris", "temporalis")


def key_face(rig, frame):
    for pb in rig.pose.bones:
        if pb.name.startswith(FACE_ANIM_BONES):
            pb.keyframe_insert("location", frame=frame, group="face")
    rig.pose.bones["jaw"].keyframe_insert("rotation_euler", frame=frame, group="face")
