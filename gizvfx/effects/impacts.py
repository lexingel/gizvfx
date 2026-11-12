# SPDX-License-Identifier: AGPL-3.0-or-later
"""impacts and explosions: hit-spark, shockwave, small-explosion."""
import math
from ..core import TAU, Rng, clamp, lerp, disc_mask, seg, ramp_at, out_expo, out_quart
from ..ramps import RAMPS, resolve
from ..kit import star, ballistic


def draw_spark(f, t, o):
    ramp = resolve(o.palette, "fire"); r = Rng(o.seed); cx, cy = 36, 36; S = o.size
    fl = seg(t, 0, 0.3)
    f.glow(cx, cy, S * 0.7 * (1 - fl) + 2, ramp[4], 0.7 * (1 - seg(t, 0, 0.4)))
    for i in range(int(o.streaks)):                                                    # streaks fly out, shorten and cool
        a = TAU * (i + r.u(-0.3, 0.3)) / o.streaks; sp = r.u(0.7, 1.0); life = r.u(0.5, 0.8); p = seg(t, 0.02, 0.02 + life)
        if p >= 1: continue
        r0 = lerp(2, S * 1.0 * sp, out_expo(p)); ln = lerp(S * 0.8, 2, p) * sp
        f.tapered(cx + math.cos(a) * r0, cy + math.sin(a) * r0, cx + math.cos(a) * (r0 + ln), cy + math.sin(a) * (r0 + ln), 3.0 if p < 0.35 else 2.0 if p < 0.7 else 1.0, 1.0, ramp, v=1.0 - 0.75 * p)
    ring_p = seg(t, 0, 0.5)
    if ring_p < 1:
        f.ring(cx, cy, lerp(3, S * 0.55, out_expo(ring_p)), lerp(2.2, 1, ring_p), ramp, v=0.9 - 0.7 * ring_p, cover=1 if ring_p < 0.5 else 0.6)
    if fl < 1:                                                                         # the white flash star on the first frames
        star(f, cx, cy, S * (0.9 - 0.6 * fl) + 2, ramp[-3:], arms=8, thin=0.1, v=1.0)
        f.disc(cx, cy, 5.0 * (1 - fl) ** 0.7 + 0.6, ramp[-2:], mode="core", bias=0.4)
    for i in range(int(o.debris)):
        a = r.u(0, TAU); sp = r.u(10, 24); p = seg(t, 0.05, r.u(0.55, 0.9))
        if p >= 1: continue
        x, y = ballistic(cx, cy, math.cos(a) * sp * p * 1.4, math.sin(a) * sp * p * 1.4 - 4, 38, p)
        f.put(x, y, ramp_at(ramp, 0.85 - 0.8 * p))


def draw_shock(f, t, o):
    ramp = resolve(o.palette, "dust"); r = Rng(o.seed); cx, cy = 48, 36; R = o.radius
    p = seg(t, 0, 0.8); e = out_expo(p)
    if p < 1:
        N = 96
        for k in range(N):                                                             # a flat ellipse ring on the ground, built from whole pixels
            a = TAU * k / N; rr = R * e; th = lerp(3.2, 0.7, p)
            for w in range(int(th) + 1):
                x = cx + math.cos(a) * (rr - w); y = cy + math.sin(a) * (rr - w) * 0.42
                if (k + w) % 4 or p < 0.5: f.put(x, y, ramp_at(ramp, 0.95 - 0.5 * w / max(th, 1) - 0.4 * p))
    for i in range(int(o.dust)):
        a = r.u(0, TAU); d = r.u(0.5, 1.0); q = seg(t, 0.05, 0.95)
        if q >= 1: continue
        rad = lerp(2.0, 5.5, q) * r.u(0.7, 1.2); x = cx + math.cos(a) * R * d * out_expo(clamp(q * 1.2)) * 0.85; y = cy + math.sin(a) * R * d * 0.38 * out_expo(clamp(q * 1.2)) - q * 7 * r.u(0.5, 1)
        f.disc(x, y, rad * (1 - q ** 2.5), RAMPS["dust"], mode="lit", bias=0.05)
    f.glow(cx, cy, 20 * (1 - seg(t, 0, 0.3)), ramp[-1], 0.5)


