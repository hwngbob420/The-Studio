"""Small Blender-version helper shared by the V2 engine (the V1 MPFB action library was retired in V2 - see actions_q.py)."""


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
