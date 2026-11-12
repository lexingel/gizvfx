# SPDX-License-Identifier: AGPL-3.0-or-later
"""gizvfx.painted - the same recipes, drawn smooth at S times the size with a painted look and a real alpha channel (no pixel palette, no dither).
brush, hatch, halftone, burst, speedlines, splat, glow, disc, ring are drawn natively smooth; every other layer is drawn as pixels and smoothly upscaled (see _bridge). Timing, options, palettes, `at`, `t`, `ease`, `v` work as in the pixel renderer,
so one recipe gives a pixel sprite sheet (`gizvfx render`) and a hi-res painted one (`gizvfx painted`).   python -m gizvfx painted ID --scale 4"""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from . import engine, spec as sp
from .core import Rng, seg, lerp, clamp
from .ramps import resolve

PAINTED = ("water", "wave", "brush", "hatch", "halftone", "glow", "disc", "ring", "burst", "speedlines", "splat", "particles", "blob", "star", "orbit", "beam", "funnel", "bolt", "rays", "poly")
STYLES = ("ink", "watercolor", "comic", "chalk", "linocut", "stencil", "glitch", "lineart")


def _col(ramp, v):
    """a smooth colour on the ramp (the pixel renderer takes hard steps)"""
    v = clamp(v * len(ramp) - 0.5, 0, len(ramp) - 1 - 1e-6); i = int(v); u = v - i; a = ramp[i]; b = ramp[min(i + 1, len(ramp) - 1)]                      # step k of the pixel ramp covers v in [k/n, (k+1)/n): its colour sits at its middle
    return tuple(int(a[k] + (b[k] - a[k]) * u) for k in range(3))


