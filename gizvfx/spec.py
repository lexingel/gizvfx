# SPDX-License-Identifier: AGPL-3.0-or-later
"""gizvfx.spec - describe an effect as data (JSON), no Python needed.

A recipe is a JSON object: canvas, timing, a palette and a list of LAYERS drawn in order (later = on top). Each layer is one building
block (glow, disc, ring, star, particles, blob, bolt, rays, orbit, beam, arc) with a time window `t` and values that animate:
  3            a fixed number
  [3, 0]       goes from 3 to 0 across the layer's window (shaped by `ease`)
  {"wave":[lo,hi,cycles]}   pulses lo..hi `cycles` times per loop (closes a loop exactly)
  "$radius"    the recipe's option of that name (so `-o radius=30` works)
Coordinates are pixels from the recipe's pivot, y down. Everything random comes from the seed, so the same recipe gives the same frames.
Part of GizVFX; `python gizvfx.py schema` lists every layer and key."""
import difflib, json, math, os, hashlib, shutil, re
from types import SimpleNamespace
import numpy as np
from .core import BAYER, Frame, TAU, Rng, clamp, lerp, seg, ramp_at, out_expo, out_quart, in_quad, smooth, disc_mask, hex2rgb
from .ramps import resolve
from .kit import star, jagged

EASE = {"linear": lambda p: p, "out": out_quart, "expo": out_expo, "in": in_quad, "smooth": smooth}
DEFAULTS = {"name": "Custom effect", "about": "", "loop": False, "duration": 1.0, "fps": 12, "size": [96, 96], "palette": "fire", "options": {}, "tags": [], "layers": [], "style": {}, "palettes": {}}
ALLOWED_TOP = set(DEFAULTS) | {"id", "pivot", "_dir"}
STYLE_KEYS = {"outline": "'auto' or '#rrggbb': 1 px outline around everything drawn", "rim": "[dx, dy] light direction: lit edge", "shadow": "[dx, dy] offset: a hard shadow in the darkest palette colour"}
COMMON = {"t": "time window [start, end] in 0..1 (default [0, 1]); the layer draws only inside it", "at": "[x, y] from the pivot; [[x0,y0],[x1,y1]] to move on a line; three or more points = a smooth curve through them",
          "palette": "ramp name or hex list for this layer (default: the recipe palette; 'main' = the recipe palette, which -o palette= changes)",
          "color": "one fixed colour '#rrggbb' instead of a palette", "v": "ramp position 0..1 (dark..bright), number or [from, to] over the layer's life",
          "ease": "linear | out | expo | in | smooth: how [from, to] values move; or a list, one name per key step: [\"out\", \"linear\", \"in\"]", "spin": "[radius, turns]: circles around its path (a spiral when it also moves)", "hold": "true = keep drawing the end state after the window", "wobble": "[ax, ay, cycles]: the layer sways around its path (whole cycles close a loop): snaking wisps, swaying columns", "smear": "[length, taper]: a trail of fading, shrinking copies of the layer along its own path (length = fraction of the window, taper = size of the oldest copy 0..1). Sword smears, comet tails, wisp tails",
          "erode": "(all layers except blob has its own) px eaten from the edge, animatable: the clean dissolve", "outline": "'#rrggbb' or 'auto' (darkest palette colour): a 1 px outline around the drawn layer", "rim": "[dx, dy] light direction, e.g. [-1, -1]: the edge facing the light takes a bright rim colour",
          "seed": "layers with the same number draw the same random shape (give it to the second layer when one body continues in another layer)"}
SCHEMA = {
    "glow": {"radius": "px, animatable", "strength": "0..1+, animatable (try {wave:[0.4,0.8,3]})", "steps": "brightness bands (default 4)", "squash": "0.1..1: flat light on the floor (1 = round)"},
    "disc": {"radius": "px", "mode": "core (bright middle) | lit (lit from top-left, smoke/stone)", "bias": "shifts shading dark(-)..bright(+)", "cover": "0..1 dithered translucency"},
    "ring": {"radius": "px", "thick": "px", "squash": "1 = circle, 0.4 = flat ellipse on the floor; animatable, e.g. [1, 0.15, 1] for a spinning coin", "cover": "0..1 dither", "arc": "[a0, a1] degrees: only part of the ring"},
    "star": {"size": "px (spike length)", "arms": "4 | 6 | 8", "thin": "0.05..0.4 body width"},
    "particles": {"mode": "burst (all fly out from the window start) | stream (endless, loop-safe)", "count": "int", "area": "[w, h] spawn box", "angle": "[a0, a1] degrees, 0 = right, 90 = down, -90 = up",
                  "speed": "[lo, hi] px travelled over a particle's life", "life": "[lo, hi] fraction of the window (burst) or of the cycle (stream)", "cycles": "stream: repeats per loop (whole number)",
                  "stagger": "burst: spread the births over this fraction of the window", "gravity": "px of downward pull at end of life (negative = rises)", "lob": "true = a parabola: launched along `angle` at `speed`, lands back at its spawn height at the end of its life (fountains, thrown debris)", "sway": "px of side wobble",
                  "size": "[start, end] px", "shape": "dot | streak | star | bubble (hollow, pops) | shard (sliver)", "streak": "streak length px", "shade": "flat | core", "travel": "ease of the flight: out | linear | in | expo", "cover": "[c0, c1] dither fade over life", "target": "[x, y] from the pivot: every particle travels from its spawn point to here instead of flying along `angle`", "drop": "true = each particle stays where the layer was when it was born: a trail behind a layer that moves along `at` (use with mode stream, one-shots; a loop would need the emitter to return)", "curve": "one number: px of sideways bow of that path (with `target`), random per particle"},
    "blob": {"mode": "lump (default) | ring (puffs on the `spread` ellipse: ground dust, smoke rings; `drift` px outward, `stagger`) | flame (puffs up a swaying spine: `height`, `radius` = [base, tip-ish], `flicker`, `sway`, `cycles`, `jitter`)", "count": "int discs merged into one body", "height": "flame: px", "flicker": "flame: reshapes per window (default 5)", "sway": "flame: px", "cycles": "flame: sways per window (whole)", "jitter": "flame: px", "drift": "ring: px outward, animatable", "stagger": "0..0.9: puffs start growing at different moments", "spread": "[w, h] px", "radius": "[lo, hi] px", "scale": "0..1+ animatable: grow and shrink the whole body", "rise": "px upward, animatable",
             "depth": "band width px (bigger = bands further in)", "lit": "[dx, dy] direction of the light, e.g. [-1, -1] = top-left (sphere-like shading)", "lit_strength": "0..1, default 0.3", "bias": "dark(-)..bright(+) animatable: cool a fireball with [0.2, -0.6]", "erode": "px eaten from the edge, animatable ([0, 10] dissolves it; better than cover)", "cover": "0..1 dither"},
    "bolt": {"from": "[x, y]", "to": "[x, y]", "width": "px, animatable", "grow": "fraction of the window spent striking from `from` to `to`", "flicker": "reshapes per window (default 6)",
             "rough": "0.1..0.5 zigzag (default 0.28)", "depth": "subdivisions (default 4)", "branches": "int side forks", "glow": "radius of the light along the bolt", "rim": "'#rrggbb' lighter edge under the stroke (cracks on dark ground)"},
    "rays": {"count": "int", "inner": "px from centre, animatable", "length": "px, animatable", "width": "px at the root", "rotate": "degrees over the window", "jitter": "0..1 random length", "squash": "0.1..1: rays lying on the floor (1 = round)"},
    "orbit": {"count": "int", "radius": "px, animatable", "squash": "1 = circle", "turns": "whole turns over the window (whole number for loops)", "size": "px, animatable", "trail": "dots behind each one", "shade": "flat | core"},
    "beam": {"from": "[x, y]", "to": "[x, y]", "width": "px, animatable", "tip": "width at the far end", "extend": "fraction of the window spent growing from `from` to `to`", "shade": "flat = one colour, no stripes", "core": "0..0.9 share of the width at the brightest step (default 0.45)"},
    "wave": {"height": "px of the crest above the water line, animatable (the wave rises)", "curl": "0..1, animatable: 0 = a steep face, 1 = the lip curls over a hollow barrel", "length": "px of the back slope behind the crest (default 1.5 x height)", "dir": "1 = breaks to the right, -1 = to the left", "foam": "px of bright foam along the crest and lip (default 2, 0 = none)", "deep": "px of water below `at` (default 4)", "depth": "px of the dark edge line (default 2)", "lit": "[x, y] light direction (default [-1, -1])", "bias": "shift the colour, animatable (default -0.35: a mid-blue body, light crest)", "cover": "0..1 dither"},
    "poly": {"shape": "crystal | shard | rock | diamond | arrow | heart (ready-made outlines)", "points": "[[x, y], ...] your own outline, px from `at` (3 to 24 points)", "rotate": "degrees, animatable (a full turn [0, 360] over a loop closes it)", "scale": "animatable", "anchor": "center (default) | base: the lowest point sits on `at`",
             "depth": "band width px (default 4)", "lit": "[dx, dy] light direction (default [-1, -1])", "lit_strength": "0..1, default 0.35", "bias": "dark(-)..bright(+)", "cover": "0..1 dither"},
    "stamp": {"image": "a PNG next to the recipe file, at most 32x32 px (your own sprite: a coin, a leaf)", "scale": "whole number 1 to 4", "flip": "true = mirror", "rotate": "0 | 90 | 180 | 270"},
    "include": {"recipe": "id of a recipe (`gizvfx list`) or the path of a .json file; its time is stretched over this layer's window and it is drawn at this layer's `at`", "options": "{name: value} for that recipe's options"},
    "funnel": {"height": "px, animatable", "base": "half-width at the bottom px", "top": "half-width at the top px", "stripes": "swirl stripes around it (default 3)", "twist": "how much the stripes lean up the column (default 0.15)",
               "turns": "whole turns over the window (loops close)", "lean": "px the column sways sideways", "fade": "0..1 dithers the top away (looks like mesh: prefer `erode`)", "profile": "half-widths bottom to top as keys, e.g. [3, 4, 9, 22] (replaces base/top)", "bend": "sideways offsets bottom to top as keys, e.g. [0, 5, -3, 6]", "ripple": "[amp, cycles]: the width pulses up the column"},
    "brush": {"path": "[[x, y], ...] 3+ points from `at`: the stroke follows a smooth curve through them", "width": "px at the fattest, animatable", "tail": "how much of the path stays visible behind the head, 0..1 (default 0.7)",
              "dry": "0..1: the old end breaks into bristle streaks (default 0.6)", "lanes": "bristle lanes across the stroke (default 7)", "head": "0.05..0.95 where along the stroke it is fattest (default 0.4); 0.25 = fat at the old end and a point at the head (claws)", "core": "0..1 share of the width that takes the brightest ramp colour (default 0.35)"},
    "hatch": {"size": "[rx, ry] half size of the ellipse it fills", "angle": "line direction in degrees (default 45)", "spacing": "px between lines (default 3)", "tone": "0..1 share of the lines that are drawn, animatable (default 0.6)",
              "cross": "0..1: a second set of lines at 90 degrees, drawn where the tone is above it (default 0 = none)", "fade": "0..1 how much the tone falls off along `fade_dir` degrees (default 0)", "fade_dir": "degrees (default 0 = to the right)"},
    "halftone": {"size": "[rx, ry] half size of the ellipse it fills", "cell": "px between dots (default 4)", "angle": "grid angle in degrees (default 45)", "tone": "0..1 how big the dots are, animatable (default 0.6)",
                 "fade": "0..1 how much the dots shrink along `fade_dir` degrees (default 0)", "fade_dir": "degrees (default 0 = to the right)"},
    "burst": {"radius": "px of the spikes, animatable", "inner": "0.2..0.9 inner radius as a share of `radius` (default 0.55)", "points": "number of spikes (default 10)", "rotate": "degrees, animatable", "jitter": "0..0.5 how uneven the spikes are (default 0.18)",
               "depth": "pixel renderer: band width px (default 3)", "outline": "pixel renderer: false = no dark outline"},
    "speedlines": {"count": "number of lines (default 10)", "length": "px (default 24)", "width": "px (default 1)", "radial": "true = lines fly out from the centre, false (default) = parallel lines", "r0": "radial: px from the centre where they start (default 10)",
                   "angle": "parallel: direction of travel in degrees (default 0 = right)", "spread": "parallel: px across the lines (default 30)", "travel": "px they move while the layer plays (default 12)"},
    "splat": {"radius": "px of the blob, animatable", "drops": "number of flying droplets (default 9)", "reach": "droplets fly out to this many radii (default 2.0)", "drips": "number of drips hanging down (default 3)", "drip_len": "px (default 14)", "depth": "pixel renderer: band width px (default 2.5)"},
    "arc": {"radius": "px", "thick": "px, animatable", "sweep": "[a0, a1] degrees the head travels", "tail": "length of the tail as a fraction of the sweep (default 0.6)"},
}


