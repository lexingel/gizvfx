# SPDX-License-Identifier: AGPL-3.0-or-later
"""gizvfx.fix - check an effect and repair what can be repaired mechanically, then write the files and say what is left for you.
Recipe level : a cropped effect gets a bigger canvas (pivot moved with it; layers are relative to the pivot).
Frame level  : 1 px holes are filled, lone pixels removed (only when flagged), more than 40 colours are limited to 24,
               a one-shot that does not end empty fades out over its last frames.
Left alone (reported with the fix to make by hand): loop that does not close, mesh dithering, flat colour, empty frames, motion pops."""
import json, os, shutil
import numpy as np
from PIL import Image
from . import engine
from .export import write_all, DARK

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0


def _nb(a, dy, dx): return np.roll(np.roll(a, dy, 0), dx, 1)


def _pinholes(frames):
    out = []; n = 0
    for f in frames:
        a = np.array(f); op = a[..., 3] > 0
        hole = ~op & _nb(op, 1, 0) & _nb(op, -1, 0) & _nb(op, 0, 1) & _nb(op, 0, -1); hole[0] = hole[-1] = False; hole[:, 0] = hole[:, -1] = False
        for y, x in np.argwhere(hole):
            nb = np.array([a[y - 1, x], a[y + 1, x], a[y, x - 1], a[y, x + 1]]); a[y, x] = nb[np.argmax(nb[:, 3])]      # the most opaque neighbour: no new colours
        n += int(hole.sum()); out.append(Image.fromarray(a, "RGBA"))
    return out, n


def _lone(frames):
    out = []; n = 0
    for f in frames:
        a = np.array(f); op = a[..., 3] > 0; cnt = sum(_nb(op, dy, dx).astype(int) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx)
        lone = op & (cnt == 0); a[lone] = 0; n += int(lone.sum()); out.append(Image.fromarray(a, "RGBA"))
    return out, n


def _fade_out(frames, k=3):
    """dither the last k frames away (4x4 Bayer), the very last one empty: a pop becomes a short fade"""
    out = list(frames); n = len(out)
    for j in range(1, k + 1):
        i = n - k + j - 1
        if i < 1: continue
        a = np.array(out[i]); keep = 1 - j / k; h, w = a.shape[:2]
        m = BAYER[np.arange(h)[:, None] % 4, np.arange(w)[None, :] % 4] < keep; a[~m] = 0; out[i] = Image.fromarray(a, "RGBA")
    return out


def _frame_problems(frames, meta):
    bad = []; arr = [np.array(f)[..., 3] > 0 for f in frames]
    if not meta["loop"] and arr[-1].any(): bad.append(f"one-shot does not end empty: {int(arr[-1].sum())} pixels left in the last frame")
    per = [{"top": int(o[0].sum()), "bottom": int(o[-1].sum()), "left": int(o[:, 0].sum()), "right": int(o[:, -1].sum())} for o in arr]
    edge = sum(sum(p.values()) for p in per)
    if edge and not meta.get("tile"):
        sides = sorted({k for p in per for k, v in p.items() if v}); first = next(i for i, p in enumerate(per) if sum(p.values()))
        bad.append(f"{edge} pixels touch the canvas edge over the animation: {', '.join(sides)} edge, first at frame {first} of {len(per)}")
    return bad


def _pad_recipe(meta, out, name, padx=8, pady=8):
    r = {k: v for k, v in meta["recipe"].items() if k != "_dir"}
    r["size"] = [meta["size"][0] + 2 * padx, meta["size"][1] + 2 * pady]; r["pivot"] = [meta["pivot"][0] + padx, meta["pivot"][1] + pady]
    r.setdefault("id", meta["id"]); dest = os.path.join(out, name + ".fixed.json"); os.makedirs(out, exist_ok=True)
    src = meta["recipe"].get("_dir")
    for l in r.get("layers", []):                                                                # stamp PNGs sit next to the recipe: bring only those
        fn = l.get("image") if l.get("type") == "stamp" else None
        if fn and src and os.path.exists(os.path.join(src, fn)) and os.path.abspath(src) != os.path.abspath(out): shutil.copy(os.path.join(src, fn), out)
    with open(dest, "w", encoding="utf-8") as fh: json.dump(r, fh, indent=1)
    return dest


