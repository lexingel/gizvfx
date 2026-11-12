# SPDX-License-Identifier: AGPL-3.0-or-later
"""gizvfx.engine - effect registry, rendering of frames, checks and export.

An effect module defines META (a dict) and draw(f, t, o): f is a core.Frame, t in [0, 1], o the merged options (dict-like with attribute access).
META keys: id 'category/name', name, loop (True = t runs 0..1 and wraps; False = a one-shot, t = 0..1 inclusive and it must end empty), duration (s),
size (w, h), pivot (x, y) = where the effect's origin is, options = {name: default}, about (one line), tags."""
import glob, importlib, json, os, pkgutil
import numpy as np
from PIL import Image
from .core import Frame
from .ramps import resolve


class Opts(dict):
    __getattr__ = dict.get


COMMON = {"palette": None, "seed": 1, "light": 1.0, "flip": False, "hard": False, "colors": 24}


def _modules():
    from . import effects
    return [importlib.import_module(f"{effects.__name__}.{m.name}") for m in pkgutil.iter_modules(effects.__path__)]


def registry():
    reg = {}
    for m in _modules():
        for meta in getattr(m, "EFFECTS", [getattr(m, "META", None)]):
            if meta: reg[meta["id"]] = (m, meta)
    from . import spec
    for p in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "recipes", "*.json"))):    # recipes shipped with Gizpix
        m, meta = spec.load(p); reg[meta["id"]] = (m, meta)
    for p in sorted(glob.glob(os.path.join(spec.user_dir(), "*.json"))):                          # recipes you imported (`gizvfx import`)
        try: m, meta = spec.load(p)
        except ValueError: continue
        reg.setdefault(meta["id"], (m, meta))                                                    # a shipped effect is never shadowed
    return reg


def get(eid):
    if eid.lower().endswith(".json"):                                                            # a recipe file of your own
        if not os.path.exists(eid): raise KeyError(f"recipe file '{eid}' not found")
        from . import spec
        try: return spec.load(eid)
        except ValueError as e: raise KeyError(str(e)) from None
    reg = registry()
    if eid in reg: return reg[eid]
    near = [k for k in reg if eid in k or k.split("/")[-1] == eid]
    if len(near) == 1: return reg[near[0]]
    raise KeyError(f"unknown effect '{eid}'" + (f"; did you mean {', '.join(near)}?" if near else "; see `gizvfx list`"))


def options(meta, given=None):
    o = Opts({**COMMON, **meta.get("options", {})})
    for k, v in (given or {}).items():
        if k not in o: raise KeyError(f"'{meta['id']}' has no option '{k}'. Options: {', '.join(sorted(o))}")
        o[k] = v
    return o


def n_frames(meta, frames=None, fps=None):
    return int(frames) if frames else max(2, round(meta["duration"] * (fps or meta.get("fps", 12))))


def render_frame(mod, meta, o, t):
    w, h = meta["size"]; f = Frame(w, h); (meta.get("draw") or mod.draw)(f, t, o); return f


def render(eid, given=None, frames=None, fps=None, bg=None):
    """list of RGBA PIL images, one per frame. Loops sample t = i/n (so frame n would equal frame 0); one-shots sample t = i/(n-1)."""
    mod, meta = get(eid); o = options(meta, given); o.palette = o.palette; n = n_frames(meta, frames, fps); out = []
    for i in range(n):
        t = i / n if meta["loop"] else i / (n - 1)
        im = render_frame(mod, meta, o, t).image(bg=None if o.colors else bg, light=float(o.light), hard=bool(o.hard))
        out.append(im.transpose(Image.FLIP_LEFT_RIGHT) if o.flip else im)
    if not o.colors: return out
    out = limit_colors(out, int(o.colors))                                               # the palette is made from the effect alone, the background is laid under it afterwards
    if bg is None: return out
    return [Image.alpha_composite(Image.new("RGBA", f.size, tuple(bg) + (255,)), f) for f in out]


def limit_colors(frames, n):
    """one shared palette of at most n colours for the whole animation (alpha untouched): the glow no longer makes hundreds of near-duplicate shades"""
    px = np.concatenate([np.array(f)[np.array(f)[..., 3] > 0][:, :3] for f in frames]) if frames else np.zeros((0, 3), np.uint8)
    if len(px) == 0: return frames
    sat = (px.max(1).astype(int) - px.min(1)) > 90                                            # small saturated accents (a red spark in a blue effect) would lose the median cut: count them 3x
    px = np.concatenate([px, px[sat], px[sat]])
    strip = Image.fromarray(px.reshape(-1, 1, 3).astype(np.uint8), "RGB"); pal = strip.quantize(colors=max(2, n), method=0, dither=0)
    out = []
    for f in frames:
        a = f.getchannel("A"); q = f.convert("RGB").quantize(palette=pal, dither=0).convert("RGB"); q.putalpha(a); out.append(q)
    return out