_OPT = re.compile(r"^(-?)\$(\w+)(?:([*+\-/])(-?[0-9]*\.?[0-9]+))?$")


def sub(x, o):
    """replace "$name" strings by the option's value, recursively"""
    if isinstance(x, str) and x.lstrip("-").startswith("$"):
        m = _OPT.match(x)                                                              # "$reach", "$reach*0.55", "-$height", "$cloud+4", "$w-6", "$w/2"
        if not m: raise ValueError(f"'{x}': an option is written $name, optionally with a sign in front and one of * + - / and a number after: \"$w*0.5\", \"-$h\", \"$w+4\"")
        sign, name, op, num = m.groups()
        if name not in o: raise KeyError(f"'{x}' is not an option of this recipe (options: {', '.join(sorted(o))})")
        v = o[name]
        if (sign or op) and not isinstance(v, (int, float)) or isinstance(v, bool) and (sign or op): raise ValueError(f"'{x}': option '{name}' is {v!r}, not a number, so it cannot be negated or calculated with")
        if sign: v = -v
        if op:
            n = float(num)
            if op == "/" and n == 0: raise ValueError(f"'{x}': division by zero")
            v = v * n if op == "*" else v + n if op == "+" else v - n if op == "-" else v / n
        return v
    if isinstance(x, list): return [sub(i, o) for i in x]
    if isinstance(x, dict): return {k: sub(v, o) for k, v in x.items()}
    return x


_SEG = [None]                                                                          # per-segment ease names of the layer being drawn (ease given as a list)


def val(x, p, t=0.0):
    if isinstance(x, dict):
        w = (list(x["wave"]) + [1, 0])[:4]; return lerp(w[0], w[1], 0.5 + 0.5 * math.sin(TAU * (t * w[2] + w[3])))
    if isinstance(x, (list, tuple)):                                                   # [a, b] or [a, b, c, ...]: evenly spaced keys over the window
        n = len(x) - 1; pos = clamp(p) * n; i = min(int(pos), n - 1); u = pos - i; se = _SEG[0]
        if se: u = EASE[se[min(i, len(se) - 1)]](u)
        return lerp(x[i], x[i + 1], u)
    return x


def pt(x, p):
    """a point, or a path: two points = a line, three or more = a smooth curve through them (Catmull-Rom)"""
    if not isinstance(x[0], (list, tuple)): return (x[0], x[1])
    if len(x) == 2: return (lerp(x[0][0], x[1][0], p), lerp(x[0][1], x[1][1], p))
    n = len(x) - 1; pos = clamp(p) * n; i = min(int(pos), n - 1); u = pos - i; P0, P1, P2, P3 = x[max(i - 1, 0)], x[i], x[i + 1], x[min(i + 2, n)]
    return tuple(0.5 * (2 * P1[k] + (-P0[k] + P2[k]) * u + (2 * P0[k] - 5 * P1[k] + 4 * P2[k] - P3[k]) * u * u + (-P0[k] + 3 * P1[k] - 3 * P2[k] + P3[k]) * u ** 3) for k in (0, 1))


def _efn(d):
    e = d.get("ease", "linear"); return EASE["linear"] if isinstance(e, list) else EASE[e]


def rng2(x, default):
    x = default if x is None else x; return (x, x) if not isinstance(x, (list, tuple)) else x


def _ramp(d, main, roles=None):
    if "color" in d: return [hex2rgb(d["color"])]
    pal = d.get("palette")
    if isinstance(pal, str) and pal.startswith("@"):                                   # a role defined in the recipe's "palettes"
        if not roles or pal[1:] not in roles: raise KeyError(f"palette '{pal}' is not defined in the recipe's palettes ({', '.join(roles or {}) or 'none'})")
        pal = roles[pal[1:]]
    return main if pal in (None, "main") else resolve(pal, "fire")


# ---- layers --------------------------------------------------------------------------------------------------------------
def L_glow(f, d, c):
    r = val(d.get("radius", 20), c.e); k = val(d.get("strength", 0.6), c.e, c.t)
    if r > 0 and k > 0: f.glow(c.ox, c.oy, r, ramp_at(c.ramp, c.v(0.6)), k, steps=int(d.get("steps", 4)), sq=val(d.get("squash", 1), c.e))


