# SPDX-License-Identifier: AGPL-3.0-or-later
"""gizvfx.gifsheet - PNG, GIF, sprite sheet + JSON (TexturePacker "hash" frames + Aseprite-style frameTags, so Godot/Phaser/Unity importers read it)."""
import json, os
from PIL import Image


def palette_frames(frames):
    """RGBA frames -> palette ('P') frames that share ONE palette, so a colour is the same index in every frame
    (a palette per frame made colours flash). Index 0 is kept for transparency only when some frame has transparent pixels.
    Up to 256 colours (255 with transparency) are kept exactly; more are quantized together without dithering.
    Returns (frames, has_transparency)."""
    import numpy as np
    arrs = [np.array(f.convert("RGBA")) for f in frames]; trans = any((a[..., 3] < 128).any() for a in arrs); off = 1 if trans else 0
    keys = np.array([65536, 256, 1], dtype=np.uint32)
    packed = [a[..., :3].astype(np.uint32) @ keys for a in arrs]
    cols = np.unique(np.concatenate([k[a[..., 3] >= 128] for k, a in zip(packed, arrs)]))
    out = []
    if len(cols) <= 256 - off:
        flat = [0, 0, 0] * off + [v for c in cols for v in (int(c) >> 16, (int(c) >> 8) & 255, int(c) & 255)]
        for k, a in zip(packed, arrs):
            ix = (np.searchsorted(cols, k) + off).astype(np.uint8)
            if trans: ix[a[..., 3] < 128] = 0
            out.append(ix)
    else:
        h = arrs[0].shape[0]; mont = Image.new("RGB", (arrs[0].shape[1], h * len(arrs)))
        for i, a in enumerate(arrs): mont.paste(Image.fromarray(a[..., :3]), (0, i * h))
        q = mont.quantize(256 - off, method=0, dither=0)
        flat = [0, 0, 0] * off + q.getpalette()[:3 * (256 - off)]
        for i, a in enumerate(arrs):
            ix = np.array(q.crop((0, i * h, a.shape[1], (i + 1) * h)), dtype=np.uint8) + off
            if trans: ix[a[..., 3] < 128] = 0
            out.append(ix)
    res = []
    for ix in out:
        im = Image.fromarray(ix, "P"); im.putpalette(flat + [0] * (768 - len(flat))); res.append(im)
    return res, trans


def save_gif(frames, path, ms=120):
    """one shared palette for all frames; transparent index only when the picture really has transparent pixels"""
    ps, trans = palette_frames(frames)
    kw = {"transparency": 0} if trans else {}
    ps[0].save(path, save_all=True, append_images=ps[1:], duration=ms, loop=0, disposal=2, optimize=False, **kw)


def sheet(frames, name, cols=None, pad=1, ms=120, scale=1):
    """(image, json dict): frames laid out in a grid, all cells the size of the biggest frame, with one animation tag 'idle'"""
    cols = cols or len(frames); rows = -(-len(frames) // cols); w = max(f.width for f in frames); h = max(f.height for f in frames)
    im = Image.new("RGBA", (cols * (w + pad) + pad, rows * (h + pad) + pad), (0, 0, 0, 0)); fr = {}
    for i, f in enumerate(frames):
        x, y = pad + (i % cols) * (w + pad), pad + (i // cols) * (h + pad); im.paste(f, (x + (w - f.width) // 2, y + (h - f.height)));
        fr[f"{name}_{i}"] = {"frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False, "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h}, "sourceSize": {"w": w, "h": h}, "duration": ms}
    meta = {"app": "gizvfx", "image": f"{name}_sheet.png", "format": "RGBA8888", "size": {"w": im.width, "h": im.height}, "scale": "1",
            "frameTags": [{"name": "idle", "from": 0, "to": len(frames) - 1, "direction": "forward"}] if len(frames) > 1 else []}
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        for f in fr.values():
            for k in ("frame", "spriteSourceSize"): f[k] = {q: val * scale for q, val in f[k].items()}
            f["sourceSize"] = {q: val * scale for q, val in f["sourceSize"].items()}
        meta["size"] = {"w": im.width, "h": im.height}
    return im, {"frames": fr, "meta": meta}