def fix(eid, given=None, out="gizvfx_fix", name=None, scale=4, painted_style=None):
    """returns (done, problems, notes, written paths): problems are what a user must fix (cropping, does not end empty, loop seam, painted check); notes are advisory (mesh, flat colour, motion pops, empty frames, lone pixels)"""
    m, meta = engine.get(eid); name = name or meta["id"].split("/")[-1]; path = eid; done = []; capped = False
    if "recipe" in meta and not meta.get("tile") and any("canvas edge" in x for x in _frame_problems(engine.render(path, given), meta)):
        w0, h0 = meta["size"]; px0, py0 = meta["pivot"]; padx, pady = min(64, (256 - w0) // 2), min(64, (256 - h0) // 2)    # draw it once on a big canvas, measure what it really covers, cut the canvas to that
        if padx > 0 or pady > 0:
            big = _pad_recipe(meta, out, name + ".big", max(padx, 0), max(pady, 0)); _, bm = engine.get(big); bf = engine.render(big, given)
            al = np.zeros(bf[0].size[::-1], bool)
            for f in bf: al |= np.array(f)[..., 3] > 0
            ys, xs = np.nonzero(al)
            if len(xs):
                m_ = 8; x0, x1, y0, y1 = (int(v) for v in (max(xs.min() - m_, 0), min(xs.max() + m_ + 1, al.shape[1]), max(ys.min() - m_, 0), min(ys.max() + m_ + 1, al.shape[0])))
                x0, y0 = min(x0, max(padx, 0)), min(y0, max(pady, 0)); x1, y1 = max(x1, max(padx, 0) + w0), max(y1, max(pady, 0) + h0)      # never smaller than the original
                if (x1 - x0, y1 - y0) != (w0, h0) and max(x1 - x0, y1 - y0) <= 256:
                    r = {k: v for k, v in bm["recipe"].items() if k != "_dir"}; r["size"] = [x1 - x0, y1 - y0]; r["pivot"] = [bm["pivot"][0] - x0, bm["pivot"][1] - y0]; r["id"] = meta["id"]
                    path = os.path.join(out, name + ".fixed.json")
                    with open(path, "w", encoding="utf-8") as fh: json.dump(r, fh, indent=1)
                    m, meta = engine.get(path); done.append(f"canvas changed to {meta['size'][0]}x{meta['size'][1]} (it was cropped; this is what the effect really covers plus 8 px)")
            try: os.remove(big)
            except OSError: pass
            if any("canvas edge" in x for x in _frame_problems(engine.render(path, given), meta)): capped = True
        else: capped = True
    frames = engine.render(path, given); tile = bool(meta.get("tile"))
    if not tile:
        fixed, n = _pinholes(frames); solid = sum(int((np.array(f)[..., 3] > 0).sum()) for f in frames)
        if n and n > 0.01 * solid: done.append(f"{n} one-pixel holes left alone: that many is dithering, not damage")      # a stippled fill must stay stippled
        elif n: frames = fixed; done.append(f"{n} one-pixel holes filled")
    _, fl = engine.report(path, given, frames)
    if any(x.startswith("lone pixels") for x in fl) and not tile:
        frames, n = _lone(frames); done.append(f"{n} lone pixels removed")
    px = np.concatenate([np.array(f)[np.array(f)[..., 3] > 0][:, :3] for f in frames])
    if len(np.unique(px, axis=0)) > 40: frames = engine.limit_colors(frames, 24); done.append("colours limited to 24")
    if not meta["loop"] and np.array(frames[-1])[..., 3].any(): frames = _fade_out(frames); done.append("faded out over the last 3 frames (it did not end empty)")
    mt, fl = engine.report(path, given, frames)
    problems = (["the canvas is already at the 256 px limit and the effect still touches the edge: make the effect smaller, or move the pivot away from that edge"] if capped else []) + _frame_problems(frames, meta) + ["seam: " + b for b in engine.check(path, given) if "loop does not close" in b or "deterministic" in b]; notes = list(fl)
    if painted_style and "recipe" not in meta: notes.append(f"painted {painted_style}: skipped, this effect is drawn by Python code, not a recipe")
    elif painted_style:
        from . import painted
        problems += [f"painted {painted_style}: {b}" for b in painted.check(path, scale, painted_style)]
    o = engine.options(meta, given or {}); fps = meta.get("fps", 12)
    paths = write_all(frames, out, name, meta, dict(o), fps, scale=scale, bg=DARK)
    rp = os.path.join(out, name + "_fix.txt")
    with open(rp, "w", encoding="utf-8") as fh:
        fh.write(f"{meta['id']}\nfixed:\n" + "".join(f"  - {x}\n" for x in done or ["nothing needed fixing"]) + "to fix by hand:\n" + "".join(f"  - {x}\n" for x in problems or ["nothing"]) + "notes (advisory, e.g. a motion pop that is meant):\n" + "".join(f"  - {x}\n" for x in notes or ["none"]))
    return done, problems, notes, paths + ([path] if path != eid else []) + [rp]