def L_disc(f, d, c):
    r = val(d.get("radius", 6), c.e) * c.sc
    if r > 0: f.disc(c.ox, c.oy, r, c.ramp, mode=d.get("mode", "core"), cover=val(d.get("cover", 1), c.e), bias=val(d.get("bias", 0), c.e))


def L_ring(f, d, c):
    r = val(d.get("radius", 20), c.e); th = val(d.get("thick", 2), c.e) * c.sc; sq = val(d.get("squash", 1), c.e); cv = val(d.get("cover", 1), c.e)
    if r <= 0 or th < 0.5: return
    th = max(th, 1.0)                                                                  # a ring thinner than a pixel would draw as dots
    if sq == 1:
        arc = d.get("arc"); f.ring(c.ox, c.oy, r, th, c.ramp, v=c.v(0.8) if "v" in d else None, cover=cv, arc=None if arc is None else (math.radians(arc[0]), math.radians(arc[1]))); return
    g = f._grid(c.ox, c.oy, r + th)                                                    # a flat ring: distance measured on the squashed plane
    if g is None: return
    x0, x1, y0, y1, xx, yy = g; dd = np.hypot(xx - c.ox, (yy - c.oy) / sq); te = max(th, 1.0 / sq)    # at least 1 px tall
    m = np.abs(dd - r) <= te / 2
    if cv < 1: m &= cv > np.tile(BAYER, (f.h // 4 + 1, f.w // 4 + 1))[y0:y1, x0:x1]
    pos = np.clip(0.5 + (dd - r) / te + ((c.v(0.5) - 0.5) if "v" in d else 0.3), 0, 0.999)
    cols = np.array(c.ramp, np.uint8)[(pos * len(c.ramp)).astype(int)]; f.rgb[y0:y1, x0:x1][m] = cols[m]; f.a[y0:y1, x0:x1][m] = 255


def L_star(f, d, c):
    s = val(d.get("size", 14), c.e) * c.sc
    if s > 1: star(f, c.ox, c.oy, s, c.ramp, arms=int(d.get("arms", 4)), thin=d.get("thin", 0.14), v=c.v(1.0))


def particles_live(d, c):
    """the live particles of one frame: [(age, x, y, angle, size, cover, v)] in the pixel coordinates of the canvas (c.ox, c.oy already added); shared by the pixel and the painted renderer"""
    n = int(d.get("count", 20)); stream = d.get("mode", "burst") == "stream"; ax, ay = rng2(d.get("area"), [0, 0]); a0, a1 = rng2(d.get("angle"), [0, 360])
    s0, s1 = rng2(d.get("speed"), [10, 30]); l0, l1 = rng2(d.get("life"), [0.5, 1.0]); z0, z1 = rng2(d.get("size"), [2, 0]); grav = d.get("gravity", 0); sway = d.get("sway", 0)
    cyc = d.get("cycles", 1); stag = clamp(d.get("stagger", 0.3), 0, 0.9); ease = EASE[d.get("travel", "out")]; shape = d.get("shape", "dot"); streak = d.get("streak", 6)
    v0, v1 = rng2(d.get("v"), [0.9, 0.3]); c0, c1 = rng2(d.get("cover"), [1, 1]); r = c.rng; live = []; tgt = d.get("target"); curve = d.get("curve", 0); px0, py0 = c.px0, c.py0
    drop = d.get("drop"); t0_, t1_ = d.get("t", [0, 1])
    if drop: at_, ef_ = d.get("at", [0, 0]), _efn(d); cur = pt(at_, ef_(c.p))                # `drop`: a particle stays where the layer was when it was born (a trail behind something that moves along `at`)
    for i in range(n):
        ang = math.radians(r.u(a0, a1)); sp = r.u(s0, s1); lf = max(r.u(l0, l1), 1e-3); ph = r.u(0, 1); bx = r.u(-0.5, 0.5) * ax; by = r.u(-0.5, 0.5) * ay; sw = r.u(0, TAU)
        age = ((c.t * cyc + (i + ph * 0.5) / n) % 1.0) / lf if stream else (c.p - ph * stag) / (lf * (1 - stag))     # (1 - stag): every burst particle is over by p = 1
        if age < 0 or age >= 1: continue
        if drop:
            pb = seg(c.t - ((c.t * cyc + (i + ph * 0.5) / n) % 1.0) / cyc, t0_, t1_) if stream else ph * stag; bp = pt(at_, ef_(pb)); bx += bp[0] - cur[0]; by += bp[1] - cur[1]
        if d.get("lob"): x = c.ox + bx + math.cos(ang) * sp * age; y = c.oy + by + math.sin(ang) * sp * age * (1 - age)
        elif tgt:                                                                      # fly from the spawn point to the target, bowing sideways by `curve`
            sx0, sy0 = c.ox + bx, c.oy + by; tx, ty = c.ox + tgt[0] - (c.ox - px0), c.oy + tgt[1] - (c.oy - py0); ang = math.atan2(ty - sy0, tx - sx0); L = math.hypot(tx - sx0, ty - sy0) or 1.0; e2 = ease(age)
            bow = curve * math.sin(math.pi * age) * math.sin(sw); x = lerp(sx0, tx, e2) - (ty - sy0) / L * bow; y = lerp(sy0, ty, e2) + (tx - sx0) / L * bow
        else: dist = sp * ease(age); x = c.ox + bx + math.cos(ang) * dist + sway * math.sin(sw + age * TAU); y = c.oy + by + math.sin(ang) * dist + grav * age * age
        size = lerp(z0, z1, age) * c.sc; cv = lerp(c0, c1, age); vv = lerp(v0, v1, age)
        if size > 0.2: live.append((age, x, y, ang, size, cv, vv))
    return live


def L_particles(f, d, c):
    live = particles_live(d, c); shape = d.get("shape", "dot"); streak = d.get("streak", 6)
    for age, x, y, ang, size, cv, vv in sorted(live, reverse=True):                    # oldest first, so the young and hot ones sit on top
        col = ramp_at(c.ramp, vv)
        if shape == "star":                                                            # a plus-shaped twinkle; size 3 = 1 px arms, 5 = 2 px arms
            arm = int(size / 2); f.put(x, y, c.ramp[-1] if len(c.ramp) > 1 else col)
            for k in range(1, arm + 1):
                for dx, dy in ((k, 0), (-k, 0), (0, k), (0, -k)): f.put(x + dx, y + dy, col)
        elif shape == "bubble":                                                        # a hollow ring that grows, then pops into four dots
            if age < 0.8: f.ring(x, y, max(size / 2, 1.2), 1.0, [col])
            else:
                for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)): f.put(x + dx * size * 0.7, y + dy * size * 0.7, col)
        elif shape == "shard":                                                         # a tapered sliver pointing along its flight
            f.tapered(x, y, x + math.cos(ang) * size * 1.6, y + math.sin(ang) * size * 1.6, max(size * 0.6, 1), 0.5, [col])
        elif shape == "streak": f.tapered(x, y, x - math.cos(ang) * streak * (1 - age * 0.7), y - math.sin(ang) * streak * (1 - age * 0.7), max(size, 1), 1, [col], cover=cv)
        elif size < 1.6: f.dput(x, y, col, cv)
        elif d.get("shade", "flat") == "core": f.disc(x, y, size / 2, c.ramp, mode="core", cover=cv, bias=vv - 0.5)
        else: f.disc(x, y, size / 2, [col], cover=cv)


