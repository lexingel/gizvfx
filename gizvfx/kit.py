# SPDX-License-Identifier: AGPL-3.0-or-later
"""gizvfx.kit - shapes shared by several effects (stars, jagged paths, ballistic points)."""
import math
from .core import TAU, ramp_at, lerp


def star(f, cx, cy, size, ramp, arms=4, thin=0.18, v=1.0):
    """a pointed star: `arms` spikes (4 = a plus, 8 adds diagonals), tapering from a thin body to a point; v = ramp position of the body"""
    for k in range(arms):
        a = TAU * k / arms + (math.pi / 4 if arms == 4 and False else 0)
        for s in range(int(size) + 1):
            u = s / max(size, 1); w = max(1.0, thin * size * (1 - u) * 2) if u < 0.85 else 1.0
            x, y = cx + math.cos(a) * s, cy + math.sin(a) * s
            if (arms == 8 and k % 2) and s > size * 0.6: continue
            f.disc(x, y, w / 2, ramp, mode="core", bias=v - 0.6)


def jagged(rng, x0, y0, x1, y1, depth=4, rough=0.28):
    """a lightning-like polyline from (x0,y0) to (x1,y1) by midpoint displacement; returns a list of points"""
    pts = [(x0, y0), (x1, y1)]
    for d in range(depth):
        out = [pts[0]]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            mx, my = (ax + bx) / 2, (ay + by) / 2; L = math.hypot(bx - ax, by - ay); nx, ny = -(by - ay) / max(L, 1e-6), (bx - ax) / max(L, 1e-6)
            off = rng.u(-1, 1) * L * rough; out += [(mx + nx * off, my + ny * off), (bx, by)]
        pts = out; rough *= 0.85
    return pts


def ballistic(x0, y0, vx, vy, g, tau):
    """position after tau (seconds-like units) with launch speed (vx, vy) and gravity g (down is +y)"""
    return x0 + vx * tau, y0 + vy * tau + 0.5 * g * tau * tau