def draw_boom(f, t, o):
    ramp = resolve(o.palette, "fire"); sm = RAMPS["smoke"]; r = Rng(o.seed); gx, gy = 48, 80; S = o.size
    f.glow(gx, gy - 14, 34 * S * (1 - seg(t, 0, 0.5)) + 6, ramp[3], 0.7 * (1 - seg(t, 0, 0.7)), steps=3)
    for k in range(8):                                                                 # smoke first, so the fire sits in front of it
        q = seg(t, 0.2 + k * 0.025, 1.0)
        if q <= 0 or q >= 1: continue
        dx = r.u(-13, 13); rad = lerp(4, 11, out_quart(q)) * S * r.u(0.85, 1.15) * (1 - seg(q, 0.62, 1.0)) ** 0.8
        if rad > 0.8: f.disc(gx + dx * q, gy - 24 - q * 36 * r.u(0.7, 1.0) - k * 1.5, rad, sm[1:], mode="lit", bias=0.0)
    fb = seg(t, 0, 0.4); grow = out_quart(fb); shrink = seg(t, 0.38, 0.82)
    blobs = [(r.u(-1, 1), r.u(0.0, 1.0), r.u(0.55, 1.0)) for _ in range(8)]
    if shrink < 1:
        m = f.mask()
        for dx, dy, sz in blobs:
            cx = gx + dx * 15 * S * grow; cy = gy - 10 - dy * 26 * S * grow; rad = (8 + 7 * sz) * S * grow * (1 - shrink) ** 0.8
            disc_mask(m, cx, cy, rad)
        disc_mask(m, gx, gy - 11, 14 * S * grow * (1 - shrink) ** 0.8)
        f.fill(m, ramp, depth=6 * S, bias=0.25 - 0.85 * seg(t, 0.05, 0.8))
    fl = seg(t, 0, 0.16)
    if fl < 1: f.disc(gx, gy - 13, 22 * S * out_quart(fl) * (1 - fl ** 2), ramp[-2:], mode="core", bias=0.5)
    for i in range(16):
        a = r.u(math.pi * 1.05, math.pi * 1.95); sp = r.u(30, 62) * S; p = seg(t, 0.03, r.u(0.5, 0.95))
        if p >= 1: continue
        x, y = ballistic(gx, gy - 8, math.cos(a) * sp * 0.9 * p, math.sin(a) * sp * 0.9 * p, 42 * S, p)
        if y < gy + 2: f.disc(x, y, 1.2 if i % 3 else 0.6, ramp, mode="core", bias=0.2 - 0.8 * p)
    N = 80; rp = seg(t, 0, 0.45)
    if rp < 1:
        for k in range(N):
            a = TAU * k / N; rr = 6 + 36 * S * out_quart(rp)
            f.put(gx + math.cos(a) * rr, gy + math.sin(a) * rr * 0.28, ramp_at(ramp, 0.95 - 0.8 * rp))


EFFECTS = [
    {"id": "impacts/hit-spark", "name": "Hit spark", "loop": False, "duration": 0.75, "fps": 12, "size": (72, 72), "pivot": (36, 36), "draw": draw_spark,
     "about": "A hit: a white flash star, streaks that fly out, shorten and cool, a shock ring and a few flying chips.", "tags": ["hit", "melee"],
     "options": {"size": 24, "streaks": 11, "debris": 8}},
    {"id": "impacts/shockwave", "name": "Shockwave", "loop": False, "duration": 1.0, "fps": 12, "size": (96, 64), "pivot": (48, 36), "draw": draw_shock,
     "about": "A ring racing out along the floor, kicking up billows of dust that drift up and thin out.", "tags": ["ground", "stomp"],
     "options": {"radius": 40, "dust": 16}},
    {"id": "explosions/small-explosion", "name": "Small explosion", "loop": False, "duration": 1.5, "fps": 12, "size": (96, 96), "pivot": (48, 80), "draw": draw_boom,
     "about": "A ground blast: a white flash, a fireball that cools from yellow to red, smoke that climbs, sparks and a floor ring.", "tags": ["blast", "fire"],
     "options": {"size": 1.0}},
]
