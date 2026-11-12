# SPDX-License-Identifier: AGPL-3.0-or-later
"""GizVFX - draw pixel-art effects (fire, explosions, hits, lightning, magic, pickups, weather) from code. No reference image, no AI, no network.

  python gizvfx.py list [WORD]                       the effects, with a one-line description
  python gizvfx.py show ID                           options, size, duration of one effect
  python gizvfx.py render ID [-o key=value ...] [--frames N] [--fps N] [--scale S] [--out DIR] [--name N] [--bg #rrggbb|none] [--no-gif] [--no-sheet] [--no-contact]
  python gizvfx.py schema [LAYER]                    the recipe language: every layer type and key (describe your own effect as JSON)
  python gizvfx.py import FILE.json                  a recipe someone sent you: validate, limits, render, report, then keep it in ~/.gizvfx/recipes
  python gizvfx.py painted ID [--scale 4] [--style ink|watercolor|comic|chalk|linocut|stencil|glitch|lineart]   the same recipe drawn smooth at 4x with a real alpha channel (layers: brush hatch halftone burst speedlines splat glow disc ring)
  python gizvfx.py recipe ID                         print a shipped recipe as JSON: copy it, change it, render the file
  (ID can also be the path of your own recipe, e.g. my_effect.json)
  python gizvfx.py check [ID ...] [--report]   (--report adds numbers + flags: mesh dithering, flat colour, lone pixels, empty frames, motion pops)                  quality checks (deterministic, loops close, one-shots end empty, nothing cropped)
  python gizvfx.py fix ID|FILE.json ...|--all [--out DIR] [--painted STYLE]   check, repair what can be repaired (cropped canvas, pinholes, lone pixels, too many colours, a one-shot that does not end empty), write the files + NAME_fix.txt, list what is left
  python gizvfx.py gallery out.png [--scale S]       one picture with a mid-animation frame of every effect
Options (-o): palette=ice (a ramp name, or hex colours dark to bright: '#102,#215,#43a'), seed=7, light=0.6, flip=true, plus the effect's own (see `show`)."""
import argparse, json, os, sys
from . import engine
from .ramps import RAMPS
from .export import write_all, contact_sheet, DARK


def _val(s):
    try: return json.loads(s)
    except ValueError: return s


def _opts(items):
    d = {}
    for it in items or []:
        if "=" not in it: raise SystemExit(f"gizvfx: option '{it}' must be key=value")
        k, v = it.split("=", 1); d[k.strip()] = _val(v.strip())
    return d


