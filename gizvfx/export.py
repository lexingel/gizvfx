# SPDX-License-Identifier: AGPL-3.0-or-later
"""gizvfx.export - GIF, sprite sheet + JSON (Aseprite-style, with gizvfx meta) and contact sheets for looking at an effect."""
import json, os
from PIL import Image, ImageDraw
from .gifsheet import save_gif, sheet as _sheet

DARK = (30, 30, 38)


def up(im, scale): return im if scale == 1 else im.resize((im.width * scale, im.height * scale), Image.NEAREST)


def write_all(frames, out_dir, name, meta, opts, fps, scale=1, gif=True, sheet=True, contact=True, bg=DARK, hold=4, contact_scale=None, contact_bg=None):
    os.makedirs(out_dir, exist_ok=True); paths = []; ms = int(round(1000 / fps))
    if sheet:
        im, js = _sheet([f for f in frames], name, ms=ms, scale=scale)
        js["meta"]["gizvfx"] = js["meta"]["pixfx"] = {"id": meta["id"], "fps": fps, "loop": bool(meta["loop"]), "frame_size": [frames[0].width * scale, frames[0].height * scale],
                               "frames": len(frames), "pivot": [meta.get("pivot", (frames[0].width // 2, frames[0].height // 2))[0] * scale, meta.get("pivot", (0, frames[0].height // 2))[1] * scale],
                               "options": {k: v for k, v in opts.items() if k != "flip" or v}}
        p = os.path.join(out_dir, f"{name}_sheet.png"); im.save(p); paths.append(p)
        p = os.path.join(out_dir, f"{name}_sheet.json"); json.dump(js, open(p, "w", encoding="utf-8"), indent=1); paths.append(p)
    if gif:
        fr = [up(f.convert("RGBA"), scale) for f in frames]
        if bg is not None:
            fr = [Image.alpha_composite(Image.new("RGBA", f.size, tuple(bg) + (255,)), f) for f in fr]
        if not meta["loop"] and hold:
            blank = fr[-1].copy(); blank.paste(tuple(bg) + (255,) if bg is not None else (0, 0, 0, 0), (0, 0, blank.width, blank.height)); fr += [blank] * hold
        p = os.path.join(out_dir, f"{name}.gif"); save_gif(fr, p, ms); paths.append(p)
    if contact:
        p = os.path.join(out_dir, f"{name}_contact.png"); contact_sheet(frames, p, scale=contact_scale or max(scale, 2), bg=contact_bg or bg or DARK); paths.append(p)
    return paths


def contact_sheet(frames, path, scale=3, cols=None, bg=DARK, maxw=2400):
    """frames in a grid of about the shape of a page (not one long column); tiles are shrunk when the sheet would be wider than maxw (2400 px)"""
    import math
    n = len(frames); w, h = frames[0].size; tw, th = w * scale, h * scale
    cols = cols or max(1, min(n, math.ceil(math.sqrt(n * th / tw))))                                           # about as wide as tall; tiles shrink to fit maxw
    f = min(1.0, (maxw - 6) / (cols * (tw + 6))) if cols * (tw + 6) > maxw else 1.0                           # one tile wider than maxw: shrink them all
    tw, th = max(1, int(tw * f)), max(1, int(th * f)); rows = -(-n // cols)
    S = Image.new("RGB", (cols * (tw + 6) + 6, rows * (th + 20) + 6), (22, 22, 28)); d = ImageDraw.Draw(S)
    for i, fr in enumerate(frames):
        x, y = 6 + (i % cols) * (tw + 6), 6 + (i // cols) * (th + 20)
        tile = Image.alpha_composite(Image.new("RGBA", fr.size, tuple(bg) + (255,)), fr.convert("RGBA")).resize((tw, th), Image.NEAREST if (scale > 1 and f == 1.0) else Image.LANCZOS)
        S.paste(tile.convert("RGB"), (x, y + 14)); d.text((x, y), str(i), fill=(160, 170, 165))
    S.save(path); return path
