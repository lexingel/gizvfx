# SPDX-License-Identifier: AGPL-3.0-or-later
"""`gizvfx update`: bring this install up to the latest version on GitHub, and `gizvfx install-skill`: give an AI agent (Claude Code) the `/gizvfx` skill.

Only these commands touch the network, and only on request. A git clone is updated with `git pull --ff-only`; a copy without .git (a downloaded zip) is replaced from the repository's zip.
Your own files stay: saved recipes (`~/.gizvfx/recipes`), the `gizvfx_ui` folder, anything you made next to the tool that is not part of it.
"""
import io, json, os, shutil, subprocess, sys, tempfile, urllib.request, zipfile

REPO = "lexingel/gizvfx"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = "<!-- installed by gizvfx install-skill -->"
KEEP = {".git", "gizvfx_ui", "__pycache__", ".gizvfx_version"}
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skill_template.md")


def _git(*a, root=None):
    try: r = subprocess.run(["git", "-C", root or ROOT, *a], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError): return None
    return r


def is_git(root=None):
    r = _git("rev-parse", "--is-inside-work-tree", root=root)
    return bool(r and r.returncode == 0 and r.stdout.strip() == "true") and os.path.isdir(os.path.join(root or ROOT, ".git"))


def local_sha(root=None):
    root = root or ROOT
    if is_git(root): return _git("rev-parse", "HEAD", root=root).stdout.strip()
    p = os.path.join(root, ".gizvfx_version")
    return open(p).read().strip() if os.path.exists(p) else ""


def remote_sha():
    r = _git("ls-remote", f"https://github.com/{REPO}.git", "refs/heads/main")
    if r and r.returncode == 0 and r.stdout.split(): return r.stdout.split()[0]
    with urllib.request.urlopen(urllib.request.Request(f"https://api.github.com/repos/{REPO}/commits/main", headers={"User-Agent": "gizvfx-update"}), timeout=30) as f:
        return json.load(f)["sha"]


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh: return fh.read()
    except OSError: return ""


def new_changelog(old_text, new_text, limit=14):
    """the CHANGELOG lines that are new, as bullet points"""
    old = set(old_text.splitlines())
    return [l for l in new_text.splitlines() if l.strip() and l not in old][:limit]


def apply_zip(zip_path, root):
    """replace the tool's files in `root` with those of a repository zip; returns the list of files written. Files that are not part of the new version and live inside the package folder are removed."""
    with zipfile.ZipFile(zip_path) as z:
        top = {n.split("/")[0] for n in z.namelist() if n.strip("/")}
        if len(top) != 1: raise ValueError("unexpected zip layout")
        tmp = tempfile.mkdtemp(prefix="gizvfx_new_")
        try:
            z.extractall(tmp); src = os.path.join(tmp, top.pop())
            if not os.path.isfile(os.path.join(src, "gizvfx.py")): raise ValueError("the downloaded zip is not GizVFX")
            written = []
            for dp, dn, fn in os.walk(src):
                dn[:] = [d for d in dn if d not in KEEP]
                for f in fn:
                    s = os.path.join(dp, f); rel = os.path.relpath(s, src); d = os.path.join(root, rel); os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copyfile(s, d); written.append(rel)
            pkg_new = {r.replace("\\", "/") for r in written if r.replace("\\", "/").startswith("gizvfx/")}
            for dp, dn, fn in os.walk(os.path.join(root, "gizvfx")):
                dn[:] = [d for d in dn if d not in KEEP]
                for f in fn:
                    rel = os.path.relpath(os.path.join(dp, f), root).replace("\\", "/")
                    if rel not in pkg_new: os.remove(os.path.join(root, rel))
            return written
        finally: shutil.rmtree(tmp, ignore_errors=True)


def render_skill(root=None):
    return _read(TEMPLATE).replace("{{DIR}}", (root or ROOT).replace("\\", "/")).replace("{{MARK}}", MARK)