def check(eid, given=None):
    """quality checks; returns a list of problems (empty = clean)"""
    mod, meta = get(eid); o = options(meta, given); n = n_frames(meta); bad = []; w, h = meta["size"]
    a = render_frame(mod, meta, o, 0.0); b = render_frame(mod, meta, o, 0.0)
    if not (np.array_equal(a.rgb, b.rgb) and np.array_equal(a.a, b.a)): bad.append("not deterministic: two renders of the same frame differ")
    if meta["loop"]:
        s = render_frame(mod, meta, o, 1.0)
        if not (np.array_equal(a.a, s.a) and np.array_equal(a.rgb[a.a > 0], s.rgb[s.a > 0])): bad.append("loop does not close: t=1 differs from t=0")
    else:
        e = render_frame(mod, meta, o, 1.0)
        if (e.a > 0).sum() > 0 or (e.light.max() > 0.05): bad.append(f"one-shot does not end empty: {(e.a > 0).sum()} pixels left at t=1")
    edge = 0; first = None; sides = set()
    for i in range(n):
        t = i / n if meta["loop"] else i / (n - 1); f = render_frame(mod, meta, o, t)
        s = {"top": int((f.a[0] > 0).sum()), "bottom": int((f.a[-1] > 0).sum()), "left": int((f.a[:, 0] > 0).sum()), "right": int((f.a[:, -1] > 0).sum())}
        if sum(s.values()) and first is None: first = i
        edge += sum(s.values()); sides |= {k for k, v in s.items() if v}
    if edge and not meta.get("tile"): bad.append(f"{edge} pixels touch the canvas edge over the animation: {', '.join(sorted(sides))} edge, first at frame {first} of {n} (cropped? make the canvas bigger, or move the pivot or `at` away from that edge; a `wave` reaches `length` px behind its crest)")
    return bad


def report(eid, given=None, frames=None):
    """mechanical quality numbers for an effect (an agent still has to LOOK at the contact sheet): returns (metrics dict, flags list)"""
    from scipy.ndimage import convolve
    frames = [np.array(f) for f in (frames if frames is not None else render(eid, given))]; ops = [f[..., 3] > 0 for f in frames]; n = len(frames); H, W = ops[0].shape
    empty = sum(1 for o in ops if not o.any()); lone = []; mesh_n = mesh_d = 0
    for o in ops:
        nb = convolve(o.astype(int), np.ones((3, 3), int), mode="constant") - o; lone.append(int((o & (nb == 0)).sum()))
        a, b, c, d = o[:-1, :-1], o[:-1, 1:], o[1:, :-1], o[1:, 1:]; any_ = a | b | c | d
        mesh_n += int(((a & d & ~b & ~c) | (b & c & ~a & ~d)).sum()); mesh_d += int(any_.sum())
    px = np.concatenate([f[o][:, :3] for f, o in zip(frames, ops) if o.any()]) if any(o.any() for o in ops) else np.zeros((0, 3), np.uint8)
    cols, cnt = np.unique(px, axis=0, return_counts=True) if len(px) else (np.zeros((0, 3)), np.array([0]))
    cen = [np.array(np.nonzero(o)).mean(1) for o in ops if o.any()]; jumps = [float(np.hypot(*(b - a))) for a, b in zip(cen, cen[1:])]
    mx = max(jumps) if jumps else 0.0; med = float(np.median(jumps)) if jumps else 0.0
    m = {"frames": n, "empty_frames": empty, "lone_px_mean": round(sum(lone) / n, 1), "lone_px_max": max(lone), "mesh": round(mesh_n / max(mesh_d, 1), 3),
         "flat": round(float(cnt.max()) / max(len(px), 1), 2), "colors": len(cols), "motion_max_jump": round(mx, 1), "motion_median_jump": round(med, 1)}
    fl = []
    if m["mesh"] > 0.12: fl.append(f"mesh {m['mesh']}: dithering reads as a net at 1x; use `erode`, a stepped glow or a thinner layer instead of `cover`")
    tile = bool(get(eid)[1].get("tile"))
    if m["flat"] > 0.7 and not tile: fl.append(f"flat {m['flat']}: one colour fills most of the effect; widen `depth`, use `lit`, or more ramp steps (`v`)")
    if m["lone_px_mean"] > 14 and not tile: fl.append(f"lone pixels {m['lone_px_mean']} per frame: fewer or larger particles (size >= 2) read better")
    if n > 4 and empty > n * 0.35: fl.append(f"{empty} of {n} frames are empty: shorten `duration` or start earlier")
    if jumps and mx > 4 * med + 10: fl.append(f"motion pops: the centre of the effect jumps {mx:.0f} px in one frame (median {med:.0f}); expected when a shape appears or changes size by design (a growing blob); otherwise check overlapping windows and shared `seed`")
    rec = get(eid)[1].get("recipe")
    if rec:                                                                                      # an option nobody uses is a typo or a leftover
        txt = json.dumps({k: v for k, v in rec.items() if k not in ("options", "_dir")})
        for k in rec.get("options", {}):
            if k != "palette" and ("$" + k) not in txt: fl.append(f"option '{k}' is never used: no layer has \"${k}\" (typo, or a leftover?)")
    if m["colors"] > 40: fl.append(f"{m['colors']} colours: raise nothing, lower `-o colors=` or avoid layered glows")
    return m, fl
