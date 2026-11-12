# SPDX-License-Identifier: AGPL-3.0-or-later
"""fire effects: torch (loop), fireball (loop)."""
import math
from ..core import TAU, Rng, clamp, lerp, disc_mask, seg, ramp_at
from ..ramps import RAMPS, resolve


def flame_mask(f, cx, base, height, width, t, ph=0.0, sway=3.0, crank=0.0):
    """a teardrop flame as a boolean mask: a column of discs whose width tapers to a point and whose centre sways. Everything is a function of
    t with whole-number cycles, so the loop closes."""
    m = f.mask(); n = max(3, int(height * 1.2))
    for i in range(n + 1):
        u = i / n
        w = width * (1 - u ** 1.5) ** 1.1 * clamp(u / 0.12 + 0.35, 0, 1)
        ox = sway * u ** 1.3 * (math.sin(TAU * (t + u * 0.45 + ph)) + 0.35 * math.sin(TAU * (2 * t + u * 0.9 + ph * 1.7))) + crank * u * u
        disc_mask(m, cx + ox, base - u * height, w / 2)
    return m


META_TORCH = {"id": "fire/torch", "name": "Torch", "loop": True, "duration": 1.0, "fps": 12, "size": (48, 84), "pivot": (24, 64),
              "about": "A wall torch: a licking teardrop flame on a wrapped head, tongues that break off, rising embers, light on the wood.",
              "tags": ["flame", "light", "ambient"], "options": {"height": 30, "width": 17, "embers": 9, "stick": True}}


def draw_torch(f, t, o):
    ramp = resolve(o.palette, "fire"); r = Rng(o.seed); cx, base = 24, 58; H, W = o.height, o.width
    wood = RAMPS["earth"]
    if o.stick:
        for y in range(base + 2, 82):
            for x in range(cx - 2, cx + 2): f.put(x, y, wood[1] if x == cx - 2 else wood[2] if x == cx - 1 else wood[3] if x == cx else wood[2])
        for y in range(base - 2, base + 8):                                     # the wrapped, pitch-soaked head
            for x in range(cx - 4, cx + 4): f.put(x, y, (24, 18, 16) if (x + y) % 3 else wood[0])
        for x in range(cx - 4, cx + 4): f.put(x, base + 8, wood[1])
    glow = 1 + 0.1 * math.sin(TAU * 2 * t)
    f.glow(cx, base - 12, 30, ramp[3], 0.5 * glow); f.glow(cx, base - 12, 17, ramp[4], 0.35 * glow)
    flick = 1 + 0.07 * math.sin(TAU * 2 * t + 1.0)
    big = flame_mask(f, cx, base, H * flick, W, t, 0.0, sway=3.2)
    for k, (dx, hh, ww, ph) in enumerate(((-5, 0.62, 0.42, 0.3), (5, 0.55, 0.4, 0.65))):                  # two side licks
        big |= flame_mask(f, cx + dx, base - 1, H * hh * (1 + 0.1 * math.sin(TAU * t + k * 2)), W * ww, t, ph, sway=2.4)
    f.fill(big, ramp[0:4], depth=W * 0.3)
    mid = flame_mask(f, cx, base - 1, H * 0.62 * flick, W * 0.5, t, 0.05, sway=2.4)
    f.fill(mid, ramp[2:5], depth=W * 0.2)
    core = flame_mask(f, cx, base - 1, H * 0.3, W * 0.26, t, 0.1, sway=1.2)
    f.fill(core, ramp[-3:], depth=2.5)
    for i in range(int(o.embers)):                                                     # embers: one whole cycle each, so the loop is seamless
        off, x0, sp, dr = r.u(), r.u(-5, 5), r.u(0.75, 1.0), r.u(-6, 6); p = (t * 1 + off) % 1.0
        if p > 0.92: continue
        x = cx + x0 * (1 - p) + dr * p + 2.0 * math.sin(TAU * (p * 1.5 + off)); y = base - 8 - p * (H * 1.5) * sp
        f.put(x, y, ramp_at(ramp, 0.95 - 0.8 * p)); f.glow(x, y, 3, ramp[3], 0.18 * (1 - p), steps=2)
    for i in range(3):                                                                 # flame tips torn off
        off = i / 3.0; p = (t + off) % 1.0; sz = 2.2 * (1 - p) ** 0.8
        if sz < 0.6: continue
        x = cx + 2.4 * math.sin(TAU * (t + 0.45 + 0.07 * i)) * 0.9 + (i - 1) * 2.0; y = base - H * (0.85 + 0.5 * p)
        f.disc(x, y, sz, ramp[2:], mode="core", bias=0.1)


META_BALL = {"id": "fire/fireball", "name": "Fireball", "loop": True, "duration": 1.0, "fps": 12, "size": (96, 40), "pivot": (70, 20),
             "about": "A fireball flying right: a churning white-hot head, a torn tail of flame cooling into smoke, embers shed behind.",
             "tags": ["projectile", "flame"], "options": {"radius": 9, "tail": 44}}


def draw_ball(f, t, o):
    import numpy as np
    ramp = resolve(o.palette, "fire"); r = Rng(o.seed); R = o.radius; hx, hy = 70, 20; L = o.tail
    f.glow(hx - 4, hy, 30, ramp[3], 0.55); f.glow(hx, hy, 15, ramp[4], 0.35)
    m = f.mask()
    for k in range(34):                                                                # head and one continuous tapering tail
        u = k / 33.0; x = hx - 2 - u * L; y = hy + 2.6 * u * math.sin(TAU * (t - u * 0.9)) + 1.2 * u * math.sin(TAU * (2 * t + u))
        rad = R * (1.0 - 0.93 * u ** 0.75) * (1 + 0.12 * math.sin(TAU * (2 * t - u * 2.2)))
        disc_mask(m, x, y, rad)
    for k in range(5):
        a = TAU * (t + k / 5.0); disc_mask(m, hx + 1.6 * math.cos(2 * a), hy + 1.6 * math.sin(2 * a), R * (0.8 + 0.08 * math.sin(3 * a)))
    xs = np.arange(f.w)[None, :].repeat(f.h, 0); g = -0.55 * np.clip((hx - xs) / L, 0, 1) ** 0.8
    f.fill(m, ramp, depth=R * 0.65, grad=g)
    c = f.mask(); disc_mask(c, hx + 1 * math.cos(TAU * t), hy + 1 * math.sin(TAU * t), R * 0.42); f.fill(c, ramp[-2:], depth=2)
    for i in range(5):                                                                 # torn-off licks behind the tail
        off = i / 5.0 + r.u(0, 0.1); p = (t + off) % 1.0; x = hx - L * (0.5 + 0.55 * p); y = hy + r.u(-5, 5) + 2 * math.sin(TAU * (p + off))
        rad = 3.2 * (1 - p) ** 0.9
        if rad > 0.7: f.disc(x, y, rad, ramp, mode="core", bias=0.1 - 0.7 * p)
    for i in range(8):                                                                 # single-pixel embers
        off = r.u(); p = (t + off) % 1.0; x = hx - 8 - p * L * 1.25; y = hy + r.u(-8, 8) * (0.3 + p)
        f.put(x, y, ramp_at(ramp, 0.9 - 0.85 * p))


EFFECTS = [dict(META_TORCH), dict(META_BALL)]
EFFECTS[0]["draw"] = draw_torch; EFFECTS[1]["draw"] = draw_ball
draw = None
