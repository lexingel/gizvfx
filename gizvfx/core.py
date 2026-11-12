# SPDX-License-Identifier: AGPL-3.0-or-later
"""gizvfx.core - the drawing surface and painter helpers for code-drawn pixel effects.

A Frame has two buffers, like a stage with lights: `rgb` + `a` (the pixels, opaque or translucent) and `light` (additive glow).
An effect is a function of time t in [0, 1]; everything random comes from a seeded generator that is rebuilt on every call, so
the same (effect, options, seed, t) always gives the same picture and a loop closes exactly. Nothing here reads a file or a clock.
Part of GizVFX; the two-buffer idea is common practice in pixel VFX."""
import math
import numpy as np
from PIL import Image

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16.0 + 1 / 32.0
TAU = math.tau


def hex2rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def clamp(v, lo=0.0, hi=1.0): return lo if v < lo else hi if v > hi else v


def lerp(a, b, t): return a + (b - a) * t


def smooth(t): t = clamp(t); return t * t * (3 - 2 * t)


def out_quart(t): t = clamp(t); return 1 - (1 - t) ** 4


def out_expo(t): t = clamp(t); return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def in_quad(t): t = clamp(t); return t * t


def seg(t, a, b):
    """progress of t through the window [a, b], 0 before and 1 after"""
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def ramp_at(ramp, v):
    """colour on a dark..bright ramp for v in 0..1 (hard steps: no blending, it is pixel art)"""
    i = int(clamp(v) * len(ramp)); return ramp[min(i, len(ramp) - 1)]


