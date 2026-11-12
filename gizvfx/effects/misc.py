# SPDX-License-Identifier: AGPL-3.0-or-later
"""more effects: lightning bolt, frost nova, heal, magic circle, coin sparkle, slash, rain, snow."""
import math
import numpy as np
from ..core import TAU, Rng, clamp, lerp, disc_mask, seg, ramp_at, out_expo, out_quart
from ..ramps import RAMPS, resolve
from ..kit import star, jagged, ballistic


# ---------------------------------------------------------------------------------------------------------------- lightning
def draw_bolt(f, t, o):
    ramp = resolve(o.palette, "electric"); r = Rng(o.seed); top = (32, 7); gx, gy = 32 + o.lean, 84
    vis = [(0.03, 0.14), (0.20, 0.34), (0.40, 0.46)]                                    # the bolt strikes in three flashes, thinner each time
    on = [i for i, (a, b) in enumerate(vis) if a <= t < b]
    pts = jagged(r, top[0], top[1], gx, gy, depth=5, rough=0.2)
    branches = []
    for k in range(int(o.branches)):
        i = r.i(len(pts) // 4, len(pts) * 3 // 4); sx, sy = pts[i]; ex = sx + r.u(10, 22) * r.pick((-1, 1)); ey = sy + r.u(14, 28)
        branches.append(jagged(r, sx, sy, ex, ey, depth=3, rough=0.25))
    flash = max([1 - (t - vis[i][0]) / (vis[i][1] - vis[i][0]) for i in on] or [0])
    if on:
        i = on[0]; w = [4, 3, 2][i]
        f.glow(gx, gy - 30, 46, ramp[2], 0.5 * flash, steps=3); f.glow(gx, gy, 24, ramp[3], 0.6 * flash)
        for a, b in zip(pts, pts[1:]): f.line(a[0], a[1], b[0], b[1], ramp[2], w + 2)
        for br in branches:
            for a, b in zip(br, br[1:]): f.line(a[0], a[1], b[0], b[1], ramp[2], max(1, w - 2))
        for a, b in zip(pts, pts[1:]): f.line(a[0], a[1], b[0], b[1], ramp[4], w)
        for a, b in zip(pts, pts[1:]): f.line(a[0], a[1], b[0], b[1], ramp[5], max(1, w - 2))
        if i == 0: f.disc(gx, gy, 8, ramp[3:], mode="core", bias=0.2)
    p = seg(t, 0.03, 0.8)
    if 0 < p < 1:                                                                       # sparks thrown up where it lands
        for k in range(14):
            a = r.u(math.pi * 1.1, math.pi * 1.9); sp = r.u(14, 30); q = seg(t, 0.03, 0.03 + r.u(0.3, 0.75))
            if q >= 1: continue
            x, y = ballistic(gx, gy, math.cos(a) * sp * q, math.sin(a) * sp * q, 70, q)
            if y < gy + 2: f.put(x, y, ramp_at(ramp, 1.0 - 0.7 * q))
        rp = seg(t, 0.03, 0.4)
        if rp < 1:
            for k in range(48):
                a = TAU * k / 48; f.put(gx + math.cos(a) * (3 + 22 * out_expo(rp)), gy + math.sin(a) * (3 + 22 * out_expo(rp)) * 0.3, ramp_at(ramp, 0.9 - 0.6 * rp))


# ---------------------------------------------------------------------------------------------------------------- frost nova
def draw_nova(f, t, o):
    ramp = resolve(o.palette, "ice"); r = Rng(o.seed); cx, cy = 56, 44; R = o.radius; N = int(o.spikes)
    p = seg(t, 0.04, 0.4); e = out_expo(p); fade = 1 - seg(t, 0.62, 0.98)
    f.glow(cx, cy, 36 * (1 - seg(t, 0, 0.35)) + 4, ramp[4], 0.7 * (1 - seg(t, 0, 0.5)), steps=3)
    if fade > 0:
        fl = f.mask()                                                                   # frost on the floor: a squashed disc that grows
        for k in range(48):
            a = TAU * k / 48; rr = R * e * (0.93 + 0.07 * math.sin(a * 5)); disc_mask(fl, cx + math.cos(a) * rr * 0.5, cy + math.sin(a) * rr * 0.2, 5 + 4 * e)
        disc_mask(fl, cx, cy, R * e * 0.55)
        m2 = fl.copy(); rows = np.arange(f.h)[:, None]; m2 &= ((rows - cy) / 0.36) ** 2 + (np.arange(f.w)[None, :] - cx) ** 2 <= (R * e) ** 2
        f.fill(m2, ramp[0:4], depth=4 * fade + 0.5, cover=0.35 + 0.65 * fade if fade < 1 else 1.0)
    for k in range(N):                                                                  # crystals erupt along the ring, back ones first
        a = TAU * (k + r.u(-0.25, 0.25)) / N; h = r.u(0.6, 1.0); q = seg(t, 0.1 + 0.14 * (k % 3) / 3, 0.38)
        if q <= 0: continue
        grow = out_quart(q) * (1 - seg(t, 0.7, 0.98)) ** 0.8; hh = (10 + 20 * h) * o.height * grow; ww = (3.5 + 3 * h) * grow
        x = cx + math.cos(a) * R * 0.78 * e; y = cy + math.sin(a) * R * 0.78 * e * 0.4
        if hh < 1.5: continue
        m = f.mask()
        for s in range(int(hh) + 1):
            u = s / max(hh, 1); disc_mask(m, x + (u * (k % 3 - 1)) * 1.5, y - s, ww * (1 - u) ** 0.85 / 2 + 0.3)
        f.fill(m, ramp[1:], depth=ww * 0.35, bias=0.1 + 0.4 * (1 - u) * 0 + (0.2 if math.sin(a) < 0 else 0))
    for k in range(18):                                                                 # snow motes lifted by the burst
        q = seg(t, 0.1, 0.97); a = r.u(0, TAU); d = r.u(0.2, 1.0); lift = r.u(8, 26)
        if q <= 0 or q >= 1: continue
        f.put(cx + math.cos(a) * R * d * 0.9 * out_expo(clamp(q * 1.4)), cy + math.sin(a) * R * d * 0.35 - lift * q, ramp_at(ramp, 0.95 - 0.5 * q))


# ---------------------------------------------------------------------------------------------------------------- heal
def draw_heal(f, t, o):
    ramp = resolve(o.palette, "heal"); r = Rng(o.seed); cx, base = 24, 54
    f.glow(cx, base - 14, 30, ramp[2], 0.42 + 0.08 * math.sin(TAU * t), steps=3); f.glow(cx, base - 14, 16, ramp[4], 0.25)
    for k in range(2):                                                                  # two rings rise and shrink over the body, the loop stays closed
        p = (t + k / 2.0) % 1.0; y = base - p * 44; rx = 14 * (1 - 0.25 * p)
        for a in range(72):
            ang = TAU * a / 72; col = ramp_at(ramp, 0.92 - 0.6 * p)
            f.put(cx + math.cos(ang) * rx, y + math.sin(ang) * rx * 0.3, col); f.put(cx + math.cos(ang) * (rx - 1), y + math.sin(ang) * (rx - 1) * 0.3 + (1 if math.sin(ang) > 0 else 0), ramp_at(ramp, 0.65 - 0.4 * p))
    for i in range(int(o.motes)):
        off = r.u(); p = (t + off) % 1.0; x = cx + r.u(-13, 13) + 2.2 * math.sin(TAU * (p + off)); y = base - 2 - p * 50 * r.u(0.7, 1.0)
        a = 1 - p
        if (i % 3) == 0:                                                                # plus-shaped sparkles that twinkle
            s = 1 + (1 if 0.2 < p < 0.7 else 0)
            for d in range(-s, s + 1): f.put(x + d, y, ramp_at(ramp, 1.0 - 0.4 * p)); f.put(x, y + d, ramp_at(ramp, 1.0 - 0.4 * p))
        else: f.put(x, y, ramp_at(ramp, 0.95 - 0.7 * p))


# ---------------------------------------------------------------------------------------------------------------- magic circle
def draw_circle(f, t, o):
    ramp = resolve(o.palette, "arcane"); r = Rng(o.seed); cx, cy = 48, 36; R = o.radius; sq = 0.4
    f.glow(cx, cy, R * 1.1, ramp[2], 0.28 + 0.06 * math.sin(TAU * t), steps=3)
    def E(rad, a): return cx + math.cos(a) * rad, cy + math.sin(a) * rad * sq
    for rad, th, v in ((R, 2, 0.65), (R * 0.82, 1, 0.55), (R * 0.45, 1, 0.8)):
        for k in range(int(rad * 7)):
            a = TAU * k / int(rad * 7); x, y = E(rad, a); f.put(x, y, ramp_at(ramp, v))
            if th > 1: x, y = E(rad - 1, a); f.put(x, y, ramp_at(ramp, v - 0.25))
    n = int(o.runes); rot = t * TAU
    for k in range(n):                                                                  # runes: short strokes in a band, the band turns once per loop
        a = rot + TAU * k / n; pat = (k * 7 + o.seed) % 5; x0, y0 = E(R * 0.91, a)
        for j in range(2 + pat % 3):
            x, y = E(R * (0.86 + 0.045 * j), a + 0.05 * ((pat + j) % 3 - 1)); f.put(x, y, ramp_at(ramp, 0.95)); f.put(x + 1, y, ramp_at(ramp, 0.7))
    pts = [E(R * 0.78, -rot / 5 + TAU * k / 5 * 2) for k in range(5)]                  # a counter-turning star inside
    for a, b in zip(pts, pts[1:] + pts[:1]): f.line(a[0], a[1], b[0], b[1], ramp_at(ramp, 0.7))
    for k in range(int(o.motes)):
        off = r.u(); p = (t + off) % 1.0; a = r.u(0, TAU); d = r.u(0.1, 0.8); x, y = E(R * d, a)
        f.put(x, y - p * 26, ramp_at(ramp, 0.95 - 0.7 * p))
    f.disc(cx, cy, 2.0 + math.sin(TAU * t) * 0.6, ramp[-2:], mode="core", bias=0.2)


# ---------------------------------------------------------------------------------------------------------------- coin sparkle
def draw_coin(f, t, o):
    ramp = resolve(o.palette, "gold"); r = Rng(o.seed); cx, cy = 24, 24
    p = seg(t, 0, 0.5); f.glow(cx, cy, 20 * (1 - seg(t, 0, 0.6)) + 2, ramp[4], 0.8 * (1 - seg(t, 0, 0.7)), steps=3)
    if p < 1: star(f, cx, cy, 6 + 15 * out_quart(min(1, p * 2)) * (1 - p), ramp[-3:], arms=4, thin=0.14); star(f, cx, cy, (4 + 8 * (1 - p)) , ramp[-2:], arms=4, thin=0.3) if p < 0.5 else None
    f.disc(cx, cy, 3 * (1 - seg(t, 0, 0.3)) ** 0.6 + 0.5, ramp[-2:], mode="core", bias=0.3) if t < 0.3 else None
    for k in range(int(o.stars)):                                                       # little twinkles that pop at their own moment
        a = r.u(0, TAU); d = r.u(8, 18); st = r.u(0.15, 0.55); q = seg(t, st, st + 0.35)
        if q <= 0 or q >= 1: continue
        s = 1 + int(3 * math.sin(math.pi * q)); x, y = cx + math.cos(a) * d, cy + math.sin(a) * d - q * 6
        for dd in range(-s, s + 1):
            if abs(dd) < s or True: f.put(x + dd, y, ramp_at(ramp, 1.0 - 0.5 * abs(dd) / (s + 1))); f.put(x, y + dd, ramp_at(ramp, 1.0 - 0.5 * abs(dd) / (s + 1)))
    ring = seg(t, 0.02, 0.5)
    if ring < 1:
        for k in range(32):
            a = TAU * k / 32
            f.put(cx + math.cos(a) * (3 + 15 * out_expo(ring)), cy + math.sin(a) * (3 + 15 * out_expo(ring)), ramp_at(ramp, 0.9 - 0.6 * ring))


# ---------------------------------------------------------------------------------------------------------------- slash
def draw_slash(f, t, o):
    ramp = resolve(o.palette, "metal"); r = Rng(o.seed); cx, cy = 20, 40; R = o.radius; a0, a1 = math.radians(-100), math.radians(40)
    sweep = out_expo(seg(t, 0.0, 0.28)); tail = seg(t, 0.22, 0.7)
    f.glow(cx + R * 0.6, cy - 4, 30 * (1 - seg(t, 0.1, 0.5)) + 2, ramp[4], 0.4 * (1 - seg(t, 0, 0.5)), steps=3)
    if tail < 1:
        head = lerp(a0, a1, sweep); back = lerp(a0, head, tail * 0.95); n = 48
        for k in range(n + 1):                                                          # a crescent: thick in the middle, pointed at both ends
            u = k / n; a = lerp(back, head, u); w = (2 + 8 * math.sin(math.pi * u) ** 0.8) * (1 - tail ** 2); rad = R + 3 * math.sin(math.pi * u)
            if w < 1: continue
            f.disc(cx + math.cos(a) * rad, cy + math.sin(a) * rad, w / 2, ramp[1:], mode="core", bias=0.25 + 0.5 * u - 0.5 * tail)
        for k in range(n + 1):
            u = k / n; a = lerp(back, head, u); w = (1 + 3 * math.sin(math.pi * u)) * (1 - tail)
            if w >= 1: f.disc(cx + math.cos(a) * (R + 1.5 * math.sin(math.pi * u)), cy + math.sin(a) * (R + 1.5 * math.sin(math.pi * u)), w / 2, ramp[-2:], mode="core", bias=0.5)
    for i in range(10):
        q = seg(t, 0.1 + r.u(0, 0.2), 0.5 + r.u(0, 0.3))
        if q <= 0 or q >= 1: continue
        a = lerp(a0, a1, r.u(0.3, 1.0)); x, y = ballistic(cx + math.cos(a) * R, cy + math.sin(a) * R, r.u(4, 14) * q, r.u(-8, 5) * q, 30, q)
        f.put(x, y, ramp_at(ramp, 1.0 - 0.7 * q))


# ---------------------------------------------------------------------------------------------------------------- weather
def draw_rain(f, t, o):
    ramp = resolve(o.palette, "water"); r = Rng(o.seed); W, H = f.w, f.h; slope = o.slope
    for i in range(int(o.drops)):
        x0 = r.u(0, W); off = r.u(); sp = r.i(1, 3); L = r.i(3, 6); p = (t * sp + off) % 1.0
        y = p * (H + L) - L; x = (x0 + slope * p * (H + L)) % W
        for k in range(L):
            yy = y + k; xx = x - slope * k
            if 0 <= yy < H - 6 or i % 2: f.put(xx % W, yy, ramp_at(ramp, 0.35 + 0.6 * k / L))
    for i in range(int(o.drops) // 3):                                                  # splashes where drops land
        x = r.u(0, W); off = r.u(); q = (t * 2 + off) % 1.0
        if q < 0.35:
            s = int(1 + q * 6); y = H - 2 - r.i(0, 3)
            f.put(x - s, y, ramp_at(ramp, 0.7)); f.put(x + s, y, ramp_at(ramp, 0.7)); f.put(x, y - int(q * 6), ramp_at(ramp, 0.9))


def draw_snow(f, t, o):
    ramp = resolve(o.palette, "ice"); r = Rng(o.seed); W, H = f.w, f.h
    for i in range(int(o.flakes)):
        x0 = r.u(0, W); off = r.u(); sp = r.i(1, 3); size = r.pick((1, 1, 1, 2, 2)); amp = r.u(2, 5); ph = r.u(0, TAU)
        p = (t * sp + off) % 1.0; y = p * (H + 4) - 2; x = (x0 + amp * math.sin(TAU * t * sp + ph)) % W
        c = ramp_at(ramp, 0.95 if size == 2 else 0.8)
        for dx in range(size):
            for dy in range(size): f.put(x + dx, y + dy, c)


EFFECTS = [
    {"id": "lightning/bolt", "name": "Lightning bolt", "loop": False, "duration": 1.0, "fps": 12, "size": (64, 96), "pivot": (32, 84), "draw": draw_bolt,
     "about": "A bolt from the top to the floor in three flashes, thinner each time, with side branches, a glow and sparks where it lands.", "tags": ["storm", "attack"],
     "options": {"branches": 3, "lean": 0}},
    {"id": "ice/frost-nova", "name": "Frost nova", "loop": False, "duration": 1.5, "fps": 12, "size": (112, 72), "pivot": (56, 44), "draw": draw_nova,
     "about": "Ice crystals erupt in a ring from the feet, a white flash, frost spreading on the floor, snow motes, then it all melts away.", "tags": ["ice", "area"],
     "options": {"radius": 46, "spikes": 14, "height": 1.0}},
    {"id": "holy/heal", "name": "Heal", "loop": True, "duration": 1.5, "fps": 12, "size": (48, 64), "pivot": (24, 54), "draw": draw_heal,
     "about": "Soft green rings rise round the body with plus-shaped sparkles and motes drifting up in a glow.", "tags": ["buff", "support"], "options": {"motes": 20}},
    {"id": "arcane/magic-circle", "name": "Magic circle", "loop": True, "duration": 2.0, "fps": 12, "size": (96, 72), "pivot": (48, 36), "draw": draw_circle,
     "about": "A rune circle on the floor: a turning band of runes, a star turning the other way, a glow and motes rising.", "tags": ["spell", "ground"],
     "options": {"radius": 40, "runes": 14, "motes": 12}},
    {"id": "pickups/coin-sparkle", "name": "Coin sparkle", "loop": False, "duration": 0.9, "fps": 12, "size": (48, 48), "pivot": (24, 24), "draw": draw_coin,
     "about": "A pickup: a bright cross flash, a thin ring and little twinkles that pop and drift up.", "tags": ["pickup", "ui"], "options": {"stars": 6}},
    {"id": "melee/slash", "name": "Slash", "loop": False, "duration": 0.7, "fps": 12, "size": (80, 72), "pivot": (20, 40), "draw": draw_slash,
     "about": "A sword cut: a crescent that sweeps through, white at the edge and thinning behind it, with chips flying off.", "tags": ["melee", "attack"], "options": {"radius": 30}},
    {"id": "weather/rain", "name": "Rain", "loop": True, "duration": 1.0, "fps": 12, "size": (64, 64), "pivot": (32, 32), "draw": draw_rain,
     "about": "A tile of falling rain that wraps both ways, with small splashes at the bottom.", "tags": ["tile", "ambient"], "tile": True, "options": {"drops": 34, "slope": 0.12}},
    {"id": "weather/snow", "name": "Snow", "loop": True, "duration": 2.0, "fps": 12, "size": (64, 64), "pivot": (32, 32), "draw": draw_snow,
     "about": "A tile of drifting snow that wraps both ways: flakes of one or two pixels swaying as they fall.", "tags": ["tile", "ambient"], "tile": True, "options": {"flakes": 36}},
]
