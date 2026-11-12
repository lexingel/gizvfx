# SPDX-License-Identifier: AGPL-3.0-or-later
"""`gizvfx ui`: a local web page to build and watch effects (nothing leaves your machine, only 127.0.0.1 is served).

The page edits a recipe (layers, options, top-level fields), shows it live as a pixel sprite or painted in any style, runs `check` and `fix`, saves the recipe and exports GIF + sprite sheet.
Standard library only (http.server); the page is gizvfx/ui_page.html.
"""
import base64, io, json, os, shutil, tempfile, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from . import engine, spec
from .ramps import RAMPS

LOCK = threading.Lock()                                       # the renderers keep a little global state: one render at a time
PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_page.html")
STYLES = ["ink", "watercolor", "comic", "chalk", "linocut", "stencil", "glitch", "lineart"]
NEW = {"id": "my/effect", "name": "My effect", "about": "", "loop": False, "duration": 1.0, "fps": 12, "size": [96, 96], "pivot": [48, 64], "palette": "fire",
       "layers": [{"type": "glow", "radius": [8, 30, 6], "strength": [0.9, 0.6, 0]}, {"type": "ring", "radius": [2, 30], "thick": [5, 0]}]}


def _png(im):
    b = io.BytesIO(); im.save(b, "PNG"); return base64.b64encode(b.getvalue()).decode()


class Work:
    """the folder the page writes to: the live recipe (so `include` and `stamp` paths next to it work), saved recipes and exports"""
    def __init__(self, root):
        self.root = os.path.abspath(root); os.makedirs(self.root, exist_ok=True); self.live = os.path.join(self.root, "_live.json")

    def target(self, body):
        """-> what `engine.get` takes: an effect id, or the live recipe file just written from the page"""
        if body.get("recipe") is not None:
            with open(self.live, "w", encoding="utf-8") as fh: json.dump(body["recipe"], fh)
            return self.live
        return body["id"]


def _given(body, meta):
    g = {k: v for k, v in (body.get("options") or {}).items() if v is not None and v != ""}
    ok = set(engine.options(meta))
    return {k: v for k, v in g.items() if k in ok}


def api_list():
    out = []
    for eid, (m, meta) in sorted(engine.registry().items()):
        out.append({"id": eid, "name": meta["name"], "about": meta.get("about", ""), "loop": bool(meta["loop"]), "duration": meta["duration"], "size": list(meta["size"]), "recipe": "recipe" in meta, "tags": list(meta.get("tags", []))})
    return {"effects": out}


def api_meta():
    return {"palettes": sorted(RAMPS), "styles": STYLES, "new": NEW, "common": spec.COMMON, "schema": spec.SCHEMA, "layers": list(spec.LAYERS), "style_keys": spec.STYLE_KEYS}


def api_recipe(eid):
    m, meta = engine.get(eid)
    if "recipe" not in meta: return {"code": True, "name": meta["name"], "about": meta.get("about", "")}
    r = {k: v for k, v in meta["recipe"].items() if not k.startswith("_")}
    return {"recipe": r}


def api_render(work, body):
    from . import painted
    eid = work.target(body); mode = body.get("mode", "pixel"); scale = int(body.get("scale", 3)); style = body.get("style", "ink")
    mod, meta = engine.get(eid); given = _given(body, meta); o = engine.options(meta, given); fps = int(body.get("fps") or meta.get("fps", 12))
    if mode == "painted":
        frames = painted.render(eid, given, fps=fps, scale=scale, style=style, opts={"intensity": float(body.get("intensity", 1.0)), "hold": 2}); sc = 1
    else:
        frames = engine.render(eid, given, fps=fps); sc = 1
    opts = dict(o); pal = meta.get("recipe", {}).get("palette") if opts.get("palette") is None else opts["palette"]
    return {"frames": [_png(f) for f in frames], "fps": fps, "loop": bool(meta["loop"]), "w": frames[0].width, "h": frames[0].height, "base": list(meta["size"]), "scale": sc,
            "name": meta["name"], "options": opts, "recipe_options": dict(meta.get("options", {})), "palette": pal if isinstance(pal, str) else None, "is_recipe": "recipe" in meta}


def api_check(work, body):
    from . import painted
    eid = work.target(body); mode = body.get("mode", "pixel"); mod, meta = engine.get(eid); given = _given(body, meta)
    problems = engine.check(eid, given)
    if mode == "painted" and "recipe" in meta:
        problems += ["painted: " + b for b in painted.check(eid, 2, body.get("style", "ink"))]
    flags = engine.report(eid, given)[1]
    return {"problems": problems, "flags": flags}