def _grain(w, h, seed, amount=0.18):
    """soft pigment grain: the same for every frame of an effect (no boiling)"""
    r = np.random.default_rng(seed); n = r.random((h // 3 + 2, w // 3 + 2)).astype(np.float32)
    big = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255.0
    fine = r.random((h, w)).astype(np.float32)
    return 1 - amount * (0.65 * big + 0.35 * fine)


def _brush(img, d, c, S):
    path = d["path"]; W = sp.val(d.get("width", 8), c.e) * S; tail = d.get("tail", 0.7); dry = d.get("dry", 0.6); nl = max(int(d.get("lanes", 7)) * 2 + 1, 9); core = d.get("core", 0.35)
    if W < 1.5 or c.e <= 0: return
    pw = math.log(0.5) / math.log(clamp(d.get("head", 0.4), 0.05, 0.95))
    hr = c.e * (1 + tail); s0 = hr - tail; rr = [Rng(c.seed * 7 + j).u(0, 1) for j in range(nl)]
    L = sum(math.hypot(a - b, e - g) for (a, e), (b, g) in zip(path[:-1], path[1:])); n = int(L * S * 0.6) + 4
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(lay); lane_w = max(1.0, W / nl * 1.5)
    pts = []
    for i in range(n + 1):
        q = i / n; u = lerp(s0, hr, q)
        if u < 0 or u > 1: pts.append(None); continue
        x, y = sp.pt(path, u); x2, y2 = sp.pt(path, min(1.0, u + 0.01)); x1, y1 = sp.pt(path, max(0.0, u - 0.01)); dx, dy = x2 - x1, y2 - y1; ln = math.hypot(dx, dy) or 1.0
        pts.append((c.ox + x * S, c.oy + y * S, -dy / ln, dx / ln, q, W * math.sin(math.pi * q ** pw) ** 0.8 / 2))
    ok = [q for q in pts if q is not None and q[5] >= 0.4]                                                    # a body under the bristle lanes, so the stroke is paint and not an outline
    if len(ok) > 3:
        poly = [(q[0] + q[2] * q[5] * 0.96, q[1] + q[3] * q[5] * 0.96) for q in ok] + [(q[0] - q[2] * q[5] * 0.96, q[1] - q[3] * q[5] * 0.96) for q in ok[::-1]]
        body = Image.new("L", img.size, 0); ImageDraw.Draw(body).polygon(poly, fill=int(255 * (0.55 + 0.25 * (1 - dry))))
        fade = Image.new("L", img.size, 0); fd = ImageDraw.Draw(fade)
        for q0, q1 in zip(ok[:-1], ok[1:]): fd.line([(q0[0], q0[1]), (q1[0], q1[1])], fill=int(255 * (1 - dry * (1 - q0[4]) ** 1.5)), width=int(2 * q0[5]) + 3)
        ba = np.asarray(body, np.float32) * np.asarray(fade.filter(ImageFilter.GaussianBlur(W * 0.25)), np.float32) / 255.0
        under = Image.new("RGBA", img.size, _col(c.ramp, 0.42) + (0,)); under.putalpha(Image.fromarray(ba.astype(np.uint8))); lay.alpha_composite(under)
    for j in range(nl):
        sv = (j + 0.5) / nl * 2 - 1; edge = abs(sv)
        base = 0.2 + 0.75 * (1 - edge) if edge < 1 - core else 0.2 + 0.1 * (1 - edge)
        for a, b in zip(pts[:-1], pts[1:]):
            if a is None or b is None or a[5] < 0.4 or b[5] < 0.4: continue
            q = a[4]; keep = clamp((rr[j] - dry * (1 - q) ** 1.2) * 7 + 0.35, 0, 1)                      # a dry lane thins out instead of cutting off
            if keep < 0.05: continue
            rgb = _col(c.ramp, min(base, 0.99) * (0.55 + 0.45 * q) + (c.v(0.5) - 0.5))
            xa, ya = a[0] + a[2] * sv * a[5], a[1] + a[3] * sv * a[5]; xb, yb = b[0] + b[2] * sv * b[5], b[1] + b[3] * sv * b[5]
            dr.line([(xa, ya), (xb, yb)], fill=rgb + (int(255 * keep * (0.85 + 0.15 * q)),), width=int(round(lane_w)))
    return lay.filter(ImageFilter.GaussianBlur(0.45 * S / 2))


def _shift(a, dx):
    """shift columns by dx, filling with nothing (np.roll would wrap a row round to the other edge)"""
    out = np.zeros_like(a)
    if dx > 0: out[:, dx:] = a[:, :-dx]
    elif dx < 0: out[:, :dx] = a[:, -dx:]
    else: out[:] = a
    return out


def _stylize(lay, style, S, seed, k=1.0):
    """the look of one layer: ink = as drawn; watercolor = wet edges, granulation, a soft bleed; comic = flat colour with a black outline; chalk = broken, dusty coverage"""
    from scipy.ndimage import gaussian_filter, binary_dilation
    if style == "ink": return lay
    a = np.asarray(lay, np.float32) / 255.0; al = a[..., 2 + 1]; rgb = a[..., :3]; h, w = al.shape; r = np.random.default_rng(seed)
    if style == "watercolor":
        core = gaussian_filter(al, 0.25 * S / 2); wide = gaussian_filter(al, 1.6 * S / 2); edge = np.clip(core - wide * 0.95, 0, 1) * 3.0
        gran = gaussian_filter(r.random((h, w)).astype(np.float32), 0.7) ; gran = (gran - gran.mean()) / (gran.std() + 1e-6) * 0.07
        mott = gaussian_filter(r.random((h, w)).astype(np.float32), 2.5 * S / 2); mott = (mott - mott.mean()) / (mott.std() + 1e-6) * 0.05
        bleed = gaussian_filter(al, 2.2 * S / 2) * 0.16
        out_a = np.clip(core * 0.9 + edge * 0.3 + bleed + gran * core, 0, 1); col = np.clip(rgb * (1 - 0.42 * np.clip(edge, 0, 1))[..., None] * (1 + mott)[..., None], 0, 1)
        lum = col.mean(-1, keepdims=True); col = np.clip(lum + (col - lum) * 1.25, 0, 1); col = 1 - (1 - col) * 0.92                  # pigment: a little more colour and a little lighter, never black
    elif style == "comic":
        m = gaussian_filter(al, 0.5 * S / 2) > 0.3; ring = binary_dilation(m, iterations=max(1, int(round(0.42 * S)))) & ~m
        col = np.floor(np.clip(rgb, 0, 0.999) * 4) / 3.0; col = np.clip(col * 1.05, 0, 1); col[ring] = (0.09, 0.08, 0.11); out_a = (m | ring).astype(np.float32)
    elif style == "chalk":
        n = gaussian_filter(r.random((h, w)).astype(np.float32), 0.45 * S / 4); n = (n - n.min()) / (n.max() - n.min() + 1e-6)
        cov = np.maximum(gaussian_filter(al, 0.8 * S / 2), al * 0.9); out_a = (cov * 1.35 > n * 0.95 + 0.05).astype(np.float32) * np.clip(cov * 1.5, 0, 1) * (0.8 + 0.2 * n)
        col = np.clip(rgb * 0.9 + 0.1, 0, 1); out_a = np.clip(out_a * 1.15, 0, 1)
    elif style == "linocut":                                                                                          # black ink on paper: the bright core is the gouged-out part, plus short gouge cuts
        from PIL import ImageDraw as _ID
        n = gaussian_filter(r.random((h, w)).astype(np.float32), 1.0 * S / 4); n = (n - n.min()) / (n.max() - n.min() + 1e-6); lum = rgb.mean(-1)
        m = (gaussian_filter(al, 0.7 * S / 2) + (n - 0.5) * 0.3 > 0.42) & ~((lum > 0.8) & (gaussian_filter(al, 2.5 * S / 2) > 0.4))
        cuts = Image.new("L", (w, h), 0); cd = _ID.Draw(cuts); ys, xs = np.nonzero(m)
        if len(xs):
            for _ in range(int(len(xs) / (S * S * 7)) + 1):
                i = int(r.integers(len(xs))); a0 = math.radians(35 + r.normal(0, 8)); L = r.uniform(2, 7) * S / 2; cd.line([(xs[i], ys[i]), (xs[i] + L * math.cos(a0), ys[i] + L * math.sin(a0))], fill=255, width=max(1, int(S * 0.4)))
        m = m & (np.asarray(cuts) < 128); col = np.zeros((h, w, 3), np.float32) + np.array([0.08, 0.07, 0.1], np.float32); out_a = m.astype(np.float32)
    elif style == "stencil":                                                                                          # spray paint: hard core, a mist of overspray dots
        core = gaussian_filter(al, 0.5 * S / 2) > 0.42; halo = gaussian_filter(al, 2.6 * S / 2); dots = (halo * 0.95 > r.random((h, w)).astype(np.float32)) & ~core
        col = np.floor(np.clip(rgb, 0, 0.999) * 4) / 3.0; out_a = np.where(core, 1.0, np.where(dots, 0.6, 0.0)).astype(np.float32)
    elif style == "glitch":                                                                                           # a broken screen: sliced rows, RGB split, scanlines. k = intensity (0 = off, 1 = normal, 2 = wrecked)
        if k <= 0: return lay
        out = np.dstack([rgb, al]); res = np.zeros_like(out); sh = max(1, int(S * 1.2 * min(k, 1.6)))
        for ch_, dx in ((0, -sh), (2, sh), (1, 0)): res[..., ch_] = _shift(out[..., ch_][..., None], dx)[..., 0]; res[..., 3] = np.maximum(res[..., 3], _shift(out[..., 3][..., None], dx)[..., 0] * (1.0 if ch_ == 1 else 0.85))
        for _ in range(min(9, int(r.integers(3, 7) * k + 0.5))):
            y0 = int(r.integers(0, h)); hh = int(r.integers(max(2, S // 2), max(3, S * 3))); dxs = int(r.integers(-S * 4, S * 4 + 1) * min(k, 1.5)); res[y0:y0 + hh] = _shift(res[y0:y0 + hh], dxs)
        rows = (np.arange(h) // max(1, S // 4)) % 2 == 0; col = res[..., :3] * np.where(rows, 1.0, 1 - 0.28 * min(k, 1.6))[:, None, None]; out_a = res[..., 3] * np.where(rows, 1.0, 1 - 0.12 * min(k, 1.6))[:, None]
    elif style == "lineart":                                                                                          # only the outline, one thin bright line with a glow (magic, energy, tracing); parts too thin for two lines become one solid line
        from scipy.ndimage import binary_erosion, binary_dilation as bd
        kk = max(1, int(round(0.4 * S))); m = gaussian_filter(al, 0.5 * S / 2) > 0.3; ring = m & ~binary_erosion(m, iterations=kk); inner = binary_erosion(m, iterations=2 * kk)
        near = bd(inner, iterations=2 * kk + 1); edge = (ring & near) | (m & ~near)
        line = gaussian_filter(edge.astype(np.float32), 0.35 * S / 2); glow = gaussian_filter(edge.astype(np.float32), 2.2 * S / 2)
        col = np.clip(1 - (1 - rgb) * 0.25, 0, 1); out_a = np.clip(line * 1.6 + glow * 0.55, 0, 1)
    else: raise ValueError(f"style must be one of {', '.join(STYLES)}")
    out = np.dstack([col, out_a]); return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGBA")


def _ellipse_mask(size, cx, cy, rx, ry, soft):
    m = Image.new("L", size, 0); ImageDraw.Draw(m).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
    return m.filter(ImageFilter.GaussianBlur(soft)) if soft else m


def _hatch(img, d, c, S):
    rx, ry = d.get("size", [14, 10]); rx *= S; ry *= S; ang = math.radians(d.get("angle", 45)); sp_ = max(1.5, d.get("spacing", 3)) * S; tone = sp.val(d.get("tone", 0.6), c.e); fade = d.get("fade", 0); fd = math.radians(d.get("fade_dir", 0))
    if tone <= 0.02: return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(lay); col = _col(c.ramp, c.v(0.3)); R = max(rx, ry); ca, sa = math.cos(ang), math.sin(ang); rng = Rng(c.seed * 11)
    k0 = int(-R / sp_) - 1
    for k in range(k0, -k0 + 1):
        r1 = Rng(c.seed * 11 + k).u(0, 1); g = (k * sp_ * -sa * math.cos(fd) + k * sp_ * ca * math.sin(fd)) / max(R, 1)
        if r1 >= clamp(tone * (1 - fade * (0.5 + 0.5 * g)), 0, 1): continue
        off = k * sp_; wob = Rng(c.seed * 13 + k).u(-0.6, 0.6) * S; ln = R * 1.2
        x0 = c.ox - sa * off - ca * ln; y0 = c.oy + ca * off - sa * ln; x1 = c.ox - sa * off + ca * ln; y1 = c.oy + ca * off + sa * ln
        dr.line([(x0, y0 + wob), ((x0 + x1) / 2, (y0 + y1) / 2 - wob), (x1, y1 + wob)], fill=col + (int(255 * Rng(c.seed * 17 + k).u(0.65, 1.0)),), width=max(1, int(S * 0.55)), joint="curve")
    m = _ellipse_mask(img.size, c.ox, c.oy, rx, ry, S * 0.4); a = np.asarray(lay.getchannel("A"), np.float32) * np.asarray(m, np.float32) / 255.0; lay.putalpha(Image.fromarray(a.astype(np.uint8)))
    return lay.filter(ImageFilter.GaussianBlur(0.3 * S / 2))


def _halftone(img, d, c, S):
    rx, ry = d.get("size", [14, 10]); rx *= S; ry *= S; cell = max(2.0, d.get("cell", 4)) * S; ang = math.radians(d.get("angle", 45)); tone = sp.val(d.get("tone", 0.6), c.e); fade = d.get("fade", 0); fd = math.radians(d.get("fade_dir", 0))
    if tone <= 0.02: return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(lay); col = _col(c.ramp, c.v(0.3)); ca, sa = math.cos(ang), math.sin(ang); R = max(rx, ry); n = int(R / cell) + 2
    for iu in range(-n, n + 1):
        for iv in range(-n, n + 1):
            u, v = (iu + 0.5) * cell, (iv + 0.5) * cell; x, y = u * ca - v * sa, u * sa + v * ca
            if (x / rx) ** 2 + (y / ry) ** 2 > 1: continue
            g = (x * math.cos(fd) + y * math.sin(fd)) / max(R, 1); tl = clamp(tone * (1 - fade * (0.5 + 0.5 * g)), 0, 1)
            r = cell * 0.5 * math.sqrt(tl)
            if r < 0.8: continue
            dr.ellipse([c.ox + x - r, c.oy + y - r, c.ox + x + r, c.oy + y + r], fill=col + (235,))
    return lay.filter(ImageFilter.GaussianBlur(0.3 * S / 2))


def _glow(img, d, c, S):
    r = sp.val(d.get("radius", 20), c.e) * S; k = sp.val(d.get("strength", 0.6), c.e, c.t)
    if r < 2 or k <= 0.02: return
    h, w = img.size[1], img.size[0]; yy, xx = np.mgrid[0:h, 0:w]; dd = np.hypot(xx - c.ox, (yy - c.oy) / min(max(sp.val(d.get("squash", 1), c.e), 0.1), 1.0)) / r; fo = np.clip(1 - dd, 0, 1); st_ = max(int(d.get("steps", 4)), 1); nn = fo * st_; fr_ = nn - np.floor(nn); sm_ = np.clip(fr_ / 0.14, 0, 1); sm_ = sm_ * sm_ * (3 - 2 * sm_)
    a = k * np.where(nn > 0, (np.floor(nn) + sm_) / st_, 0) * np.clip((1 - dd) / 0.1, 0, 1)                      # the pixel glow falls off in steps (ceil(f * steps) / steps): the same bands, with soft edges
    rgb = np.array(_col(c.ramp, c.v(0.6)), np.uint8); lay = np.zeros((h, w, 4), np.uint8); lay[..., :3] = rgb; lay[..., 3] = (np.where(a < 0.06, 0, a) * 255).astype(np.uint8)
    return Image.fromarray(lay, "RGBA")


def _disc(img, d, c, S, ring=False):
    r = sp.val(d.get("radius", 8 if not ring else 20), c.e) * S; th = sp.val(d.get("thick", 2), c.e) * S if ring else 0; sq = sp.val(d.get("squash", 1), c.e)
    if r < 1 or (ring and th < 0.5 * S): return                                                                   # a ring thinner than half a recipe pixel is gone, as in the pixel renderer
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(lay); col = _col(c.ramp, c.v(0.7 if not ring else 0.8)) + (255,)
    if ring:
        arc = d.get("arc"); nb = 1 if "v" in d else max(1, min(4, int(th / (0.8 * S))))                           # without a fixed `v` the band goes from dark (inside) to bright (outside), as in the pixel ring
        for b in range(nb):
            rb = r - th / 2 + th * (b + 0.5) / nb; wb = th / nb + 1; R = rb + wb / 2; box = [c.ox - R, c.oy - R * sq, c.ox + R, c.oy + R * sq]; cb = (col if nb == 1 else _col(c.ramp, 0.25 + 0.7 * (b + 0.5) / nb) + (255,))
            if arc is not None and sq == 1: dr.arc(box, arc[0], arc[1], fill=cb, width=max(1, int(wb)))
            else: dr.ellipse(box, outline=cb, width=max(1, int(wb)))
    else:                                                                                                         # a filled disc is shaded like the pixel one: brightest in the middle ("core") or on the lit side ("lit")
        h, w = img.size[1], img.size[0]; x0, x1, y0, y1 = max(0, int(c.ox - r - 2)), min(w, int(c.ox + r + 3)), max(0, int(c.oy - r - 2)), min(h, int(c.oy + r + 3))
        if x1 <= x0 or y1 <= y0: return
        yy, xx = np.mgrid[y0:y1, x0:x1]; dd = np.hypot(xx + 0.5 - c.ox, yy + 0.5 - c.oy) / r
        if d.get("mode", "core") == "lit": dd = np.hypot(xx + 0.5 - (c.ox - 0.35 * r), yy + 0.5 - (c.oy - 0.45 * r)) / (r * 1.25)
        v = np.clip(1 - dd, 0, 1) * 0.999 + sp.val(d.get("bias", 0), c.e); pos = np.clip(v, 0, 0.9999) * (len(c.ramp) - 1); i0 = pos.astype(int); fr = (pos - i0)[..., None]; R = np.array(c.ramp, np.float32)
        rgb = R[i0] * (1 - fr) + R[np.minimum(i0 + 1, len(c.ramp) - 1)] * fr; a = np.clip((1 - np.hypot(xx + 0.5 - c.ox, yy + 0.5 - c.oy) / r) * r + 0.5, 0, 1)
        arr = np.zeros((h, w, 4), np.uint8); arr[y0:y1, x0:x1, :3] = rgb.astype(np.uint8); arr[y0:y1, x0:x1, 3] = (a * 255).astype(np.uint8); lay = Image.fromarray(arr, "RGBA")
    return lay.filter(ImageFilter.GaussianBlur(0.4 * S / 2))


def _burst(img, d, c, S):
    P = sp.burst_poly(d, c.e, c.seed)
    if not P: return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(lay); pts = [(c.ox + x * S, c.oy + y * S) for x, y in P]
    dr.polygon(pts, fill=_col(c.ramp, c.v(0.55)) + (255,)); inner = [(c.ox + x * S * 0.62, c.oy + y * S * 0.62) for x, y in P]; dr.polygon(inner, fill=_col(c.ramp, min(0.95, c.v(0.55) + 0.3)) + (255,))
    if d.get("outline", True): dr.line(pts + [pts[0]], fill=_col(c.ramp, 0.0) + (255,), width=max(1, int(S * 0.5)), joint="curve")
    return lay.filter(ImageFilter.GaussianBlur(0.12 * S / 2))


def _speed(img, d, c, S):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(lay); col = _col(c.ramp, c.v(0.85)) + (255,); w = max(2.2, d.get("width", 1) * S * 1.9)
    for x0, y0, x1, y1 in sp.speed_segs(d, c.e, c.seed):
        ln = math.hypot(x1 - x0, y1 - y0) or 1.0; nx, ny = -(y1 - y0) / ln * w / 2, (x1 - x0) / ln * w / 2                      # a thin wedge: fat at the head, a point at the tail
        dr.polygon([(c.ox + x0 * S, c.oy + y0 * S), (c.ox + x1 * S + nx, c.oy + y1 * S + ny), (c.ox + x1 * S - nx, c.oy + y1 * S - ny)], fill=col)
    return lay.filter(ImageFilter.GaussianBlur(0.3 * S / 2))


def _splat(img, d, c, S):
    shapes = sp.splat_shapes(d, c.e, c.seed)
    if not shapes: return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(lay); col = _col(c.ramp, c.v(0.5)) + (255,); hi = _col(c.ramp, min(0.95, c.v(0.5) + 0.3)) + (255,)
    for sh in shapes:
        if sh[0] == "disc":
            x, y, r = c.ox + sh[1] * S, c.oy + sh[2] * S, sh[3] * S; dr.ellipse([x - r, y - r, x + r, y + r], fill=col); dr.ellipse([x - r * 0.55 - r * 0.15, y - r * 0.55 - r * 0.2, x + r * 0.45 - r * 0.15, y + r * 0.45 - r * 0.2], fill=hi)
        else:
            x0, y0, x1, y1, w = sh[1:]; dr.line([(c.ox + x0 * S, c.oy + y0 * S), (c.ox + x1 * S, c.oy + y1 * S)], fill=col, width=max(1, int(w * S))); r = w * S / 2; dr.ellipse([c.ox + x1 * S - r * 1.3, c.oy + y1 * S - r * 1.3, c.ox + x1 * S + r * 1.3, c.oy + y1 * S + r * 1.3], fill=col)
    return lay.filter(ImageFilter.GaussianBlur(0.35 * S / 2))


DRAW = {"water": lambda i, d, c, S: _water(i, d, c, S), "wave": lambda i, d, c, S: _wave(i, d, c, S), "funnel": lambda i, d, c, S: _funnel(i, d, c, S), "bolt": lambda i, d, c, S: _bolt(i, d, c, S), "rays": lambda i, d, c, S: _rays(i, d, c, S), "poly": lambda i, d, c, S: _poly(i, d, c, S), "orbit": lambda i, d, c, S: _orbit(i, d, c, S), "beam": lambda i, d, c, S: _beam(i, d, c, S), "particles": lambda i, d, c, S: _particles(i, d, c, S), "blob": lambda i, d, c, S: _blob(i, d, c, S), "star": lambda i, d, c, S: _star(i, d, c, S), "burst": _burst, "speedlines": _speed, "splat": _splat, "brush": _brush, "hatch": _hatch, "halftone": _halftone, "glow": _glow, "disc": _disc, "ring": lambda i, d, c, S: _disc(i, d, c, S, True)}


def _ramp_rgb(v, ramp):
    """colours along a ramp for an array of positions 0..1, smooth between the steps"""
    pos = np.clip(np.asarray(v) * len(ramp) - 0.5, 0, len(ramp) - 1 - 1e-6); i0 = pos.astype(int); fr = (pos - i0)[..., None]; R = np.array(ramp, np.float32)                      # same mapping as _col
    return R[i0] * (1 - fr) + R[np.minimum(i0 + 1, len(ramp) - 1)] * fr


def _star(img, d, c, S):
    """a sparkle: an even number of arms is a set of crossing lines with round ends (a plus for 4), an odd number is a polygon of spikes"""
    s = sp.val(d.get("size", 14), c.e) * S; arms = max(2, int(d.get("arms", 4))); thin = d.get("thin", 0.14)
    if s < 2: return
    R = s / 2; lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(lay); body = _col(c.ramp, min(c.v(1.0), 0.72)) + (255,); hot = _col(c.ramp, 0.999) + (255,)
    if arms % 2 == 0:
        wd = max(1.5 * S, s * thin * 1.6)
        for k in range(arms // 2):
            a = math.pi * k / (arms // 2) - math.pi / 2; w_ = wd if k == 0 or (arms // 2) == 1 else wd * 0.7; x0, y0, x1, y1 = c.ox - math.cos(a) * R, c.oy - math.sin(a) * R, c.ox + math.cos(a) * R, c.oy + math.sin(a) * R
            dr.line([(x0, y0), (x1, y1)], fill=body, width=max(1, int(w_))); 
            for ex, ey in ((x0, y0), (x1, y1)): dr.ellipse([ex - w_ / 2, ey - w_ / 2, ex + w_ / 2, ey + w_ / 2], fill=body)
        dr.ellipse([c.ox - wd * 0.8, c.oy - wd * 0.8, c.ox + wd * 0.8, c.oy + wd * 0.8], fill=hot)
    else:
        r = R * max(thin * 2.2, 0.16); pts = [(c.ox + (R if k % 2 == 0 else r) * math.cos(-math.pi / 2 + math.pi * k / arms), c.oy + (R if k % 2 == 0 else r) * math.sin(-math.pi / 2 + math.pi * k / arms)) for k in range(2 * arms)]
        dr.polygon(pts, fill=body); dr.ellipse([c.ox - r * 1.1, c.oy - r * 1.1, c.ox + r * 1.1, c.oy + r * 1.1], fill=hot)
    return lay.filter(ImageFilter.GaussianBlur(0.25 * S / 2))


def _particles(img, d, c, S):
    live = sp.particles_live(d, c.u); shape = d.get("shape", "dot"); streak = d.get("streak", 6)
    if not live: return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(lay)
    for age, x, y, ang, size, cv, vv in sorted(live, reverse=True):                                          # oldest first, as in the pixel renderer
        x, y, z = x * S, y * S, size * S; col = _col(c.ramp, vv); a = int(255 * clamp(cv, 0, 1)); ca, sa = math.cos(ang), math.sin(ang)
        if shape == "star":
            arm = z * 0.9; w = arm * 0.22; dr.polygon([(x, y - arm), (x + w, y - w), (x + arm, y), (x + w, y + w), (x, y + arm), (x - w, y + w), (x - arm, y), (x - w, y - w)], fill=col + (a,))
            dr.ellipse([x - w, y - w, x + w, y + w], fill=_col(c.ramp, 0.999) + (255,))
        elif shape == "bubble":
            if age < 0.8: dr.ellipse([x - max(z / 2, 1.2 * S), y - max(z / 2, 1.2 * S), x + max(z / 2, 1.2 * S), y + max(z / 2, 1.2 * S)], outline=col + (a,), width=max(1, int(S * 0.5)))
            else:
                for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)): dr.ellipse([x + dx * z * 0.7 - S * 0.4, y + dy * z * 0.7 - S * 0.4, x + dx * z * 0.7 + S * 0.4, y + dy * z * 0.7 + S * 0.4], fill=col + (a,))
        elif shape in ("shard", "streak"):
            if shape == "shard": tx, ty, wid = x + ca * z * 1.6, y + sa * z * 1.6, max(z * 0.6, 1) / 2                    # a sliver pointing along its flight
            else: L = streak * (1 - age * 0.7) * S; tx, ty, wid = x - ca * L, y - sa * L, max(z, S) / 2                  # a streak trailing behind the head
            nx, ny = -sa * wid, ca * wid; dr.polygon([(x + nx, y + ny), (x - nx, y - ny), (tx, ty)], fill=col + (a,))
        else:
            r = max(z / 2, 0.6 * S)
            if d.get("shade", "flat") == "core" and r > 1.2 * S:                                                      # brightest in the middle, as the pixel disc ("core"), with the same bias
                for fr_ in (1.0, 0.75, 0.5, 0.25): dr.ellipse([x - r * fr_, y - r * fr_, x + r * fr_, y + r * fr_], fill=_col(c.ramp, clamp((1 - fr_ * 0.95) + (vv - 0.5), 0, 0.999)) + (a,))
            else: dr.ellipse([x - r, y - r, x + r, y + r], fill=col + (a,))
    return lay.filter(ImageFilter.GaussianBlur(0.3 * S / 2))


def _blob(img, d, c, S):
    from scipy.ndimage import distance_transform_edt
    from .core import Frame
    rec = []; sp.L_blob(Frame(2, 2), d, c.u, rec=rec)
    if not rec: return
    W, H = img.size; m = Image.new("L", (W, H), 0); dr = ImageDraw.Draw(m)
    for x, y, r in rec:
        if r > 0: dr.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=255)
    mk = np.asarray(m) > 127; er = sp.val(d.get("erode", 0), c.e) * S
    if not mk.any(): return
    dist = distance_transform_edt(np.pad(mk, 1))[1:-1, 1:-1]
    if er > 0: mk = mk & (dist > er)
    if not mk.any(): return
    v = np.clip(dist / max(d.get("depth", 5) * S, 1e-6), 0, 1) * 0.999 + sp.val(d.get("bias", 0), c.e)
    if d.get("lit"):
        lx, ly = d["lit"]; k = d.get("lit_strength", 0.3); sx, sy = sp.rng2(d.get("spread"), [10, 10]); lo, hi = sp.rng2(d.get("radius"), [4, 8]); sc = sp.val(d.get("scale", 1), c.e); Rr = (max(sx, sy, hi) * max(sc, 0.2) + hi) * S
        yy, xx = np.mgrid[0:H, 0:W]; v = v + k * ((xx + 0.5 - c.ox) * lx + (yy + 0.5 - c.oy) * ly) / (math.hypot(lx, ly) * Rr)
    rgb = _ramp_rgb(v, c.ramp); a = np.asarray(Image.fromarray((mk * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.45 * S / 2)), np.float32) / 255 * float(sp.val(d.get("cover", 1), c.e))
    out = np.dstack([rgb, a * 255]).astype(np.uint8); return Image.fromarray(out, "RGBA")


def _orbit(img, d, c, S):
    n = int(d.get("count", 5)); R = sp.val(d.get("radius", 20), c.e) * S; sq = sp.val(d.get("squash", 1), c.e); turns = d.get("turns", 1); size = sp.val(d.get("size", 3), c.e) * S; trail = int(d.get("trail", 0))
    if size <= 0.2 * S or R < 0: return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(lay)
    for i in range(n):
        for j in range(trail, -1, -1):                                                                             # the tail first, the head on top
            a = sp.TAU * (i / n + c.p * turns) - j * 0.16; z = size * (1 - j / (trail + 1)); x, y = c.ox + math.cos(a) * R, c.oy + math.sin(a) * R * sq; r = max(z / 2, 0.6 * S)
            dr.ellipse([x - r, y - r, x + r, y + r], fill=_col(c.ramp, c.v(0.9) - 0.5 * j / (trail + 1)) + (255,))
            if d.get("shade", "flat") == "core" and r > 1.4 * S: dr.ellipse([x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45], fill=_col(c.ramp, 0.999) + (255,))
    return lay.filter(ImageFilter.GaussianBlur(0.3 * S / 2))


def _beam(img, d, c, S):
    x0, y0 = sp.pt(d.get("from", [0, 0]), c.e); x1, y1 = sp.pt(d.get("to", [30, 0]), c.e); w0 = sp.val(d.get("width", 4), c.e) * S; w1 = sp.val(d.get("tip", d.get("width", 4)), c.e) * S; ex = d.get("extend", 0)
    g = sp.out_expo(seg(c.p, 0, ex)) if ex > 0 else 1.0; ax, ay = c.ox + x0 * S, c.oy + y0 * S; bx, by = c.ox + lerp(x0, x1, g) * S, c.oy + lerp(y0, y1, g) * S
    if max(w0, w1) < 0.4 * S: return
    ln = math.hypot(bx - ax, by - ay) or 1.0; nx, ny = -(by - ay) / ln, (bx - ax) / ln; lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(lay)
    flat = d.get("shade") == "flat"; core = clamp(d.get("core", 0.45), 0.05, 0.95); levels = 1 if flat else 10; top = min(c.v(0.95), 0.999)
    for k in range(levels):                                                                                          # nested wedges from the rim inwards: dark at the edge, full colour from `core` of the width inwards, as in the pixel beam
        sc_ = 1.0 if flat else 1 - k / levels; q = (k + 0.5) / levels; v = top if flat else min(1.0, q / max(1 - core, 1e-3)) * top
        pts = [(ax + nx * w0 / 2 * sc_, ay + ny * w0 / 2 * sc_), (bx + nx * w1 / 2 * sc_, by + ny * w1 / 2 * sc_), (bx - nx * w1 / 2 * sc_, by - ny * w1 / 2 * sc_), (ax - nx * w0 / 2 * sc_, ay - ny * w0 / 2 * sc_)]
        dr.polygon(pts, fill=_col(c.ramp, v) + (255,))
    if not flat:                                                                                                       # a white-hot line down the middle
        k_ = core * 0.35; dr.polygon([(ax + nx * w0 / 2 * k_, ay + ny * w0 / 2 * k_), (bx + nx * w1 / 2 * k_, by + ny * w1 / 2 * k_), (bx - nx * w1 / 2 * k_, by - ny * w1 / 2 * k_), (ax - nx * w0 / 2 * k_, ay - ny * w0 / 2 * k_)], fill=_col(c.ramp, 0.999) + (255,))
    return lay.filter(ImageFilter.GaussianBlur(0.4 * S / 2))


def _funnel(img, d, c, S):
    """a swirling column drawn row by row at S times the resolution; the stripes follow the same formula as the pixel funnel"""
    H = int(sp.val(d.get("height", 40), c.e)); wb = sp.val(d.get("base", 6), c.e); wt = sp.val(d.get("top", 18), c.e); st = d.get("stripes", 3); tw = d.get("twist", 0.15); lean = d.get("lean", 0); fade = d.get("fade", 0); prof = d.get("profile"); bend = d.get("bend"); rip = d.get("ripple")
    if H <= 0: return
    Wp, Hp = img.size; arr = np.zeros((Hp, Wp, 4), np.uint8); xs = np.arange(Wp)
    for j in range(H * S):
        k = j / S; u = k / max(H - 1, 1); w = sp.val(prof, u) if prof else lerp(wb, wt, u); xc = c.ox + (lean * math.sin(u * math.pi + c.p * sp.TAU) + (sp.val(bend, u) if bend else 0)) * S; y = int(round(c.oy - j))
        if rip: w += rip[0] * math.sin(k * 0.3 + c.p * sp.TAU * rip[1])
        if w <= 0.05 or not (0 <= y < Hp): continue
        sx = np.clip((xs - xc) / (w * S), -1, 1); inside = np.abs(xs - xc) <= w * S; ph = np.arcsin(sx) + k * tw + c.p * d.get("turns", 1) * sp.TAU
        v = (0.3 + 0.55 * (0.5 + 0.5 * np.sin(st * ph))) * (1 - 0.45 * sx * sx) + (c.v(0.5) - 0.5); rgb = _ramp_rgb(v, c.ramp)
        edge = np.clip((w * S - np.abs(xs - xc)) / (0.6 * S) + 0.5, 0, 1) * (1 - fade * u)                          # a soft edge
        arr[y, :, :3] = np.where(inside[:, None], rgb, 0).astype(np.uint8); arr[y, :, 3] = (edge * 255 * inside).astype(np.uint8)
    lay = Image.fromarray(arr, "RGBA"); return lay.filter(ImageFilter.GaussianBlur(0.5 * S / 2))                       # the rows are 1 px apart at S: a small blur closes them


def _bolt(img, d, c, S):
    paths = sp.bolt_paths(d, c.u)
    if not paths: return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(lay)
    if d.get("glow"):
        r = d["glow"] * S; x, y = c.ox + (sp.pt(d.get("from", [0, -30]), c.e)[0] + sp.pt(d.get("to", [0, 30]), c.e)[0]) / 2 * S, c.oy + (sp.pt(d.get("from", [0, -30]), c.e)[1] + sp.pt(d.get("to", [0, 30]), c.e)[1]) / 2 * S
        yy, xx = np.mgrid[0:img.size[1], 0:img.size[0]]; a = np.clip(1 - np.hypot(xx - x, yy - y) / r, 0, 1) ** 2 * 0.5; g = np.zeros(a.shape + (4,), np.uint8); g[..., :3] = _col(c.ramp, 0.7); g[..., 3] = (a * 255).astype(np.uint8); lay = Image.fromarray(g, "RGBA"); dr = ImageDraw.Draw(lay)
    col = _col(c.ramp, c.v(0.65)); S_ = S
    if d.get("rim"):
        rc = tuple(sp.hex2rgb(d["rim"]))
        for pl, ww in paths: dr.line([(x * S_, y * S_) for x, y in pl], fill=rc + (255,), width=int(max(1, ww) * S_ + 2 * S_ * 0.5), joint="curve")
    for pl, ww in paths: dr.line([(x * S_, y * S_) for x, y in pl], fill=col + (255,), width=max(1, int(max(1, ww) * S_)), joint="curve")
    for pl, ww in paths:
        if ww >= 2 and not d.get("rim") and not d.get("color"): dr.line([(x * S_, y * S_) for x, y in pl], fill=tuple(int(v) for v in c.ramp[-1]) + (255,), width=max(1, int(S_ * 0.8)), joint="curve")   # a bright core
    return lay.filter(ImageFilter.GaussianBlur(0.4 * S / 2))


def _rays(img, d, c, S):
    n = int(d.get("count", 8)); r0 = sp.val(d.get("inner", 4), c.e) * S; ln = sp.val(d.get("length", 12), c.e) * S; rot = math.radians(sp.val(d.get("rotate", 0), c.e)); jit = d.get("jitter", 0); wd = d.get("width", 2) * S; sq = sp.val(d.get("squash", 1), c.e)
    if ln <= 0.5 * S: return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(lay); rg = c.u.rng; col = _col(c.ramp, c.v(0.8)) + (255,)
    for i in range(n):
        a = sp.TAU * i / n + rot; L = ln * (1 - jit * rg.u(0, 1)); x0, y0 = c.ox + math.cos(a) * r0, c.oy + math.sin(a) * r0 * sq; x1, y1 = x0 + math.cos(a) * L, y0 + math.sin(a) * L * sq
        nx, ny = -(y1 - y0), (x1 - x0); m = math.hypot(nx, ny) or 1.0; nx, ny = nx / m * wd / 2, ny / m * wd / 2
        dr.polygon([(x0 + nx, y0 + ny), (x0 - nx, y0 - ny), (x1, y1)], fill=col)                                    # a wedge, fat at the root and a point at the tip
    return lay.filter(ImageFilter.GaussianBlur(0.3 * S / 2))


def _wave(img, d, c, S):
    body, crest, streaks = sp.wave_geometry(d, c.e)
    if not body: return
    P = [(c.ox + x * S, c.oy + y * S) for x, y in body]
    m = Image.new("L", img.size, 0); ImageDraw.Draw(m).polygon(P, fill=255); mk = np.asarray(m) > 127
    if not mk.any(): return
    from scipy.ndimage import distance_transform_edt
    h, w = mk.shape; dist = distance_transform_edt(np.pad(mk, 1))[1:-1, 1:-1]; yy, xx = np.mgrid[0:h, 0:w]; lx, ly = d.get("lit", [-1, -1]); R = max(max(abs(x), abs(y)) for x, y in body) * S + 1
    Hc = max(sp.val(d.get("height", 24), c.e) * S, 1.0)
    v = np.clip(dist / max(d.get("depth", 2) * S, 1e-6), 0, 1) * 0.999 + d.get("lit_strength", 0.35) * ((xx + 0.5 - c.ox) * lx + (yy + 0.5 - c.oy) * ly) / (math.hypot(lx, ly) * R) + 0.6 * (c.oy - yy - 0.5) / Hc - 0.25 + sp.val(d.get("bias", -0.35), c.e)
    rgb = _ramp_rgb(v, c.ramp); al = np.asarray(m.filter(ImageFilter.GaussianBlur(0.35 * S / 2)), np.float32) / 255 * float(sp.val(d.get("cover", 1), c.e))
    lay = Image.fromarray(np.dstack([rgb, al * 255]).astype(np.uint8), "RGBA"); fo = sp.val(d.get("foam", 2), c.e)
    if fo >= 0.5:                                                                                  # foam along the crest and the lip
        dr = ImageDraw.Draw(lay); col = tuple(int(q) for q in c.ramp[-1]) + (255,); pts = [(c.ox + x * S, c.oy + y * S) for x, y in crest]
        dr.line(pts, fill=col, width=max(1, int(fo * S * 0.8)), joint="curve")
        for (x0, y0), (x1, y1) in streaks: dr.line([(c.ox + x0 * S, c.oy + y0 * S), (c.ox + x1 * S, c.oy + y1 * S)], fill=col, width=max(1, int(S * 0.7)))
        lay = lay.filter(ImageFilter.GaussianBlur(0.3 * S / 2))
    return lay


def _water(img, d, c, S):
    poly, top = sp.water_geometry(d, c.e, c.t)
    if not poly: return
    P = [(c.ox + x * S, c.oy + y * S) for x, y in poly]
    m = Image.new("L", img.size, 0); ImageDraw.Draw(m).polygon(P, fill=255); mk = np.asarray(m) > 127
    if not mk.any(): return
    from scipy.ndimage import distance_transform_edt
    h, w = mk.shape; dist = distance_transform_edt(np.pad(mk, 1))[1:-1, 1:-1]; yy = np.mgrid[0:h, 0:w][0]; Dc = max(sp.val(d.get("depth", 10), c.e) * S, 1.0)
    v = np.clip(dist / max(d.get("edge", 1.5) * S, 1e-6), 0, 1) * 0.999 + 0.6 * (c.oy - yy - 0.5) / Dc + 0.1 + sp.val(d.get("bias", -0.35), c.e)
    rgb = _ramp_rgb(v, c.ramp); al = np.asarray(m.filter(ImageFilter.GaussianBlur(0.35 * S / 2)), np.float32) / 255 * float(sp.val(d.get("cover", 1), c.e))
    lay = Image.fromarray(np.dstack([rgb, al * 255]).astype(np.uint8), "RGBA"); fo = sp.val(d.get("foam", 1), c.e)
    if fo >= 0.5:
        dr = ImageDraw.Draw(lay); dr.line([(c.ox + x * S, c.oy + y * S) for x, y in top], fill=tuple(int(q) for q in c.ramp[-1]) + (255,), width=max(1, int(fo * S * 0.8)), joint="curve"); lay = lay.filter(ImageFilter.GaussianBlur(0.3 * S / 2))
    return lay


def _poly(img, d, c, S):
    pts = d.get("points") or sp.POLYS[d.get("shape", "crystal")]; sc = sp.val(d.get("scale", 1), c.e); a = math.radians(sp.val(d.get("rotate", 0), c.e) + getattr(c, "tilt", 0.0)); ca, sa = math.cos(a), math.sin(a)
    if sc <= 0.05: return
    ay = -max(y for x, y in pts) if d.get("anchor") == "base" else 0.0
    P = [(c.ox + (x * ca - (y + ay) * sa) * sc * S, c.oy + (x * sa + (y + ay) * ca) * sc * S) for x, y in pts]
    m = Image.new("L", img.size, 0); ImageDraw.Draw(m).polygon(P, fill=255); mk = np.asarray(m) > 127
    if not mk.any(): return
    from scipy.ndimage import distance_transform_edt
    h, w = mk.shape; dist = distance_transform_edt(np.pad(mk, 1))[1:-1, 1:-1]; yy, xx = np.mgrid[0:h, 0:w]; lx, ly = d.get("lit", [-1, -1]); R = (max(max(abs(x), abs(y)) for x, y in pts) * sc + 1) * S
    v = np.clip(dist / max(d.get("depth", 4) * S, 1e-6), 0, 1) * 0.999 + d.get("lit_strength", 0.35) * ((xx + 0.5 - c.ox) * lx + (yy + 0.5 - c.oy) * ly) / (math.hypot(lx, ly) * R) + sp.val(d.get("bias", 0), c.e)
    rgb = _ramp_rgb(v, c.ramp); al = np.asarray(m.filter(ImageFilter.GaussianBlur(0.35 * S / 2)), np.float32) / 255 * float(sp.val(d.get("cover", 1), c.e)); out = np.dstack([rgb, al * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


_DEPTH = [0]


def _include(meta, d, c, S, style, opts, tick, o):
    """an included recipe, drawn smooth by this renderer: its time is stretched over this layer's window and its pivot is this layer's `at`"""
    if _DEPTH[0] >= 2: raise ValueError("include is nested more than 2 deep")
    mod, m2 = engine.get(d["recipe"])
    if "recipe" not in m2: raise ValueError(f"include: '{d['recipe']}' is drawn by Python code; only recipes can be included")
    sub = dict(m2["recipe"]); sub["pivot"] = [c.u.ox, c.u.oy]; o2 = engine.options(m2, d.get("options")); o2.seed = c.seed
    if d.get("palette") not in (None, "main"): o2.palette = d["palette"]
    meta2 = dict(m2); meta2["size"] = meta["size"]; meta2["recipe"] = sub
    _DEPTH[0] += 1
    try: return render_frame(meta2, o2, c.p, S, style, opts, tick, inner=True)
    finally: _DEPTH[0] -= 1


def _post(lay, d, c, S):
    """erode / outline on one layer, as in the pixel renderer (rim is pixel-only)"""
    if lay is None: return lay
    from scipy.ndimage import distance_transform_edt, binary_dilation
    a = np.asarray(lay.getchannel("A"), np.float32) / 255
    er = sp.val(d.get("erode", 0), c.e) if d["type"] != "blob" else 0
    if er > 0:
        dist = distance_transform_edt(np.pad(a > 0.5, 1))[1:-1, 1:-1]; a = a * np.clip((dist - er * S) / (0.6 * S) + 0.5, 0, 1); arr = np.asarray(lay).copy(); arr[..., 3] = (a * 255).astype(np.uint8); lay = Image.fromarray(arr, "RGBA")
    if isinstance(d.get("rim"), (list, tuple)):                                                                       # a lighter edge on the side facing the light, as in the pixel renderer
        dx, dy = d["rim"]; sdx, sdy = int(np.sign(dx)), int(np.sign(dy)); kk = max(1, int(round(0.6 * S))); m = a > 0.4; Hh, Ww = m.shape; sh = np.zeros_like(m)
        ys, xs = np.nonzero(m); ys2, xs2 = ys - sdy * kk, xs - sdx * kk; ok = (ys2 >= 0) & (ys2 < Hh) & (xs2 >= 0) & (xs2 < Ww); sh[ys2[ok], xs2[ok]] = True      # the mask moved the way the pixel rim looks: what is not covered after the move is the lit edge
        rm = m & ~np.roll(np.roll(m, -sdy * kk, 0), -sdx * kk, 1); arr = np.asarray(lay).copy(); arr[rm, :3] = c.ramp[-2] if len(c.ramp) > 2 else c.ramp[-1]; lay = Image.fromarray(arr, "RGBA")
    if d.get("outline"):
        m = a > 0.4; ring = binary_dilation(m, iterations=max(1, int(round(0.45 * S)))) & ~m; oc = c.ramp[0] if d["outline"] == "auto" else sp.hex2rgb(d["outline"])
        ol = np.zeros(a.shape + (4,), np.uint8); ol[ring] = tuple(oc) + (255,); res = Image.fromarray(ol, "RGBA"); res.alpha_composite(lay); lay = res
    return lay


def _ctx(meta, d, i, t, o, S, main, vs=0.0):
    spec = meta["recipe"]; px, py = spec["pivot"]; t0, t1 = d.get("t", [0, 1]); p = seg(t, t0, t1); sp._SEG[0] = d["ease"] if isinstance(d.get("ease"), list) else None; e = sp._efn(d)(p); (ox, oy), tilt = sp.at_xy(spec, d, t, e, o)
    if d.get("spin"): ox += d["spin"][0] * math.cos(sp.TAU * d["spin"][1] * p); oy += d["spin"][0] * math.sin(sp.TAU * d["spin"][1] * p)
    if d.get("wobble"): w_ = d["wobble"]; ox += w_[0] * math.sin(sp.TAU * (t * w_[2])); oy += w_[1] * math.sin(sp.TAU * (t * w_[2] + 0.25))
    vv = d.get("v"); seed = int(o.seed) * 131 + int(d.get("seed", i)) * 17; ramp = sp._ramp(d, main, sp._roles(spec, o)); vf = lambda default, vv=vv, e=e: sp.val(default if vv is None else vv, e) + vs
    u = type("C", (), {})(); u.t, u.p, u.e = t, p, e; u.ox, u.oy = px + ox, py + oy; u.px0, u.py0 = px, py; u.ramp, u.seed, u.sc, u.v, u.loop, u.dir = ramp, seed, 1.0, vf, bool(spec.get("loop")), spec.get("_dir"); u.rng = Rng(seed)
    def _atf(tt):                                                                                                       # where this layer is at another moment (a `drop` of particles asks)
        sv = sp._SEG[0]; sp._SEG[0] = d["ease"] if isinstance(d.get("ease"), list) else None
        try: return sp.at_xy(spec, d, tt, sp._efn(d)(seg(tt, t0, t1)), o)[0]
        finally: sp._SEG[0] = sv
    u.at_fn = _atf
    c = type("C", (), {})(); c.t, c.p, c.e = t, p, e; c.tilt = tilt; c.ox, c.oy = u.ox * S, u.oy * S; c.ramp, c.seed, c.v, c.u = ramp, seed, vf, u
    return c


def _layers(meta, d, i, t, o, S, main, style, opts, tick, vs=0.0):
    """the images one layer draws at time t (soft light first, then the styled body)"""
    c = _ctx(meta, d, i, t, o, S, main, vs); W, H = meta["size"]; hold = max(1, int((opts or {}).get("hold", 2))); k = float((opts or {}).get("intensity", 1.0)); gs = (tick // hold) * 7919 if style == "glitch" else 0; stub = type("I", (), {"size": (W * S, H * S)})()
    if d["type"] in DRAW:
        lay = _post(DRAW[d["type"]](stub, d, c, S), d, c, S)
        if lay is None: return []
        return [("light", lay)] if d["type"] == "glow" else [("solid", _stylize(lay, style, S, c.seed + gs, k))]
    glow, solid = _bridge(meta, d, i, t, o, S, main, vs)
    if glow is None: return []
    return [("light", glow), ("solid", _stylize(_post(solid, d, c, S), style, S, c.seed + gs, k))]


def _bridge(meta, d, i, t, o, S, main, vs=0.0):
    """a layer with no native painted version: the pixel layer is drawn at the recipe size, then smoothly upscaled (a premultiplied bicubic resize and a crisp alpha); the soft light and the solid body are returned apart"""
    from .core import Frame
    W, H = meta["size"]; spec = meta["recipe"]; px, py = spec["pivot"]; g = Frame(W, H); sp._one(spec, g, d, i, t, px, py, main, o, 1.0, vs)
    if not (g.a.any() or g.light.any()): return None, None
    im = g.image(light=1.0); up = im.convert("RGBa").resize((W * S, H * S), Image.BICUBIC).convert("RGBA")
    opq = Image.fromarray(np.where(g.a > 0, 255, 0).astype(np.uint8), "L").resize((W * S, H * S), Image.BICUBIC)
    sharp = np.clip((np.asarray(opq, np.float32) / 255 - 0.4) / 0.2, 0, 1); a_up = np.asarray(up.getchannel("A"), np.float32) / 255
    glow = np.asarray(up).copy(); ga = np.clip(a_up * (1 - sharp) * 0.8, 0, 1); glow[..., 3] = (np.where(ga < 0.06, 0, ga) * 255).astype(np.uint8)       # soft light: a faint tail is cut before it reaches the edge, and it stays soft in every style
    solid = np.asarray(up).copy(); solid[..., 3] = (sharp * 255).astype(np.uint8)
    return Image.fromarray(glow, "RGBA"), Image.fromarray(solid, "RGBA")


def render_frame(meta, o, t, S, style="ink", opts=None, tick=0, inner=False):
    spec = meta["recipe"]; W, H = meta["size"]; img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); main = resolve(o.palette, spec["palette"]); light = np.zeros((H * S, W * S, 3), np.float32)
    for i, d in enumerate(spec["layers"]):
        d = sp.sub(d, o); t0, t1 = d.get("t", [0, 1]); sm = d.get("smear"); n = 24 if sm else 0                                                                          # twice the copies of the pixel trail: smooth, not stair steps
        for k in range(n, -1, -1):                                                                                 # a smear: older copies first, fainter and darker, then the real layer
            tk = t; alpha = 1.0; vs = 0.0
            if k:
                if not spec["loop"] and t >= t1: continue
                tk = (t - k / n * sm[0] * (t1 - t0)) % 1.0 if spec["loop"] else t - k / n * sm[0] * (t1 - t0); alpha = 1 - (1 - sm[1]) * k / n; vs = -0.45 * k / n
            if tk < t0 or (tk > t1 and not d.get("hold")): continue
            dk = sp.resolve_pts(spec, d, tk, o)
            for kind, lay in (_layers(meta, dk, i, tk, o, S, main, ("ink" if k and style in ("comic", "linocut", "stencil") else style), opts, tick, vs) if d["type"] != "include" else [("solid", _include(meta, dk, _ctx(meta, dk, i, tk, o, S, main, vs), S, style, opts, tick, o))]):
                arr = np.asarray(lay)
                if kind == "light": light += arr[..., :3].astype(np.float32) / 255 * (arr[..., 3:4].astype(np.float32) / 255) * alpha                         # light is added to everything under it at the end, as in the pixel renderer
                else:
                    if alpha < 1: arr = arr.copy(); arr[..., 3] = (arr[..., 3] * alpha).astype(np.uint8); lay = Image.fromarray(arr, "RGBA")
                    if k: lay = lay.filter(ImageFilter.GaussianBlur(0.7 * S))                                                  # a trail copy is softened: the stacked bands of a disc melt into one streak
                    img.alpha_composite(lay)
    if light.any():                                                                                                   # the light: it brightens what is under it, and on empty ground it is a soft translucent glow
        arr = np.asarray(img).astype(np.float32); has = arr[..., 3] > 4; add = np.clip(light, 0, 1) * 255 * float(o.light)
        arr[..., :3] = np.where(has[..., None], np.clip(arr[..., :3] + add, 0, 255), np.clip(add, 0, 255)); ga = np.where(add.max(-1) / 255 > 0.06, np.clip(add.max(-1) / 255 * 0.85, 0, 1) * 255, 0); arr[..., 3] = np.maximum(arr[..., 3], ga)
        img = Image.fromarray(arr.astype(np.uint8), "RGBA")
    if inner: return img
    a = np.asarray(img.getchannel("A"), np.float32) * _grain(W * S, H * S, int(o.seed) + 5, 0.14 if o.hard is False else 0.0)
    a[:S], a[-S:], a[:, :S], a[:, -S:] = 0, 0, 0, 0                                                                  # the outermost recipe pixel stays empty (outlines and glitch shifts may not reach the canvas edge)
    img.putalpha(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)))
    return img


def render(eid, given=None, frames=None, fps=None, scale=4, style="ink", opts=None):
    mod, meta = engine.get(eid); o = engine.options(meta, given); n = engine.n_frames(meta, frames, fps); out = []
    if "recipe" not in meta: raise ValueError(f"'{eid}' is drawn by Python code; only recipes have a painted version")
    for i in range(n):
        t = i / n if meta["loop"] else i / (n - 1); im = render_frame(meta, o, t, int(scale), style, opts, i)
        out.append(im.transpose(Image.FLIP_LEFT_RIGHT) if o.flip else im)
    return out


def check(eid, scale=2, style="ink", opts=None):
    """deterministic, one-shot ends empty, nothing touches the edge"""
    mod, meta = engine.get(eid); o = engine.options(meta); bad = []
    a = render_frame(meta, o, 0.5, scale, style, opts, 3); b = render_frame(meta, o, 0.5, scale, style, opts, 3)
    if np.asarray(a).tobytes() != np.asarray(b).tobytes(): bad.append("not deterministic")
    if not meta["loop"] and np.asarray(render_frame(meta, o, 1.0, scale, style, opts, 9).getchannel("A")).max() > 12: bad.append("one-shot does not end empty")
    n = engine.n_frames(meta)
    for i in range(n):
        t = i / n if meta["loop"] else i / (n - 1); al = np.asarray(render_frame(meta, o, t, scale, style, opts, i).getchannel("A"))
        if (al[0] > 190).any() or (al[-1] > 190).any() or (al[:, 0] > 190).any() or (al[:, -1] > 190).any():                              # drawn pixels, as in the pixel check; a faint glow may reach the edge
            bad.append(f"frame {i} touches the canvas edge"); break
    return bad
