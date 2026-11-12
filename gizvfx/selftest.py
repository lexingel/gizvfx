# SPDX-License-Identifier: AGPL-3.0-or-later
"""gizvfx selftest: every effect is deterministic, loops close, one-shots end empty, nothing is cropped; palette and option handling; sheet, JSON and GIF export.
python -m gizvfx selftest   (no golden hashes: float maths can differ by a pixel between platforms, so the checks are about properties, not bytes)"""
import json, os, tempfile
import numpy as np
from PIL import Image, ImageSequence
from . import engine
from .export import write_all
from .ramps import resolve


def run():
    reg = engine.registry(); assert len(reg) >= 12, len(reg)
    for eid in sorted(reg):
        bad = engine.check(eid); assert not bad, (eid, bad)
        m, meta = reg[eid]; assert {"id", "name", "loop", "duration", "size", "about"} <= set(meta), eid
    fr = engine.render("fire/torch", {"palette": "ice"}); fr2 = engine.render("fire/torch", {"palette": "ice"})
    assert all(np.array_equal(np.array(a), np.array(b)) for a, b in zip(fr, fr2)), "same options must give the same frames"
    other = engine.render("fire/torch", {"seed": 9}); assert any(not np.array_equal(np.array(a), np.array(b)) for a, b in zip(fr, other)), "seed must change something"
    assert engine.render("impacts/hit-spark", {"flip": True})[1].size == (72, 72)
    for bad_opt in ({"nope": 1},):
        try: engine.options(engine.get("fire/torch")[1], bad_opt); raise SystemExit("an unknown option must be an error")
        except KeyError: pass
    try: resolve("not-a-palette"); raise SystemExit("an unknown palette must be an error")
    except ValueError: pass
    assert resolve("#102,#215,#43a")[1] == (34, 17, 85)
    for eid in ("fire/torch", "explosions/small-explosion"):
        m, meta = engine.get(eid); frames = engine.render(eid, frames=6)
        with tempfile.TemporaryDirectory() as d:
            paths = write_all(frames, d, "x", meta, {}, 12, scale=2)
            assert len(paths) == 4 and all(os.path.getsize(p) > 0 for p in paths), paths
            js = json.load(open(os.path.join(d, "x_sheet.json"), encoding="utf-8")); assert js["meta"]["gizvfx"]["frames"] == 6 and js["meta"]["gizvfx"]["loop"] == meta["loop"]
            with Image.open(os.path.join(d, "x.gif")) as g: n = sum(1 for _ in ImageSequence.Iterator(g))
            assert n >= 6, n
    from . import spec                                                               # recipes: a described effect renders, and mistakes are named
    mod, meta = spec.load({"name": "t", "size": [48, 48], "options": {"r": 10}, "layers": [{"type": "ring", "radius": "$r", "thick": [3, 0]}, {"type": "glow", "radius": 12, "strength": [0.6, 0]}]})
    assert len(engine.render_frame(mod, meta, engine.options(meta), 0.2).a.nonzero()[0]) > 0
    for bad_spec, word in (({"layers": [{"type": "particle"}]}, "particles"), ({"layers": [{"type": "glow", "raduis": 3}]}, "radius"), ({"layers": [{"type": "glow", "radius": "$nope"}]}, "option")):
        try:
            m2, me2 = spec.load({"size": [32, 32], **bad_spec}); engine.render_frame(m2, me2, engine.options(me2), 0.5); raise SystemExit(f"recipe mistake not caught: {bad_spec}")
        except (ValueError, KeyError) as e: assert word in str(e), (word, str(e))
    mod, meta = spec.load({"name": "t", "size": [64, 64], "layers": [{"type": "poly", "shape": "crystal", "scale": [0, 1, 0]}, {"type": "include", "recipe": "environment/smoke-puff", "t": [0, 0.8]}]})
    assert engine.render_frame(mod, meta, engine.options(meta), 0.4).a.any() and not engine.check("environment/smoke-puff")
    for bad_spec, word in (({"layers": [{"type": "particles", "count": 9999}]}, "limit"), ({"size": [999, 20], "layers": [{"type": "glow"}]}, "size"), ({"layers": [{"type": "include", "recipe": "fire/torch"}]}, "Python"), ({"layers": [{"type": "stamp", "image": "../x.png"}]}, "recipe file")):
        try:
            m2, me2 = spec.load({"size": [32, 32], **bad_spec}); engine.render_frame(m2, me2, engine.options(me2), 0.5); raise SystemExit(f"limit not enforced: {bad_spec}")
        except (ValueError, KeyError) as e: assert word in str(e), (word, str(e))
    for eid in ("melee/ink-slash", "impacts/ink-burst", "impacts/pop-burst", "impacts/paint-splat", "melee/speed-dash"):                                    # painted version: renders, deterministic, one-shot ends empty
        from . import painted
        assert not painted.check(eid), (eid, painted.check(eid)); assert painted.render(eid, frames=3, scale=2)[1].size == (engine.get(eid)[1]["size"][0] * 2, engine.get(eid)[1]["size"][1] * 2)
    for eid in ("fire/fire-wall", "magic/energy-orb", "magic/teleport", "weather/tornado", "lightning/strike", "magic/crystal-eruption"):                                                         # a recipe of layers with no native painted version still renders (smooth upscale)
        fr = painted.render(eid, frames=3, scale=2, style="comic"); assert fr[1].getchannel("A").getbbox(), eid
    for st in painted.STYLES: assert painted.render("melee/claw-scratch", frames=3, scale=2, style=st)[1].getchannel("A").getbbox(), st
    try: painted.render("fire/torch"); raise SystemExit("a Python effect has no painted version")
    except ValueError: pass
    with tempfile.TemporaryDirectory() as d:                                                       # fix: a cropped one-shot comes out clean
        rp = os.path.join(d, "crop.json"); json.dump({"id": "test/crop", "loop": False, "duration": 1.0, "size": [30, 30], "layers": [{"type": "star", "size": [0, 30], "arms": 8, "at": [0, 0]}, {"type": "glow", "radius": [10, 30]}]}, open(rp, "w"))
        from .fix import fix
        done, problems, notes, _ = fix(rp, out=os.path.join(d, "o"), scale=1)
        assert done and not problems, (done, problems)
    from . import spec                                                                           # option arithmetic and a bolt colour rim next to the generic rim
    o = {"w": 10, "s": "x"}
    assert [spec.sub(t, o) for t in ("$w", "-$w", "$w*0.5", "$w+4", "$w-6", "$w/4")] == [10, -10, 5.0, 14.0, 4.0, 2.5]
    for bad_ in ("$s+1", "$w + 4", "$q"):
        try: spec.sub(bad_, o); raise AssertionError(bad_)
        except (ValueError, KeyError): pass
    with tempfile.TemporaryDirectory() as d:
        rp = os.path.join(d, "b.json"); json.dump({"id": "test/b", "duration": 0.5, "size": [60, 60], "layers": [{"type": "bolt", "from": [0, -20], "to": [0, 20], "rim": "#223355"}, {"type": "disc", "radius": 5, "rim": [-1, -1]}]}, open(rp, "w"))
        assert len(engine.render(rp)) > 1
        sp = os.path.join(d, "big.json"); json.dump({"id": "test/big", "duration": 0.5, "size": [250, 250], "pivot": [5, 5], "layers": [{"type": "ring", "radius": [0, 80], "thick": [3, 0]}]}, open(sp, "w"))
        from .fix import fix
        _, problems, _, _ = fix(sp, out=os.path.join(d, "o"), scale=1); assert any("256" in x for x in problems), problems       # the canvas limit is reported, not crashed on
    with tempfile.TemporaryDirectory() as d:                                                       # drop: a trail stays behind a moving layer
        tp = os.path.join(d, "t.json"); json.dump({"id": "test/t", "duration": 1.0, "size": [120, 40], "pivot": [10, 20], "layers": [{"type": "particles", "mode": "stream", "count": 30, "at": [[0, 0], [90, 0]], "drop": True, "life": [0.3, 0.4], "speed": [0, 1], "size": [3, 2], "t": [0, 0.9]}]}, open(tp, "w"))
        fr = engine.render(tp, {"colors": 0}); xs = [np.nonzero(np.array(fr[6])[..., 3])[1]]
        assert xs[0].size and xs[0].max() - xs[0].min() > 20, "particles should be spread along the path the layer flew"
    with tempfile.TemporaryDirectory() as d:                                                       # an animated squash, options inside paths, an unused option is flagged
        qp = os.path.join(d, "q.json"); json.dump({"id": "test/q", "duration": 0.5, "size": [60, 60], "options": {"h": 20, "foam": 1}, "layers": [{"type": "ring", "radius": 14, "thick": 5, "squash": [1, 0.15, 1], "at": [[0, 0], [0, "-$h"], [0, 0]]}]}, open(qp, "w"))
        assert len(engine.render(qp)) > 1 and any("'foam' is never used" in x for x in engine.report(qp)[1])
    from .spec import wave_geometry                                                              # the wave layer: a body and a crest, a curl makes the outline longer, dir mirrors it
    b0, c0, _ = wave_geometry({"height": 30, "curl": 0}, 0.5); b1, c1, _ = wave_geometry({"height": 30, "curl": 1}, 0.5); bm, _, _ = wave_geometry({"height": 30, "curl": 1, "dir": -1}, 0.5)
    assert b0 and c0 and len(b1) > len(b0) and not wave_geometry({"height": 0}, 0.5)[0] and sorted(x for x, _ in bm) == sorted(-x for x, _ in b1)
    from .spec import wave_anchor, water_geometry, sub as _sub                                   # surface points, the sea, chained option arithmetic
    d_ = {"height": 30, "curl": 1}; cx_, cy_, _a = wave_anchor(d_, 0.5, "crest"); lx_, ly_, _a = wave_anchor(d_, 0.5, "lip"); sx_, sy_, sa_ = wave_anchor(d_, 0.5, "slope", 0.5)
    assert (cx_, cy_) == (0.0, -30.0) and lx_ > 5 and -90 <= sa_ <= 0 and abs(wave_anchor({**d_, "dir": -1}, 0.5, "lip")[0] + lx_) < 1e-9 and abs(wave_anchor({**d_, "dir": -1}, 0.5, "slope", 0.5)[2] + sa_) < 1e-6
    assert water_geometry({"width": 60, "depth": 8}, 0.5, 0.3)[0] and not water_geometry({"width": 60, "depth": 0}, 0.5, 0.3)[0] and _sub("$w*2+4", {"w": 10}) == 24
    with tempfile.TemporaryDirectory() as d:                                                       # a layer sits on a wave and turns with it
        wp = os.path.join(d, "w.json"); json.dump({"id": "test/w", "duration": 0.6, "size": [120, 80], "pivot": [60, 60], "layers": [{"id": "w", "type": "wave", "height": 30, "curl": 0.5}, {"type": "poly", "shape": "arrow", "at": {"on": "w", "point": "slope", "u": 0.6, "tilt": True}, "scale": 0.5}]}, open(wp, "w"))
        assert len(engine.render(wp, {"colors": 0})) > 1
        json.dump({"id": "test/w2", "duration": 0.6, "size": [120, 80], "layers": [{"type": "poly", "at": {"on": "nope"}}]}, open(os.path.join(d, "w2.json"), "w"))
        try: engine.render(os.path.join(d, "w2.json")); raise AssertionError("an unknown id should be an error")
        except ValueError: pass
    from .spec import water_anchor                                                               # a float on the sea tilts with the ripples; anchors move, bolt ends and palette roles take them
    x0_, y0_, a0_ = water_anchor({"width": 80, "ripple": 2, "wavelength": 12}, 0.5, 0.0, 5.0); assert abs(y0_) <= 2 and -90 < a0_ < 90 and water_anchor({"width": 80}, 0.5, 0.0, 500.0)[0] == 40.0
    with tempfile.TemporaryDirectory() as d:
        rp = os.path.join(d, "r.json"); json.dump({"id": "test/r", "duration": 0.8, "size": [120, 80], "pivot": [60, 60], "options": {"c": "fire"}, "palettes": {"rope": "$c"}, "layers": [
            {"id": "w", "type": "wave", "height": 30, "curl": 0.5}, {"id": "s", "type": "water", "width": 100},
            {"type": "poly", "shape": "arrow", "at": {"on": "w", "point": "slope", "u": [0.9, 0.3], "tilt": True}, "scale": 0.4},
            {"type": "bolt", "from": {"on": "w", "point": "crest"}, "to": {"on": "w", "point": "slope", "u": [0.9, 0.3]}, "palette": "@rope"},
            {"type": "poly", "shape": "diamond", "at": {"on": "s", "x": 20, "tilt": True}, "scale": 0.4}]}, open(rp, "w"))
        fa = engine.render(rp, {"colors": 0}); assert len(fa) > 1 and np.array(fa[3])[..., 3].any()
        from . import painted
        assert len(painted.render(rp, {}, scale=2)) > 1                                         # the painted renderer resolves the same anchors
    with tempfile.TemporaryDirectory() as d:                                                       # fix --apply replaces the recipe and keeps a backup
        ap_ = os.path.join(d, "a.json"); json.dump({"id": "test/a", "duration": 0.8, "size": [40, 40], "layers": [{"type": "ring", "radius": [0, 40], "thick": [3, 0]}]}, open(ap_, "w"))
        from .fix import fix as _fix
        _, pr_, _, _ = _fix(ap_, out=os.path.join(d, "o"), scale=1, apply=True)
        assert not pr_ and os.path.exists(ap_ + ".bak") and json.load(open(ap_))["size"][0] > 40 and json.load(open(ap_ + ".bak"))["size"] == [40, 40]
    with tempfile.TemporaryDirectory() as d:                                                       # what the handout says about a thick ring and a poly
        cp_ = os.path.join(d, "c.json")
        def _cell(layer):
            json.dump({"id": "test/c", "duration": 0.5, "size": [80, 80], "pivot": [40, 40], "layers": [layer]}, open(cp_, "w")); return np.array(engine.render(cp_, {"colors": 0})[2])
        assert _cell({"type": "ring", "radius": 10, "thick": 20})[40, 40, 3] > 0 and _cell({"type": "ring", "radius": 10, "thick": 6})[40, 40, 3] == 0
        pc_ = _cell({"type": "poly", "shape": "crystal", "scale": 2}); assert len({tuple(c) for c in pc_[pc_[..., 3] > 0][:, :3]}) > 1
        pc_ = _cell({"type": "poly", "shape": "crystal", "scale": 2, "color": "#ff0000"}); assert len({tuple(c) for c in pc_[pc_[..., 3] > 0][:, :3]}) == 1
    with tempfile.TemporaryDirectory() as d:                                                       # check names the layer that keeps drawing at the end of a one-shot
        lp_ = os.path.join(d, "l.json"); json.dump({"id": "test/l", "duration": 0.8, "size": [60, 60], "layers": [{"type": "ring", "radius": [0, 15], "thick": [3, 0]}, {"type": "glow", "radius": 10}]}, open(lp_, "w"))
        assert any("layers still drawing at t=1: 1 glow" in b for b in engine.check(lp_))
    with tempfile.TemporaryDirectory() as d:                                                       # flash flares a layer white at a hit; clip keeps a layer inside another layer's pixels
        fp_ = os.path.join(d, "f.json"); json.dump({"id": "test/f", "duration": 1.0, "size": [80, 80], "pivot": [40, 60], "palette": "ice", "layers": [
            {"id": "col", "type": "beam", "from": [0, 0], "to": [0, -40], "width": 10},
            {"type": "poly", "shape": "diamond", "scale": 4, "at": [0, -20], "color": "#202040", "clip": "col"},
            {"type": "ring", "radius": 20, "thick": 3, "at": [0, -20], "color": "#2040a0", "flash": [0.0]}]}, open(fp_, "w"))
        fr_ = engine.render(fp_, {"colors": 0}); f0_ = np.array(fr_[0]); cols_ = f0_[f0_[..., 3] > 0][:, :3]
        assert (cols_.min(1) > 200).any() and not (np.array(fr_[-2])[..., :3][np.array(fr_[-2])[..., 3] > 0].min(1) > 200).all()    # white at the hit
        bad_ = dict(json.load(open(fp_)), layers=[{"type": "ring", "radius": 5, "clip": "nope"}]); json.dump(bad_, open(fp_, "w"))
        try: engine.render(fp_, {"colors": 0}); raise SystemExit("clip to a missing id must fail")
        except (KeyError, ValueError) as ex_: assert "no layer has" in str(ex_)
    with tempfile.TemporaryDirectory() as d:                                                       # include: a .json next to the recipe, `repeat` plays a loop several times in a window
        json.dump({"id": "test/idle", "loop": True, "duration": 1, "size": [60, 60], "layers": [{"type": "orbit", "count": 1, "radius": 15, "size": 3, "turns": 1}]}, open(os.path.join(d, "idle.json"), "w"))
        json.dump({"id": "test/rel", "duration": 2, "size": [60, 60], "layers": [{"type": "include", "recipe": "idle.json", "repeat": 2, "t": [0, 0.5]}]}, open(os.path.join(d, "rel.json"), "w"))
        fr_ = engine.render(os.path.join(d, "rel.json"), {"colors": 0}); n_ = len(fr_); assert n_ > 8 and np.array(fr_[0])[..., 3].any() and not np.array(fr_[-1])[..., 3].any()
        i1_, i2_ = int(0.25 * (n_ - 1)), int(0.5 * (n_ - 1)); assert np.array_equal(np.array(fr_[0]), np.array(fr_[min(i2_, n_ - 1)])) or np.array(fr_[i1_])[..., 3].any()   # it plays and loops inside the window
    with tempfile.TemporaryDirectory() as d:                                                       # erode on an include layer works in the pixel and the painted renderer; check names the layers at the edge
        json.dump({"id": "test/i2", "loop": True, "duration": 1, "size": [60, 60], "layers": [{"type": "ring", "radius": 15, "thick": 4}]}, open(os.path.join(d, "i.json"), "w"))
        json.dump({"id": "test/r2", "duration": 2, "size": [60, 60], "layers": [{"type": "include", "recipe": "i.json", "t": [0, 1], "erode": [0, 4]}]}, open(os.path.join(d, "r.json"), "w"))
        from . import painted as _pt
        pf_ = _pt.render(os.path.join(d, "r.json"), {}, scale=2); assert int((np.array(pf_[0])[..., 3] > 40).sum()) > 2 * int((np.array(pf_[-2])[..., 3] > 40).sum())
        json.dump({"id": "test/e", "duration": 1, "size": [40, 40], "pivot": [20, 30], "layers": [{"type": "ring", "radius": 8, "thick": 2}, {"type": "beam", "from": [0, 0], "to": [0, -40], "width": 4}]}, open(os.path.join(d, "e.json"), "w"))
        assert any("layers touching the edge: 1 beam" in b for b in engine.check(os.path.join(d, "e.json")))
    print(f"gizvfx selftest ok ({len(reg)} effects)"); return 0