def skill_path(base=None):
    return os.path.join(base or os.path.join(os.path.expanduser("~"), ".claude", "skills"), "gizvfx", "SKILL.md")


def install_skill(base=None, quiet=False):
    p = skill_path(base); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh: fh.write(render_skill())
    if not quiet: print(f"skill written: {p}  (use /gizvfx in Claude Code; /gizvfx update keeps the tool current)")
    return p


def refresh_skill_if_installed(base=None):
    p = skill_path(base)
    if ROOT.replace("\\", "/") in _read(p): install_skill(base, quiet=True); return p                  # only the skill that points at THIS install (another install keeps its own)
    return None


def update(check=False, force=False, say=print):
    """returns an exit code: 0 ok / up to date, 1 failed, 3 refused (local changes)"""
    old = local_sha()
    try: new = remote_sha()
    except Exception as e: say(f"gizvfx update: cannot reach GitHub ({type(e).__name__}: {e}). Nothing changed."); return 1
    short = lambda s: s[:7] if s else "unknown"
    if old == new: say(f"GizVFX is up to date ({short(new)})."); return 0
    if check: say(f"update available: {short(old)} -> {short(new)}. Run `python gizvfx.py update` (or /gizvfx update)."); return 0
    old_cl = _read(os.path.join(ROOT, "CHANGELOG.md")); old_req = _read(os.path.join(ROOT, "requirements.txt"))
    if is_git():
        st = _git("status", "--porcelain", "--untracked-files=no").stdout.strip()
        if st and not force:
            say("gizvfx update: this folder has local changes, so it was not touched:\n" + "\n".join("  " + l for l in st.splitlines()[:15]) + "\nCommit or stash them, or run `update --force` (it discards changes to tracked files)."); return 3
        if st: _git("checkout", "--", ".")
        r = _git("pull", "--ff-only", "https://github.com/%s.git" % REPO, "main")
        if not r or r.returncode != 0:
            say("gizvfx update: git pull failed:\n" + (r.stderr.strip() if r else "git not available") + "\nIf the history differs, clone again or run `git fetch && git reset --hard origin/main` yourself."); return 1
    else:
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False); tmp.close()
            req = urllib.request.Request(f"https://github.com/{REPO}/archive/refs/heads/main.zip", headers={"User-Agent": "gizvfx-update"})
            with urllib.request.urlopen(req, timeout=60) as f, open(tmp.name, "wb") as out: shutil.copyfileobj(f, out)
            n = len(apply_zip(tmp.name, ROOT)); os.remove(tmp.name)
        except Exception as e: say(f"gizvfx update: download or unpack failed ({type(e).__name__}: {e}). The old files may be partly replaced: run the update again."); return 1
        with open(os.path.join(ROOT, ".gizvfx_version"), "w") as fh: fh.write(new)
    say(f"updated {short(old)} -> {short(new)}")
    news = new_changelog(old_cl, _read(os.path.join(ROOT, "CHANGELOG.md")))
    if news: say("what is new (CHANGELOG):\n" + "\n".join("  " + l[:240] for l in news))
    if _read(os.path.join(ROOT, "requirements.txt")) != old_req:
        say("requirements.txt changed: installing")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", os.path.join(ROOT, "requirements.txt")]); say("  pip ok" if r.returncode == 0 else "  pip failed: run `pip install -r requirements.txt` yourself")
    sk = refresh_skill_if_installed()
    if sk: say(f"skill refreshed: {sk}")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "gizvfx.py"), "selftest"], capture_output=True, text=True)
    say("selftest: " + (r.stdout.strip().splitlines() or ["no output"])[-1] if r.returncode == 0 else "selftest FAILED after the update:\n" + (r.stdout + r.stderr)[-600:])
    say("Read HANDOUT.md again if the changelog above mentions new layer keys or commands."); return 0 if r.returncode == 0 else 1