def L_blob(f, d, c, rec=None):
    dm = disc_mask if rec is None else (lambda m_, x_, y_, r_: rec.append((x_, y_, r_)))                  # rec: a list that collects the discs (the painted renderer draws them smooth)
    n = int(d.get("count", 8)); mode = d.get("mode", "lump"); sx, sy = rng2(d.get("spread"), [10, 10]); lo, hi = rng2(d.get("radius"), [4, 8]); sc = val(d.get("scale", 1), c.e) * c.sc
    rise = val(d.get("rise", 0), c.e); stag = clamp(d.get("stagger", 0.3 if mode == "ring" else 0), 0, 0.9); m = f.mask(); r = c.rng
    if c.loop: stag = 0                                                                # stagger runs on window progress: it would break a loop seam
    if mode == "flame":                                                                # puffs stacked up a swaying spine, shrinking to a tip; reshaped `flicker` times per window
        H = val(d.get("height", 30), c.e) * c.sc; fl = max(1, int(d.get("flicker", 5))); rr = Rng(c.seed * 13 + int(c.p * fl) % fl); sw = d.get("sway", 3); cyc = d.get("cycles", 1)
        for i in range(n):
            u = (i + 0.5) / n; x = c.ox + sw * u * math.sin(TAU * c.p * cyc + rr.u(0, 0.6)) + rr.u(-1, 1) * d.get("jitter", 1.2) * u; rad = max(0.0, lerp(hi, 0.8, u ** 0.8) * sc * rr.u(0.85, 1.1))
            dm(m, x, c.oy - rise - u * H, rad)
    else:
        for i in range(n):
            dx, dy, rr = r.u(-1, 1), r.u(-1, 1), r.u(lo, hi); dl = r.u(0, stag) if stag > 0 else 0.0
            s_i = sc * (clamp((c.e - dl) / (1 - dl)) if stag > 0 else 1.0)              # stagger: each puff starts growing at its own moment
            if mode == "ring":                                                         # puffs on an ellipse (ground dust, smoke rings), each drifting outward by `drift` px
                a = TAU * (i + dx * 0.2) / n; dr = val(d.get("drift", 0), c.e)
                dm(m, c.ox + math.cos(a) * (sx + dr), c.oy + math.sin(a) * (sy + dr * sy / max(sx, 1)) - rise, rr * s_i)
            else: dm(m, c.ox + dx * sx * sc, c.oy + dy * sy * sc - rise, rr * sc)
    if rec is not None: return
    er = val(d.get("erode", 0), c.e)
    if er > 0 and m.any():                                                             # eat the body away from its edge: a clean, banded dissolve
        from scipy.ndimage import distance_transform_edt
        m = m & (distance_transform_edt(np.pad(m, 1))[1:-1, 1:-1] > er)
    grad = None
    if d.get("lit"):                                                                   # light from this side: brighter that way, darker the other
        lx, ly = d["lit"]; k = d.get("lit_strength", 0.3); yy, xx = np.mgrid[0:f.h, 0:f.w]; R = max(sx, sy, hi) * max(sc, 0.2) + hi
        grad = k * ((xx + 0.5 - c.ox) * lx + (yy + 0.5 - c.oy) * ly) / (math.hypot(lx, ly) * R)
    f.fill(m, c.ramp, depth=d.get("depth", 5), grad=grad, bias=val(d.get("bias", 0), c.e), cover=val(d.get("cover", 1), c.e))


