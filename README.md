# GizVFX

Effects drawn from code, in two looks from one recipe:

- **Pixel**: palette-limited sprites with dithered glow, GIF + sprite sheet + JSON (46 effects: 13 in Python, 33 JSON recipes).
- **Painted**: the same recipe drawn smooth at 4x with a real alpha channel, in eight styles: `ink`, `watercolor`, `comic`, `chalk`, `linocut`, `stencil`, `glitch`, `lineart`.

No reference image, no AI call, no network. See `ABOUT.md` for what it does in plain words. Describe a new effect in words, an agent turns it into a small JSON recipe of layers, you look at the contact sheet and adjust (see `HANDOUT.md`).

```bash
python gizvfx.py list                                   # the effects
python gizvfx.py render fire/torch -o palette=ice --out fx
python gizvfx.py painted melee/ink-slash --style watercolor --out fx
python gizvfx.py schema                                 # the recipe language
python gizvfx.py check                                  # deterministic, loops close, one-shots end empty
python gizvfx.py fix my_effect.json --out fx            # check + repair + write the files, list what is left
python gizvfx.py selftest
```

Needs Python 3.10+, numpy, Pillow (scipy for the painted `poly` layer). Your own recipes live next to your files or in `~/.gizvfx/recipes` (`import`). Code AGPL-3.0-or-later, docs CC BY 4.0. Split out of Gizpix; the painting-style ideas come from reading cloveric/claude-drawing (MIT), no code copied.