def api_fix(work, body):
    from .fix import fix
    eid = work.target(body); out = tempfile.mkdtemp(prefix="gizvfx_fix_")
    try:
        done, problems, notes, paths = fix(eid, given=_given(body, engine.get(eid)[1]), out=out, name="fixed", scale=2)
        res = {"done": [x for x in done if not x.startswith("your recipe is unchanged")], "problems": problems, "notes": notes}
        fixed = next((p for p in paths if p.endswith(".fixed.json")), None)
        if fixed:
            with open(fixed, encoding="utf-8") as fh: res["fixed_recipe"] = json.load(fh)
        return res
    finally: shutil.rmtree(out, ignore_errors=True)


def api_save(work, body):
    name = "".join(c for c in str(body.get("name", "effect")) if c.isalnum() or c in "-_") or "effect"
    path = os.path.join(work.root, name + ".json")
    with open(path, "w", encoding="utf-8") as fh: json.dump(body["recipe"], fh, indent=1)
    return {"path": path}


def api_export(work, body):
    from .export import write_all
    from . import painted
    eid = work.target(body); mode = body.get("mode", "pixel"); style = body.get("style", "ink"); mod, meta = engine.get(eid); given = _given(body, meta); o = engine.options(meta, given); fps = meta.get("fps", 12)
    name = str(body.get("name") or meta["id"].split("/")[-1]) + ("" if mode == "pixel" else "_" + style)
    out = tempfile.mkdtemp(prefix="gizvfx_exp_")
    try:
        if mode == "painted":
            frames = painted.render(eid, given, fps=fps, scale=4, style=style); m2 = dict(meta); m2["pivot"] = tuple(v * 4 for v in meta["pivot"]); paths = write_all(frames, out, name, m2, dict(o), fps, scale=1, contact=False, bg=None)
        else:
            frames = engine.render(eid, given, fps=fps); paths = write_all(frames, out, name, meta, dict(o), fps, scale=4, contact=False)
        files = {}
        for p in paths:
            with open(p, "rb") as fh: files[os.path.basename(p)] = base64.b64encode(fh.read()).decode()
        keep = os.path.join(work.root, "export"); os.makedirs(keep, exist_ok=True)
        for p in paths: shutil.copy(p, keep)
        return {"files": files, "folder": keep}
    finally: shutil.rmtree(out, ignore_errors=True)


POST = {"/api/render": api_render, "/api/check": api_check, "/api/fix": api_fix, "/api/save": api_save, "/api/export": api_export}


def make_handler(work, port):
    allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def _send(self, code, data, ctype="application/json"):
            raw = data if isinstance(data, bytes) else json.dumps(data).encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype != "application/octet-stream" else "")); self.send_header("Content-Length", str(len(raw))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(raw)

        def _guard(self):
            if self.headers.get("Host", "") not in allowed: self._send(403, {"error": "forbidden host"}); return False       # no DNS-rebinding: only the page served from this very address
            return True

        def do_GET(self):
            if not self._guard(): return
            u = urlparse(self.path); q = parse_qs(u.query)
            try:
                if u.path == "/":
                    with open(PAGE, "rb") as fh: return self._send(200, fh.read(), "text/html")
                if u.path == "/api/list": return self._send(200, api_list())
                if u.path == "/api/meta": return self._send(200, api_meta())
                if u.path == "/api/recipe":
                    with LOCK: return self._send(200, api_recipe(q["id"][0]))
                self._send(404, {"error": "not found"})
            except (KeyError, ValueError) as e: self._send(200, {"error": str(e.args[0] if e.args else e)})

        def do_POST(self):
            if not self._guard(): return
            fn = POST.get(urlparse(self.path).path)
            if not fn: return self._send(404, {"error": "not found"})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
                with LOCK: self._send(200, fn(work, body))
            except (KeyError, ValueError, TypeError, IndexError, ZeroDivisionError) as e: self._send(200, {"error": str(e.args[0] if e.args else e)})
            except Exception as e: self._send(200, {"error": f"{type(e).__name__}: {e}"})
    return H


def serve(port=8765, folder="gizvfx_ui", open_browser=True):
    work = Work(folder)
    for p in range(port, port + 20):
        try: srv = ThreadingHTTPServer(("127.0.0.1", p), make_handler(work, p)); break
        except OSError: continue
    else: raise SystemExit("gizvfx: no free port between %d and %d" % (port, port + 19))
    url = f"http://127.0.0.1:{p}/"
    print(f"GizVFX UI: {url}   (saved recipes and exports go to {work.root}; Ctrl+C stops)")
    if open_browser: threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    finally: srv.server_close()