def bolt_paths(d, c):
    """[(points, width)] of one frame of a lightning bolt (the main stroke first, then the branches), or [] ; shared by the pixel and the painted renderer"""
    x0, y0 = pt(d.get("from", [0, -30]), c.e); x1, y1 = pt(d.get("to", [0, 30]), c.e); w = val(d.get("width", 3), c.e)
    if w <= 0: return []
    grow = d.get("grow", 0); g = out_expo(seg(c.p, 0, grow)) if grow > 0 else 1.0; k = int(c.p * d.get("flicker", 6)) % max(1, int(d.get("flicker", 6))); r = Rng(c.seed * 7919 + k)
    pts = jagged(r, c.ox + x0, c.oy + y0, c.ox + lerp(x0, x1, g), c.oy + lerp(y0, y1, g), depth=int(d.get("depth", 4)), rough=d.get("rough", 0.28))
    paths = [(pts, w)]
    for _ in range(int(d.get("branches", 0))):
        bx, by = pts[r.i(len(pts) // 4, len(pts) * 3 // 4)]; ln = math.hypot(x1 - x0, y1 - y0) * r.u(0.2, 0.4); a = math.atan2(y1 - y0, x1 - x0) + r.u(-1.0, 1.0)
        paths.append((jagged(r, bx, by, bx + math.cos(a) * ln, by + math.sin(a) * ln, depth=3), max(1, w / 2)))
    return paths


def L_bolt(f, d, c):
    x0, y0 = pt(d.get("from", [0, -30]), c.e); x1, y1 = pt(d.get("to", [0, 30]), c.e); w = val(d.get("width", 3), c.e); paths = bolt_paths(d, c)
    if not paths: return
    if d.get("glow"): f.glow(c.ox + lerp(x0, x1, 0.5), c.oy + lerp(y0, y1, 0.5), d["glow"], ramp_at(c.ramp, 0.7), 0.5)
    if d.get("rim"):                                                                   # a lighter edge under the stroke: cracks read on dark ground
        rc = hex2rgb(d["rim"])
        for pl, ww in paths:
            for a, b in zip(pl, pl[1:]): f.line(a[0], a[1], b[0], b[1], rc, width=max(1, int(ww)) + 2)
    for pl, ww in paths:
        for a, b in zip(pl, pl[1:]): f.line(a[0], a[1], b[0], b[1], ramp_at(c.ramp, c.v(0.65)), width=max(1, int(ww)))
    for pl, ww in paths:
        if ww >= 2 and not d.get("rim") and not d.get("color"):                         # a bright 1 px core down the thick strokes
            for a, b in zip(pl, pl[1:]): f.line(a[0], a[1], b[0], b[1], c.ramp[-1], width=1)


def L_rays(f, d, c):
    n = int(d.get("count", 8)); r0 = val(d.get("inner", 4), c.e); ln = val(d.get("length", 12), c.e); rot = math.radians(val(d.get("rotate", 0), c.e)); jit = d.get("jitter", 0); wd = d.get("width", 2)
    if ln <= 0.5: return
    for i in range(n):
        a = TAU * i / n + rot; L = ln * (1 - jit * c.rng.u(0, 1)); sq = val(d.get("squash", 1), c.e); x0, y0 = c.ox + math.cos(a) * r0, c.oy + math.sin(a) * r0 * sq
        f.tapered(x0, y0, x0 + math.cos(a) * L, y0 + math.sin(a) * L * sq, wd, 1, c.ramp, v=c.v(0.8))


def L_orbit(f, d, c):
    n = int(d.get("count", 5)); R = val(d.get("radius", 20), c.e); sq = val(d.get("squash", 1), c.e); turns = d.get("turns", 1); size = val(d.get("size", 3), c.e) * c.sc; trail = int(d.get("trail", 0))
    if size <= 0.2 or R < 0: return
    for i in range(n):
        for j in range(trail + 1):
            a = TAU * (i / n + c.p * turns) - j * 0.16; s = size * (1 - j / (trail + 1)); x, y = c.ox + math.cos(a) * R, c.oy + math.sin(a) * R * sq
            col = ramp_at(c.ramp, c.v(0.9) - 0.5 * j / (trail + 1))
            if s < 1.6: f.put(x, y, col)
            elif d.get("shade", "flat") == "core": f.disc(x, y, s / 2, c.ramp, mode="core")
            else: f.disc(x, y, s / 2, [col])


def L_beam(f, d, c):
    x0, y0 = pt(d.get("from", [0, 0]), c.e); x1, y1 = pt(d.get("to", [30, 0]), c.e); w0 = val(d.get("width", 4), c.e) * c.sc; w1 = val(d.get("tip", d.get("width", 4)), c.e) * c.sc
    ex = d.get("extend", 0); g = out_expo(seg(c.p, 0, ex)) if ex > 0 else 1.0; ax, ay = c.ox + x0, c.oy + y0; bx, by = c.ox + lerp(x0, x1, g), c.oy + lerp(y0, y1, g)
    if max(w0, w1) < 0.4: return
    gr = f._grid((ax + bx) / 2, (ay + by) / 2, math.hypot(bx - ax, by - ay) / 2 + max(w0, w1))      # one distance field along the segment: bands run along the beam, no stamped discs
    if gr is None: return
    gx0, gx1, gy0, gy1, xx, yy = gr; vx, vy = bx - ax, by - ay; u = np.clip(((xx - ax) * vx + (yy - ay) * vy) / max(vx * vx + vy * vy, 1e-6), 0, 1)
    dd = np.hypot(xx - (ax + vx * u), yy - (ay + vy * u)); hw = (w0 + (w1 - w0) * u) / 2; m = dd <= hw + 0.25; q = np.clip(1 - dd / np.maximum(hw, 1e-6), 0, 1)
    top = c.v(0.95)
    pos = np.full(q.shape, min(top, 0.999)) if d.get("shade") == "flat" else np.clip(q / max(1 - d.get("core", 0.45), 1e-3), 0, 1) * min(top, 0.999)
    cols = np.array(c.ramp, np.uint8)[(pos * len(c.ramp)).astype(int).clip(0, len(c.ramp) - 1)]
    f.rgb[gy0:gy1, gx0:gx1][m] = cols[m]; f.a[gy0:gy1, gx0:gx1][m] = 255


def L_arc(f, d, c):
    R = d.get("radius", 22); th = val(d.get("thick", 6), c.e) * c.sc; a0, a1 = d.get("sweep", [-60, 60]); tr = d.get("tail", 0.6); head = lerp(a0, a1, out_quart(c.e)); tail = max(a0, head - tr * (a1 - a0)); S = 6
    if th <= 0.4 or head <= tail: return
    for s in range(S):
        f.ring(c.ox, c.oy, R, th * (0.25 + 0.75 * (s + 1) / S), c.ramp, v=min(0.99, c.v(0.5) + 0.5 * (s + 1) / S) if "v" not in d else c.v(0.8), arc=(math.radians(lerp(tail, head, s / S)), math.radians(lerp(tail, head, (s + 1) / S))))


def L_brush(f, d, c):
    """an ink-brush stroke: a head runs along a curve, the width swells and ends in a point, and the old end dries into bristle streaks (lanes that drop out)"""
    path = d["path"]; W = val(d.get("width", 8), c.e) * c.sc; tail = d.get("tail", 0.7); dry = d.get("dry", 0.6); nl = int(d.get("lanes", 7)); core = d.get("core", 0.35)
    if W < 0.8 or c.e <= 0: return
    pw = math.log(0.5) / math.log(clamp(d.get("head", 0.4), 0.05, 0.95))                                                  # where along the stroke it is fattest: low = fat near the old end, high = fat at the head
    hr = c.e * (1 + tail); s0 = hr - tail; rr = [Rng(c.seed * 7 + j).u(0, 1) for j in range(nl)]                       # the head runs on past the end of the path and the tail catches up: the stroke ends empty. Each lane has its own staying power
    L = sum(math.hypot(a - b, e - g) for (a, e), (b, g) in zip(path[:-1], path[1:])); n = int(L * 2.2) + 2
    for i in range(n + 1):
        q = i / n; u = lerp(s0, hr, q)                                                                             # q: 0 at the old end, 1 at the head
        if u < 0 or u > 1: continue
        x, y = pt(path, u); x2, y2 = pt(path, min(1.0, u + 0.01)); x1, y1 = pt(path, max(0.0, u - 0.01)); dx, dy = x2 - x1, y2 - y1; ln = math.hypot(dx, dy) or 1.0; nx, ny = -dy / ln, dx / ln
        w = W * math.sin(math.pi * q ** pw) ** 0.8; hw = w / 2
        if hw < 0.45: continue
        for k in range(-int(math.ceil(hw)), int(math.ceil(hw)) + 1):
            sv = k / max(hw, 1e-6)
            if abs(sv) > 1.02: continue
            lane = min(nl - 1, int((sv + 1) / 2 * nl))
            if rr[lane] < dry * (1 - q) ** 1.2: continue                                                           # a dry lane lets go
            v = 0.25 + 0.7 * (1 - abs(sv)) / max(core, 1e-3) if abs(sv) < 1 - core else 0.25 + 0.15 * (1 - abs(sv)); v = min(v, 0.99) + (c.v(0.5) - 0.5)
            f.put(c.ox + x + nx * k, c.oy + y + ny * k, ramp_at(c.ramp, clamp(v * (0.55 + 0.45 * q), 0, 0.999)))


def L_hatch(f, d, c):
    """parallel lines inside an ellipse, as many as the tone says (line n is drawn when its own random number is below the tone): shading made of lines, not of dither"""
    rx, ry = d.get("size", [14, 10]); rx *= c.sc; ry *= c.sc; ang = math.radians(d.get("angle", 45)); sp = max(1.5, d.get("spacing", 3) * c.sc); tone = val(d.get("tone", 0.6), c.e); cross = d.get("cross", 0); fade = d.get("fade", 0); fd = math.radians(d.get("fade_dir", 0))
    if tone <= 0.02: return
    yy, xx = np.mgrid[0:f.h, 0:f.w]; px = xx + 0.5 - c.ox; py = yy + 0.5 - c.oy; m = (px / max(rx, 1) ) ** 2 + (py / max(ry, 1)) ** 2 <= 1.0
    g = (px * math.cos(fd) + py * math.sin(fd)) / max(rx, ry, 1); tl = np.clip(tone * (1 - fade * (0.5 + 0.5 * g)), 0, 1)
    col = ramp_at(c.ramp, clamp(c.v(0.3), 0, 0.999)); rh = np.array([Rng(c.seed * 11 + j).u(0, 1) for j in range(512)])
    for k, a in enumerate((ang, ang + math.pi / 2) if cross > 0 else (ang,)):
        u = px * math.cos(a) + py * math.sin(a); li = np.floor(u / sp).astype(int); on = (np.mod(u, sp) < 1.0) & (rh[np.mod(li, 512)] < (tl if k == 0 else np.clip(tl - cross, 0, 1) * 2))
        sel = m & on; f.rgb[sel] = col; f.a[sel] = 255


def L_halftone(f, d, c):
    """a grid of dots whose size follows the tone (comic halftone): shading made of dots, with a size that can fall off in one direction"""
    rx, ry = d.get("size", [14, 10]); rx *= c.sc; ry *= c.sc; cell = max(2.0, d.get("cell", 4) * c.sc); ang = math.radians(d.get("angle", 45)); tone = val(d.get("tone", 0.6), c.e); fade = d.get("fade", 0); fd = math.radians(d.get("fade_dir", 0))
    if tone <= 0.02: return
    yy, xx = np.mgrid[0:f.h, 0:f.w]; px = xx + 0.5 - c.ox; py = yy + 0.5 - c.oy; m = (px / max(rx, 1)) ** 2 + (py / max(ry, 1)) ** 2 <= 1.0
    u = px * math.cos(ang) + py * math.sin(ang); v = -px * math.sin(ang) + py * math.cos(ang); cu = (np.floor(u / cell) + 0.5) * cell; cv = (np.floor(v / cell) + 0.5) * cell
    cx = cu * math.cos(ang) - cv * math.sin(ang); cy = cu * math.sin(ang) + cv * math.cos(ang); g = (cx * math.cos(fd) + cy * math.sin(fd)) / max(rx, ry, 1)
    tl = np.clip(tone * (1 - fade * (0.5 + 0.5 * g)), 0, 1); r = cell * 0.5 * np.sqrt(tl); sel = m & (np.hypot(u - cu, v - cv) <= r)
    f.rgb[sel] = ramp_at(c.ramp, clamp(c.v(0.3), 0, 0.999)); f.a[sel] = 255


# ---- shapes shared by the pixel and the painted renderer (plain numbers, px from the layer's `at`) -------------------------------------------
def burst_poly(d, e, seed):
    n = max(4, int(d.get("points", 10))); R = val(d.get("radius", 18), e); ri = clamp(d.get("inner", 0.55), 0.1, 0.95); rot = math.radians(val(d.get("rotate", 0), e)); jit = d.get("jitter", 0.18); r = Rng(seed * 5 + 1)
    if R < 1: return []
    jr = [1 + r.u(-jit, jit) for _ in range(n)]                                         # the same unevenness every frame: the burst does not boil
    return [((R if k % 2 == 0 else R * ri) * jr[k // 2 % n] * math.cos(rot + math.pi * k / n), (R if k % 2 == 0 else R * ri) * jr[k // 2 % n] * math.sin(rot + math.pi * k / n)) for k in range(2 * n)]


def speed_segs(d, e, seed):
    """[(x0, y0, x1, y1)] lines that grow, move and shrink away (a one-shot ends empty)"""
    n = int(d.get("count", 10)); L = d.get("length", 24); r = Rng(seed * 9 + 2); k = math.sin(math.pi * e) ** 0.7; out = []
    if k < 0.05: return out
    if d.get("radial"):
        r0 = d.get("r0", 10); tr = d.get("travel", 12) * e
        for i in range(n):
            a = 2 * math.pi * (i + r.u(-0.3, 0.3)) / n; l = L * r.u(0.55, 1.0) * k; s0 = r0 + tr * r.u(0.6, 1.0); out.append((s0 * math.cos(a), s0 * math.sin(a), (s0 + l) * math.cos(a), (s0 + l) * math.sin(a)))
    else:
        a = math.radians(d.get("angle", 0)); ca, sa = math.cos(a), math.sin(a); sp_ = d.get("spread", 30); tr = d.get("travel", 12) * e
        for i in range(n):
            off = (i + 0.5) / n * sp_ - sp_ / 2 + r.u(-1, 1); l = L * r.u(0.45, 1.0) * k; head = tr + r.u(-4, 4); out.append((ca * (head - l) - sa * off, sa * (head - l) + ca * off, ca * head - sa * off, sa * head + ca * off))
    return out


def splat_shapes(d, e, seed):
    """('disc', x, y, r) and ('line', x0, y0, x1, y1, w): a blob that bursts out, flying droplets and drips that run, then shrinks away"""
    R = val(d.get("radius", 12), e); r = Rng(seed * 3 + 7); g = out_expo(seg(e, 0, 0.35)); k = 1 - smooth(seg(e, 0.72, 1.0)); out = []
    if R < 0.8 or k <= 0.02: return out
    out.append(("disc", 0, 0, R * (0.35 + 0.65 * g) * k))
    for i in range(3): out.append(("disc", r.u(-0.55, 0.55) * R * g * k, r.u(-0.55, 0.55) * R * g * k, R * r.u(0.45, 0.7) * g * k))
    for i in range(int(d.get("drops", 9))):
        a = r.u(0, TAU); dist = R * lerp(1.1, d.get("reach", 2.0), r.u(0, 1)) * g; rad = max(0.0, R * r.u(0.10, 0.28) * (1.3 - dist / (R * d.get("reach", 2.0) + 1e-6)) * k)
        if rad > 0.4: out.append(("disc", dist * math.cos(a), dist * math.sin(a) * 0.8, rad))
    nd = int(d.get("drips", 3)); dl = d.get("drip_len", 14)
    for i in range(nd):
        x = (i + 0.5) / max(nd, 1) * R * 1.4 - R * 0.7 + r.u(-1.5, 1.5); ln = dl * r.u(0.5, 1.0) * seg(e, 0.2, 0.85) * k
        if ln > 1: out.append(("line", x, R * 0.5, x, R * 0.5 + ln, max(1.4, R * 0.16) * k))
    return out


def L_burst(f, d, c):
    from PIL import Image, ImageDraw
    P = burst_poly(d, c.e, c.seed)
    if not P: return
    im = Image.new("L", (f.w, f.h), 0); ImageDraw.Draw(im).polygon([(c.ox + x * c.sc, c.oy + y * c.sc) for x, y in P], fill=255); m = np.array(im) > 127
    if not m.any(): return
    from scipy.ndimage import binary_dilation
    if d.get("outline", True): ol = binary_dilation(m) & ~m; f.rgb[ol] = c.ramp[0]; f.a[ol] = 255
    f.fill(m, c.ramp, depth=d.get("depth", 3), bias=c.v(0.5) - 0.5)


def L_speedlines(f, d, c):
    w = max(2.0, d.get("width", 1) * c.sc * 1.6)
    for x0, y0, x1, y1 in speed_segs(d, c.e, c.seed): f.tapered(c.ox + x0, c.oy + y0, c.ox + x1, c.oy + y1, 0.5, w, c.ramp, v=clamp(c.v(0.85), 0.3, 0.99))                 # a wedge: fat at the head, a point at the tail


def L_splat(f, d, c):
    m = f.mask(); shapes = splat_shapes(d, c.e, c.seed); first = None; nd = 0; drops = []
    for sh in shapes:
        if sh[0] == "disc":
            nd += 1; first = first or sh
            if nd <= 4: disc_mask(m, c.ox + sh[1], c.oy + sh[2], sh[3])                                      # the blob: one big disc and three that join it
            else: drops.append(sh)                                                                           # flying droplets are small: drawn as shaded discs, not filled by depth
        else:
            x0, y0, x1, y1, w = sh[1:]; n = int(max(abs(x1 - x0), abs(y1 - y0))) * 2 + 1
            for i in range(n + 1): disc_mask(m, c.ox + lerp(x0, x1, i / n), c.oy + lerp(y0, y1, i / n), w / 2)
    if m.any():
        from scipy.ndimage import binary_dilation
        ol = binary_dilation(m) & ~m; f.rgb[ol] = c.ramp[1 if len(c.ramp) > 2 else 0]; f.a[ol] = 255
        f.fill(m, c.ramp, depth=d.get("depth", 3.5), bias=c.v(0.5) - 0.5 - 0.3)                              # the brightest step is kept for the gloss spot
    for sh in drops: f.disc(c.ox + sh[1], c.oy + sh[2], max(0.9, sh[3]), c.ramp, mode="lit", bias=-0.1)
    if first and first[3] > 3: f.disc(c.ox + first[1] - first[3] * 0.32, c.oy + first[2] - first[3] * 0.36, max(1.0, first[3] * 0.2), [c.ramp[-1]], mode="core")


def L_funnel(f, d, c):
    H = int(val(d.get("height", 40), c.e)); wb = val(d.get("base", 6), c.e); wt = val(d.get("top", 18), c.e); st = d.get("stripes", 3); tw = d.get("twist", 0.15)
    lean = d.get("lean", 0); fade = d.get("fade", 0); prof = d.get("profile"); bend = d.get("bend"); rip = d.get("ripple")
    for k in range(max(H, 0)):
        u = k / max(H - 1, 1); w = val(prof, u) if prof else lerp(wb, wt, u); xc = c.ox + lean * math.sin(u * math.pi + c.p * TAU) + (val(bend, u) if bend else 0); y = c.oy - k
        if rip: w += rip[0] * math.sin(k * 0.3 + c.p * TAU * rip[1])
        w = round(w, 3)                                                                 # rounding noise must not flip a pixel column at the loop seam
        for x in range(-int(w), int(w) + 1):
            sx = clamp(x / max(w, 1e-6), -1, 1); ph = math.asin(sx) + k * tw + c.p * d.get("turns", 1) * TAU
            v = (0.3 + 0.55 * (0.5 + 0.5 * math.sin(st * ph))) * (1 - 0.45 * sx * sx) + (c.v(0.5) - 0.5)
            f.dput(xc + x, y, ramp_at(c.ramp, v), 1 - fade * u)


POLYS = {"crystal": [[0, -13], [5, -4], [4, 9], [-4, 9], [-5, -4]], "shard": [[0, -11], [3, 7], [-3, 7]], "diamond": [[0, -9], [6, 0], [0, 9], [-6, 0]], "arrow": [[0, -10], [6, 0], [2, 0], [2, 10], [-2, 10], [-2, 0], [-6, 0]],
         "rock": [[-7, 5], [-8, -1], [-4, -6], [2, -7], [7, -2], [8, 4], [3, 7]],
         "heart": [[0, 7], [-4, 3], [-7, -1], [-7, -4], [-5, -7], [-2, -7], [0, -4], [2, -7], [5, -7], [7, -4], [7, -1], [4, 3]]}


def L_poly(f, d, c):
    from PIL import Image, ImageDraw
    pts = d.get("points") or POLYS[d.get("shape", "crystal")]
    if not 3 <= len(pts) <= 24: raise ValueError("poly needs 3 to 24 points")
    sc = val(d.get("scale", 1), c.e) * c.sc; a = math.radians(val(d.get("rotate", 0), c.e)); ca, sa = math.cos(a), math.sin(a)
    if sc <= 0.05: return
    ay = -max(y for x, y in pts) if d.get("anchor") == "base" else 0.0                  # base: the lowest point sits on `at` (things that stand on the floor)
    P = [(round(c.ox + (x * ca - (y + ay) * sa) * sc, 2), round(c.oy + (x * sa + (y + ay) * ca) * sc, 2)) for x, y in pts]

    im = Image.new("L", (f.w, f.h), 0); ImageDraw.Draw(im).polygon(P, fill=255); m = np.array(im) > 0
    if not m.any(): return
    lx, ly = d.get("lit", [-1, -1]); yy, xx = np.mgrid[0:f.h, 0:f.w]; R = max(max(abs(x), abs(y)) for x, y in pts) * sc + 1
    grad = d.get("lit_strength", 0.35) * ((xx + 0.5 - c.ox) * lx + (yy + 0.5 - c.oy) * ly) / (math.hypot(lx, ly) * R)
    f.fill(m, c.ramp, depth=d.get("depth", 4), grad=grad, bias=val(d.get("bias", 0), c.e), cover=val(d.get("cover", 1), c.e))


def wave_geometry(d, e):
    """one frame of a breaking wave: (body outline, crest line), both [(x, y)] in px from `at` (the water line under the crest, y down).
    A back slope rises to the crest, the lip curls forward and down over a hollow barrel, the face drops to the trough; shared by the pixel and the painted renderer"""
    H = val(d.get("height", 24), e); curl = clamp(val(d.get("curl", 0.6), e)); L = val(d.get("length", max(H * 1.5, 1)), e); deep = d.get("deep", 4); sgn = -1 if d.get("dir", 1) < 0 else 1
    if H < 1: return [], []
    r = curl * H / 1.55; ri = 0.55 * r; cx, cy = 0.0, -H + r                                       # the barrel circle: top of the outer arc is the crest, r + ri reaches the water at full curl
    back = [(-L * (1 - u), -H * (u ** 1.8)) for u in [i / 14 for i in range(15)]]                   # gentle at the foot, steep at the crest
    if r < 0.8:                                                                                    # no curl: a steep face straight down
        outer, inner, foot = [], [], (0.28 * H, 0.0)
    else:
        te = math.radians(-90 + 120 * curl)                                                        # how far round the lip goes (more curl: further, down and back under)
        outer = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in [math.radians(-90) + (te - math.radians(-90)) * i / 14 for i in range(1, 15)]]
        inner = [(cx + ri * math.cos(a), cy + ri * math.sin(a)) for a in [te + (math.radians(-270) - te) * i / 14 for i in range(0, 15)]]
        foot = (ri + 0.25 * H, 0.0)
    body = back + outer + inner + [foot, (foot[0], deep), (-L, deep)]
    crest = back[-5:] + outer
    if sgn < 0: body = [(-x, y) for x, y in body]; crest = [(-x, y) for x, y in crest]
    return body, crest


def L_wave(f, d, c):
    from PIL import Image, ImageDraw
    body, crest = wave_geometry(d, c.e)
    if not body: return
    P = [(c.ox + x * c.sc, c.oy + y * c.sc) for x, y in body]
    im = Image.new("L", (f.w, f.h), 0); ImageDraw.Draw(im).polygon(P, fill=255); m = np.array(im) > 0
    if not m.any(): return
    lx, ly = d.get("lit", [-1, -1]); yy, xx = np.mgrid[0:f.h, 0:f.w]; R = max(max(abs(x), abs(y)) for x, y in body) * c.sc + 1
    Hc = max(val(d.get("height", 24), c.e) * c.sc, 1.0)
    grad = d.get("lit_strength", 0.35) * ((xx + 0.5 - c.ox) * lx + (yy + 0.5 - c.oy) * ly) / (math.hypot(lx, ly) * R) + 0.6 * (c.oy - yy - 0.5) / Hc - 0.25      # darker down at the water, lighter up at the crest
    f.fill(m, c.ramp, depth=d.get("depth", 2), grad=grad, bias=val(d.get("bias", -0.35), c.e), cover=val(d.get("cover", 1), c.e))
    fo = val(d.get("foam", 2), c.e) * c.sc
    if fo >= 0.5:                                                                                  # foam: a bright line along the crest and the lip
        col = c.ramp[-1]
        for (x0, y0), (x1, y1) in zip(crest, crest[1:]): f.line(c.ox + x0 * c.sc, c.oy + y0 * c.sc, c.ox + x1 * c.sc, c.oy + y1 * c.sc, col, max(1, int(round(fo))))


_IMG = {}


def L_stamp(f, d, c):
    from PIL import Image
    if not c.dir: raise ValueError("stamp needs a recipe file (an image is looked up next to it), not an inline recipe")
    path = os.path.realpath(os.path.join(c.dir, d["image"]))
    if not path.startswith(os.path.realpath(c.dir) + os.sep): raise ValueError("stamp: the image must sit inside the recipe's own folder")
    if path not in _IMG:
        with Image.open(path) as im: im = im.convert("RGBA")
        if im.width > 32 or im.height > 32: raise ValueError(f"stamp: {d['image']} is {im.width}x{im.height}; at most 32x32")
        _IMG[path] = np.array(im)
    a = _IMG[path]; r = int(d.get("rotate", 0)) // 90 % 4
    if r: a = np.rot90(a, -r)
    if d.get("flip"): a = a[:, ::-1]
    k = int(clamp(d.get("scale", 1), 1, 4)); k = max(1, int(k * c.sc + 0.5)); a = np.repeat(np.repeat(a, k, 0), k, 1); h, w = a.shape[:2]; x0 = int(round(c.ox - w / 2)); y0 = int(round(c.oy - h / 2))
    for yy in range(h):
        for xx in range(w):
            if a[yy, xx, 3] >= 128: f.put(x0 + xx, y0 + yy, tuple(int(v) for v in a[yy, xx, :3]))


_DEPTH = [0]


def L_include(f, d, c):
    from . import engine
    if _DEPTH[0] >= 2: raise ValueError("include is nested more than 2 deep")
    mod, meta = engine.get(d["recipe"])
    if "recipe" not in meta: raise ValueError(f"include: '{d['recipe']}' is drawn by Python code; only recipes can be included (`gizvfx list`: those with the tag 'recipe')")
    sub = dict(meta["recipe"]); sub["pivot"] = [c.ox, c.oy]; o2 = engine.options(meta, d.get("options")); o2.seed = c.seed
    if d.get("palette") not in (None, "main"): o2.palette = d["palette"]
    _DEPTH[0] += 1
    try: draw_spec(sub, f, c.p, o2)
    finally: _DEPTH[0] -= 1


LAYERS = {"wave": L_wave, "glow": L_glow, "disc": L_disc, "ring": L_ring, "star": L_star, "particles": L_particles, "blob": L_blob, "bolt": L_bolt, "rays": L_rays, "orbit": L_orbit, "funnel": L_funnel, "brush": L_brush, "hatch": L_hatch, "halftone": L_halftone, "burst": L_burst, "speedlines": L_speedlines, "splat": L_splat, "poly": L_poly, "stamp": L_stamp, "include": L_include, "beam": L_beam, "arc": L_arc}


# ---- validation, drawing, loading ---------------------------------------------------------------------------------------
def validate(spec):
    for k in spec:
        if k not in ALLOWED_TOP: raise ValueError(f"recipe key '{k}' is unknown" + _near(k, ALLOWED_TOP))
    if not spec["layers"]: raise ValueError("a recipe needs at least one layer")
    if len(spec["layers"]) > 40: raise ValueError(f"a recipe may have at most 40 layers, this has {len(spec['layers'])}")
    if not (isinstance(spec["size"], (list, tuple)) and len(spec["size"]) == 2 and all(isinstance(v, int) and 8 <= v <= 256 for v in spec["size"])): raise ValueError(f"size must be [w, h], whole numbers 8 to 256, got {spec['size']}")
    for k in spec.get("style", {}):
        if k not in STYLE_KEYS: raise ValueError(f"style key '{k}' is unknown" + _near(k, STYLE_KEYS) + f". Keys: {', '.join(STYLE_KEYS)}")
    for i, d in enumerate(spec["layers"]):
        ty = d.get("type")
        if ty not in LAYERS: raise ValueError(f"layer {i}: type '{ty}' is unknown" + _near(str(ty), LAYERS) + f". Types: {', '.join(LAYERS)}")
        ok = set(SCHEMA[ty]) | set(COMMON) | {"type"}
        for k in d:
            if k not in ok: raise ValueError(f"layer {i} ({ty}): key '{k}' is unknown" + _near(k, ok) + f". Keys: {', '.join(sorted(ok))}")
        for key, cap in (("count", 400 if ty == "particles" else 60 if ty == "blob" else 64),):
            if isinstance(d.get(key), int) and d[key] > cap: raise ValueError(f"layer {i} ({ty}): count {d[key]} is more than the limit of {cap}")
        if ty == "include" and "recipe" not in d: raise ValueError(f"layer {i} (include): needs a \"recipe\"")
        if ty == "stamp" and "image" not in d: raise ValueError(f"layer {i} (stamp): needs an \"image\"")
        t = d.get("t", [0, 1])
        if not (isinstance(t, list) and len(t) == 2 and 0 <= t[0] <= t[1] <= 1): raise ValueError(f"layer {i} ({ty}): t must be [start, end] with 0 <= start <= end <= 1, got {t}")
        es = d.get("ease", "linear")
        if any(x not in EASE for x in (es if isinstance(es, list) else [es])): raise ValueError(f"layer {i} ({ty}): ease must be one of {', '.join(EASE)} (or a list of them, one per key step)")


def _near(k, pool):
    m = difflib.get_close_matches(k, list(pool), 1, 0.6); return f" (did you mean '{m[0]}'?)" if m else ""


def _one(spec, g, d, i, t, px, py, main, o, sc, vs):
    t0, t1 = d.get("t", [0, 1]); p = seg(t, t0, t1); _SEG[0] = d["ease"] if isinstance(d.get("ease"), list) else None; e = _efn(d)(p); ox, oy = pt(d.get("at", [0, 0]), e); wob = d.get("wobble")
    if d.get("spin"): ox += d["spin"][0] * math.cos(TAU * d["spin"][1] * p); oy += d["spin"][0] * math.sin(TAU * d["spin"][1] * p)
    if wob: ox += wob[0] * math.sin(TAU * (t * wob[2])); oy += wob[1] * math.sin(TAU * (t * wob[2] + 0.25))
    vv = d.get("v")
    c = SimpleNamespace(f=g, t=t, p=p, e=e, px0=px, py0=py, ox=px + ox, oy=py + oy, ramp=_ramp(d, main, spec.get("palettes")), seed=int(o.seed) * 131 + int(d.get("seed", i)) * 17, rng=None, sc=sc, dir=spec.get("_dir"), loop=bool(spec.get("loop")),
                        v=lambda default, vv=vv, e=e: val(default if vv is None else vv, e) + vs)
    c.rng = Rng(c.seed); LAYERS[d["type"]](g, d, c)


def _post(f, g, d, main, e, roles=None):
    """erode / outline / rim on what one layer drew (into the scratch frame g), then lay it on the real frame"""
    from scipy.ndimage import distance_transform_edt, binary_dilation
    m = g.a > 0; er = val(d.get("erode", 0), e) if d["type"] != "blob" else 0; ramp = _ramp(d, main, roles)
    if er > 0 and m.any():
        m = m & (distance_transform_edt(np.pad(m, 1))[1:-1, 1:-1] > er); g.a[~m] = 0
    if isinstance(d.get("rim"), (list, tuple)):                                        # (a bolt's rim is a colour: that is drawn by the bolt itself)
        dx, dy = d["rim"]; rm = m & ~np.roll(m, (-int(np.sign(dy)), -int(np.sign(dx))), (0, 1)); g.rgb[rm] = ramp[-2] if len(ramp) > 2 else ramp[-1]
    if d.get("outline"):
        oc = ramp[0] if d["outline"] == "auto" else hex2rgb(d["outline"]); ol = binary_dilation(m) & ~m; g.rgb[ol] = oc; g.a[ol] = 255
    mk = g.a > 0; f.rgb[mk] = g.rgb[mk]; f.a[mk] = 255; f.light += g.light


def _style(f, st, main):
    """whole-effect treatment after every layer: shadow, outline, rim (all from the pixels that were drawn, glow excluded)"""
    from scipy.ndimage import binary_dilation
    m = f.a > 0
    if not m.any(): return
    if st.get("shadow"):
        dx, dy = st["shadow"]; sh = np.roll(m, (int(dy), int(dx)), (0, 1)) & ~m; f.rgb[sh] = main[0]; f.a[sh] = 255
    if st.get("outline"):
        oc = main[0] if st["outline"] == "auto" else hex2rgb(st["outline"]); ol = binary_dilation(m) & ~m; f.rgb[ol] = oc; f.a[ol] = 255
    if st.get("rim"):
        dx, dy = st["rim"]; rm = m & ~np.roll(m, (-int(np.sign(dy)), -int(np.sign(dx))), (0, 1)); f.rgb[rm] = main[-2] if len(main) > 2 else main[-1]


def draw_spec(spec, f, t, o):
    px, py = spec["pivot"]; main = resolve(o.palette, spec["palette"])
    for i, d in enumerate(spec["layers"]):
        try:
            d = sub(d, o); t0, t1 = d.get("t", [0, 1]); sm = d.get("smear"); S = 7 if sm else 0
            post = ("outline" in d) or isinstance(d.get("rim"), (list, tuple)) or ("erode" in d and d["type"] != "blob"); g = Frame(f.w, f.h) if post else f
            for k in range(S, -1, -1):                                                 # the oldest copy of a smear first, the real layer last
                tk = t
                if k:
                    if not spec["loop"] and t >= t1: continue                          # a one-shot ends empty: no trail once the window is over
                    dt = k / S * sm[0] * (t1 - t0); tk = (t - dt) % 1.0 if spec["loop"] else t - dt
                if tk < t0 or (tk > t1 and not d.get("hold")): continue
                _one(spec, g, d, i, tk, px, py, main, o, 1 - (1 - sm[1]) * k / S if k else 1.0, -0.45 * k / S if k else 0.0)
            if post: _post(f, g, d, main, _efn(d)(seg(t, t0, t1)), spec.get("palettes"))
        except (TypeError, KeyError, IndexError, ValueError, ZeroDivisionError) as ex:
            raise ValueError(f"layer {i} ({d.get('type')}): {type(ex).__name__}: {ex}") from None
    if spec.get("style"): _style(f, spec["style"], main)


def load(src):
    """recipe (path to a .json file, or a dict) -> (module-like, meta) for the engine"""
    if isinstance(src, dict): spec = dict(src)
    else:
        with open(src, encoding="utf-8") as fh:
            try: spec = json.load(fh)
            except ValueError as e: raise ValueError(f"{src}: not valid JSON: {e}") from None
    spec = {**DEFAULTS, **spec}
    if not isinstance(src, dict): spec["_dir"] = os.path.dirname(os.path.abspath(src))
    validate(spec); spec["size"] = list(spec["size"]); spec["pivot"] = list(spec.get("pivot") or [spec["size"][0] // 2, spec["size"][1] // 2])
    base = os.path.splitext(os.path.basename(src))[0] if not isinstance(src, dict) else "custom"
    meta = {"id": spec.get("id") or f"custom/{base}", "name": spec["name"], "loop": bool(spec["loop"]), "duration": spec["duration"], "fps": spec["fps"], "size": tuple(spec["size"]),
            "pivot": tuple(spec["pivot"]), "about": spec["about"], "tags": list(spec["tags"]) + ["recipe"], "options": dict(spec["options"]),
            "recipe": spec, "draw": lambda f, t, o, spec=spec: draw_spec(spec, f, t, o)}
    return SimpleNamespace(draw=meta["draw"]), meta


def schema_text(ty=None):
    out = ["Recipe (JSON): " + ", ".join(f"{k}" for k in sorted(ALLOWED_TOP)), "  id 'category/name', name, about, tags[], loop true|false, duration s, fps, size [w,h], pivot [x,y] (default centre),",
           "  palette (name or hex list), options {name: default} (use as \"$name\" in any value), layers [ ... ],",
           "  palettes {role: name or hex list} (a layer says \"palette\": \"@role\"), style {" + "; ".join(f"{k}: {v}" for k, v in STYLE_KEYS.items()) + "}", "", "Keys every layer takes:"]
    out += [f"  {k:8s} {v}" for k, v in COMMON.items()] + [""]
    for name in ([ty] if ty else LAYERS):
        if name not in LAYERS: raise ValueError(f"unknown layer type '{name}'. Types: {', '.join(LAYERS)}")
        out.append(f"layer \"{name}\":"); out += [f"  {k:9s} {v}" for k, v in SCHEMA[name].items()]; out.append("")
    out.append("Values: 3 | [from, to] | [a, b, c, ...] (evenly spaced keys: rise, hold, fade in ONE layer) | \"$option*0.5\" | {\"wave\":[lo,hi,cycles]} | \"$option\". Loops: use `wave`, particles mode stream with whole `cycles`, orbit with whole `turns`.")
    return "\n".join(out)


def user_dir():
    return os.environ.get("GIZVFX_RECIPES") or os.path.join(os.path.expanduser("~"), ".gizvfx", "recipes")


def import_recipe(path):
    """validate (key names, limits), render and report a recipe someone sent you, then keep a copy in your recipe folder under a content-hash name. Returns (dest, meta, problems, flags)"""
    from . import engine
    mod, meta = load(path)
    if "stamp" in {l.get("type") for l in meta["recipe"]["layers"]}: raise ValueError("a recipe with `stamp` layers needs its image files: copy the folder by hand instead of importing")
    problems = engine.check(path); metrics, flags = engine.report(path)
    raw = open(path, "rb").read(); h = hashlib.sha256(raw).hexdigest()[:8]; os.makedirs(user_dir(), exist_ok=True)
    dest = os.path.join(user_dir(), f"{os.path.splitext(os.path.basename(path))[0]}-{h}.json"); shutil.copyfile(path, dest)
    return dest, meta, problems, flags