class Frame:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rgb = np.zeros((h, w, 3), np.uint8); self.a = np.zeros((h, w), np.uint8); self.light = np.zeros((h, w, 3), np.float32)

    # ---- single pixels -------------------------------------------------------------------------------------------
    def put(self, x, y, c, a=255):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            if a >= 255: self.rgb[y, x] = c; self.a[y, x] = 255
            elif a > 0:                                         # translucent: blend over what is there
                old = self.a[y, x] / 255.0; na = a / 255.0; tot = na + old * (1 - na)
                self.rgb[y, x] = (np.array(c) * na + self.rgb[y, x] * old * (1 - na)) / max(tot, 1e-6); self.a[y, x] = int(tot * 255)

    def dput(self, x, y, c, cover):
        """dithered translucency: the pixel is drawn only where the 4x4 Bayer threshold is below `cover` (0..1)"""
        x, y = int(x), int(y)
        if cover > BAYER[y & 3, x & 3]: self.put(x, y, c)

    # ---- shapes ----------------------------------------------------------------------------------------------------
    def _grid(self, cx, cy, r):
        x0, x1 = max(0, int(math.floor(cx - r - 1))), min(self.w, int(math.ceil(cx + r + 2)))
        y0, y1 = max(0, int(math.floor(cy - r - 1))), min(self.h, int(math.ceil(cy + r + 2)))
        if x0 >= x1 or y0 >= y1: return None
        yy, xx = np.mgrid[y0:y1, x0:x1]; return x0, x1, y0, y1, xx + 0.5, yy + 0.5

    def disc(self, cx, cy, r, ramp, lit=(-0.35, -0.45), mode="core", cover=1.0, bias=0.0):
        """a filled disc shaded by hard ramp steps. mode 'core': brightest in the middle (fire, energy).
        mode 'lit': brightest on the side facing `lit` (smoke, stone, ice). cover < 1 dithers it translucent."""
        g = self._grid(cx, cy, r)
        if g is None or r <= 0: return
        x0, x1, y0, y1, xx, yy = g; d = np.hypot(xx - cx, yy - cy); inside = d <= r
        if mode == "core": v = 1 - d / max(r, 1e-6)
        else:                                                    # sphere shading: brightest where the surface faces the light
            nx = (xx - cx) / max(r, 1e-6); ny = (yy - cy) / max(r, 1e-6); nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0, 1))
            lx, ly = lit; lz = 0.6; n = math.sqrt(lx * lx + ly * ly + lz * lz); v = np.clip((nx * lx + ny * ly + nz * lz) / n, 0, 1)
        v = np.clip(v + bias, 0, 0.999); idx = (v * len(ramp)).astype(int); cols = np.array(ramp, np.uint8)[idx]
        keep = inside if cover >= 1 else inside & (cover > np.tile(BAYER, (self.h // 4 + 1, self.w // 4 + 1))[y0:y1, x0:x1])
        sub_rgb = self.rgb[y0:y1, x0:x1]; sub_a = self.a[y0:y1, x0:x1]; sub_rgb[keep] = cols[keep]; sub_a[keep] = 255

    def ring(self, cx, cy, r, thick, ramp, v=None, cover=1.0, arc=None):
        """a ring of the given thickness. colour by distance across the band (inner dark .. outer bright) unless v is a fixed ramp position.
        arc = (a0, a1) in radians limits it to a part of the circle"""
        g = self._grid(cx, cy, r + thick)
        if g is None: return
        x0, x1, y0, y1, xx, yy = g; d = np.hypot(xx - cx, yy - cy); m = np.abs(d - r) <= thick / 2
        if arc is not None:
            ang = np.arctan2(yy - cy, xx - cx) % TAU; a0, a1 = arc[0] % TAU, arc[1] % TAU
            m &= (ang >= a0) & (ang <= a1) if a0 <= a1 else (ang >= a0) | (ang <= a1)
        if cover < 1: m &= cover > np.tile(BAYER, (self.h // 4 + 1, self.w // 4 + 1))[y0:y1, x0:x1]
        vv = np.full(d.shape, v) if v is not None else np.clip(0.5 + (d - r) / max(thick, 1e-6), 0, 0.999)
        cols = np.array(ramp, np.uint8)[(np.clip(vv, 0, 0.999) * len(ramp)).astype(int)]
        self.rgb[y0:y1, x0:x1][m] = cols[m]; self.a[y0:y1, x0:x1][m] = 255

    def ellipse(self, cx, cy, rx, ry, ramp, v=0.5, cover=1.0):
        g = self._grid(cx, cy, max(rx, ry))
        if g is None: return
        x0, x1, y0, y1, xx, yy = g; m = ((xx - cx) / max(rx, 1e-6)) ** 2 + ((yy - cy) / max(ry, 1e-6)) ** 2 <= 1
        if cover < 1: m &= cover > np.tile(BAYER, (self.h // 4 + 1, self.w // 4 + 1))[y0:y1, x0:x1]
        self.rgb[y0:y1, x0:x1][m] = ramp_at(ramp, v); self.a[y0:y1, x0:x1][m] = 255

    def line(self, x0, y0, x1, y1, c, width=1):
        """a straight line of whole pixels (Bresenham), width 1 or more"""
        x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1)); dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1); err = dx + dy; h = width // 2
        while True:
            for ox in range(-h, width - h):
                for oy in range(-h, width - h): self.put(x0 + ox, y0 + oy, c)
            if x0 == x1 and y0 == y1: break
            e2 = 2 * err
            if e2 >= dy: err += dy; x0 += sx
            if e2 <= dx: err += dx; y0 += sy

    def tapered(self, x0, y0, x1, y1, w0, w1, ramp, v=None, cover=1.0):
        """a stroke that changes width from w0 to w1 along its length (slash trails, flame tongues, beams)"""
        n = int(max(abs(x1 - x0), abs(y1 - y0))) * 2 + 1
        for i in range(n + 1):
            t = i / max(n, 1); w = lerp(w0, w1, t)
            if w >= 0.5: self.disc(lerp(x0, x1, t), lerp(y0, y1, t), w / 2, ramp, mode="core", cover=cover, bias=0.2 if v is None else v - 0.5)

    def mask(self): return np.zeros((self.h, self.w), bool)

    def fill(self, mask, ramp, depth=3.0, grad=None, cover=1.0, bias=0.0):
        """colour a whole shape by how deep each pixel is inside it: the edge takes the darkest ramp step, the middle the brightest. Hard bands,
        which is what gives flames and fireballs their layered pixel look. grad (same shape as the frame, -1..1) shifts the band, bias shifts all of it."""
        from scipy.ndimage import distance_transform_edt
        if not mask.any(): return
        d = distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1]; v = np.clip(d / max(depth, 1e-6), 0, 1) * 0.999 + bias
        if grad is not None: v = v + grad
        idx = (np.clip(v, 0, 0.999) * len(ramp)).astype(int); cols = np.array(ramp, np.uint8)[idx]
        keep = mask if cover >= 1 else mask & (cover > np.tile(BAYER, (self.h // 4 + 1, self.w // 4 + 1))[:self.h, :self.w])
        self.rgb[keep] = cols[keep]; self.a[keep] = 255

    def glow(self, cx, cy, r, c, k=1.0, steps=4, sq=1.0):
        """additive light: a round falloff quantized to a few steps so it keeps the pixel look"""
        g = self._grid(cx, cy, r)
        if g is None or r <= 0: return
        x0, x1, y0, y1, xx, yy = g; d = np.hypot(xx - cx, (yy - cy) / min(max(sq, 0.1), 1.0)) / r; f = np.clip(1 - d, 0, 1); f = np.ceil(f * steps) / steps * (d < 1)
        self.light[y0:y1, x0:x1] += f[..., None] * np.array(c, np.float32) / 255.0 * k

    # ---- output ----------------------------------------------------------------------------------------------------
    def image(self, bg=None, light=1.0, hard=False):
        """RGBA image: pixels, plus the light added on top of them; light that falls on empty space becomes a translucent glow.
        bg = (r, g, b) composites onto that colour instead (what a GIF needs)."""
        a = self.a.astype(np.float32) / 255.0; rgb = self.rgb.astype(np.float32); L = self.light * light * 255.0
        has = a > 0; out_rgb = np.where(has[..., None], np.clip(rgb + L, 0, 255), np.clip(L, 0, 255))
        gl = np.clip(L.max(-1) / 255.0, 0, 1) * 0.85; out_a = np.where(has, a, np.where(gl > 0.06, gl, 0))
        if hard:                                                                       # no half-transparent pixels: glow is dithered on or off, translucent pixels snap
            tile = np.tile(BAYER, (self.h // 4 + 1, self.w // 4 + 1))[:self.h, :self.w]
            out_a = np.where(has, (a >= 0.5).astype(np.float32), (gl > tile).astype(np.float32))
        res = np.dstack([out_rgb, out_a * 255]).astype(np.uint8)
        if bg is not None:
            al = out_a[..., None]; res = np.dstack([out_rgb * al + np.array(bg, np.float32) * (1 - al), np.full(a.shape, 255)]).astype(np.uint8)
        return Image.fromarray(res, "RGBA")


def disc_mask(m, cx, cy, r):
    """add a disc to the boolean mask m (in place) and return it"""
    h, w = m.shape; x0, x1 = max(0, int(cx - r - 1)), min(w, int(cx + r + 2)); y0, y1 = max(0, int(cy - r - 1)), min(h, int(cy + r + 2))
    if x0 >= x1 or y0 >= y1 or r <= 0: return m
    yy, xx = np.mgrid[y0:y1, x0:x1]; m[y0:y1, x0:x1] |= np.hypot(xx + 0.5 - cx, yy + 0.5 - cy) <= r; return m


class Rng:
    """seeded randomness that is rebuilt for every frame: `r = Rng(seed)`; the n-th draw is the same in every frame of an effect"""
    def __init__(self, seed): self.g = np.random.default_rng(int(seed))
    def u(self, lo=0.0, hi=1.0, n=None): return self.g.uniform(lo, hi, n)
    def i(self, lo, hi): return int(self.g.integers(lo, hi))
    def pick(self, seq): return seq[int(self.g.integers(0, len(seq)))]