def _bg(s):
    if s is None: return DARK
    if s.lower() in ("none", "transparent"): return None
    from .core import hex2rgb
    return hex2rgb(s if len(s.lstrip("#")) == 6 else "".join(c * 2 for c in s.lstrip("#")))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == "selftest":
            from .selftest import run; return run()
        if cmd == "list":
            w = rest[0].lower() if rest else ""; cat = None
            for eid, (m, meta) in sorted(engine.registry().items()):
                if w and w not in (eid + " " + meta["name"] + " " + meta.get("about", "") + " " + " ".join(meta.get("tags", []))).lower(): continue
                if eid.split("/")[0] != cat: cat = eid.split("/")[0]; print(f"\n[{cat}]")
                print(f"  {eid:26s} {'loop' if meta['loop'] else 'once'} {meta['duration']:>4}s {meta['size'][0]}x{meta['size'][1]:<4} {meta['about']}")
            print("\nPalettes: " + ", ".join(sorted(RAMPS))); return 0
        if cmd == "palettes":
            print(", ".join(sorted(RAMPS))); return 0
        if cmd == "schema":
            from .spec import schema_text; print(schema_text(rest[0] if rest else None)); return 0
        if cmd == "import":                                                                      # someone sent you a recipe
            from .spec import import_recipe
            dest, meta, problems, flags = import_recipe(rest[0])
            print(f"{meta['id']}: {len(meta['recipe']['layers'])} layers, {meta['size'][0]}x{meta['size'][1]}, {'loop' if meta['loop'] else 'one-shot'}")
            for x in problems: print("  PROBLEM " + x)
            for x in flags: print("  FLAG " + x)
            print(f"kept as {dest}" + ("  (it has problems: fix before using)" if problems else "")); return 1 if problems else 0
        if cmd == "recipe":                                                                      # print a recipe to copy and edit
            m, meta = engine.get(rest[0])
            if "recipe" not in meta: raise KeyError(f"'{rest[0]}' is drawn by Python code, not a recipe. Recipes: " + ", ".join(k for k, (_, mt) in sorted(engine.registry().items()) if "recipe" in mt))
            print(json.dumps(meta["recipe"], indent=1)); return 0
        if cmd == "show":
            m, meta = engine.get(rest[0]); print(f"{meta['id']}  {meta['name']}  ({'loop' if meta['loop'] else 'one-shot'}, {meta['duration']} s, {meta['size'][0]}x{meta['size'][1]} px, {meta.get('fps', 12)} fps)\n{meta['about']}")
            print("options:", json.dumps({**engine.COMMON, **meta.get("options", {})})); return 0
        if cmd == "check":
            rep = "--report" in rest; rest = [r for r in rest if r != "--report"]
            ids = rest or sorted(engine.registry()); bad = 0
            for eid in ids:
                if rep:
                    mt, fl = engine.report(eid); print(f"{eid}: " + ", ".join(f"{k} {v}" for k, v in mt.items()))
                    for x in fl: print("  FLAG " + x)
                p = engine.check(eid); bad += bool(p); print(("ok   " if not p else "FAIL ") + eid + ("" if not p else ": " + "; ".join(p)))
            return 1 if bad else 0
        if cmd == "fix":                                                                         # check, repair what can be repaired, write the files, list what is left
            ap = argparse.ArgumentParser(prog="gizvfx fix"); ap.add_argument("ids", nargs="*"); ap.add_argument("--all", action="store_true"); ap.add_argument("-o", "--opt", action="append")
            ap.add_argument("--out", default="gizvfx_fix"); ap.add_argument("--scale", type=int, default=4); ap.add_argument("--painted", choices=["ink", "watercolor", "comic", "chalk", "linocut", "stencil", "glitch", "lineart"]); a = ap.parse_args(rest)
            from .fix import fix
            ids = sorted(engine.registry()) if a.all else a.ids; left_n = 0
            if not ids: raise ValueError("fix: give an effect id, a recipe .json, or --all")
            for eid in ids:
                done, left, paths = fix(eid, _opts(a.opt), out=a.out, scale=a.scale, painted_style=a.painted); left_n += bool(left)
                print(f"{eid}: " + ("; ".join(done) if done else "nothing to fix") + (f"  | LEFT: {len(left)}" if left else "  | clean"))
                for x in left: print("   - " + x)
            return 1 if left_n else 0
        if cmd == "gallery":
            ap = argparse.ArgumentParser(prog="gizvfx gallery"); ap.add_argument("out"); ap.add_argument("--scale", type=int, default=2); a = ap.parse_args(rest)
            frames = []
            for eid in sorted(engine.registry()):
                fr = engine.render(eid, bg=DARK); frames.append(fr[len(fr) // 3])
            from PIL import Image
            W = max(f.width for f in frames); H = max(f.height for f in frames); frames = [f if f.size == (W, H) else _centre(f, W, H) for f in frames]
            contact_sheet(frames, a.out, scale=a.scale); print(a.out); return 0
        if cmd == "render":
            ap = argparse.ArgumentParser(prog="gizvfx render"); ap.add_argument("id"); ap.add_argument("-o", "--opt", action="append"); ap.add_argument("--frames", type=int); ap.add_argument("--fps", type=int)
            ap.add_argument("--scale", type=int, default=4); ap.add_argument("--out", default="gizvfx_out"); ap.add_argument("--name"); ap.add_argument("--bg"); ap.add_argument("--no-gif", action="store_true")
            ap.add_argument("--no-sheet", action="store_true"); ap.add_argument("--no-contact", action="store_true"); a = ap.parse_args(rest)
            m, meta = engine.get(a.id); given = _opts(a.opt); o = engine.options(meta, given); fps = a.fps or meta.get("fps", 12)
            frames = engine.render(a.id, given, frames=a.frames, fps=fps)
            name = a.name or meta["id"].split("/")[-1]
            for p in write_all(frames, a.out, name, meta, dict(o), fps, scale=a.scale, gif=not a.no_gif, sheet=not a.no_sheet, contact=not a.no_contact, bg=_bg(a.bg)): print(p)
            return 0
        if cmd == "painted":                                                                     # the same recipe, drawn smooth at S times the size (brush hatch halftone glow disc ring)
            ap = argparse.ArgumentParser(prog="gizvfx painted"); ap.add_argument("id"); ap.add_argument("-o", "--opt", action="append"); ap.add_argument("--frames", type=int); ap.add_argument("--fps", type=int)
            ap.add_argument("--scale", type=int, default=4); ap.add_argument("--out", default="gizvfx_out"); ap.add_argument("--name"); ap.add_argument("--bg"); ap.add_argument("--intensity", type=float, default=1.0); ap.add_argument("--hold", type=int, default=2); ap.add_argument("--style", default="ink", choices=["ink", "watercolor", "comic", "chalk", "linocut", "stencil", "glitch", "lineart"]); a = ap.parse_args(rest)
            from . import painted
            m, meta = engine.get(a.id); given = _opts(a.opt); o = engine.options(meta, given); fps = a.fps or meta.get("fps", 12)
            frames = painted.render(a.id, given, frames=a.frames, fps=fps, scale=a.scale, style=a.style, opts={"intensity": a.intensity, "hold": a.hold}); name = (a.name or meta["id"].split("/")[-1]) + "_" + ("painted" if a.style == "ink" else a.style)
            m2 = dict(meta); m2["pivot"] = tuple(v * a.scale for v in meta["pivot"])
            for pth in write_all(frames, a.out, name, m2, dict(o), fps, scale=1, contact=False, bg=_bg(a.bg)): print(pth)
            return 0
    except (KeyError, ValueError) as e:                                                          # recipe errors arrive as ValueError from the draw call too
        print(f"gizvfx: {e.args[0] if e.args else e}", file=sys.stderr); return 2
    print(f"gizvfx: unknown command '{cmd}'. Commands: list, show, palettes, schema, import, recipe, render, painted, check, fix, gallery, selftest", file=sys.stderr); return 2


def _centre(f, W, H):
    from PIL import Image
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); c.alpha_composite(f, ((W - f.width) // 2, (H - f.height) // 2)); return c
