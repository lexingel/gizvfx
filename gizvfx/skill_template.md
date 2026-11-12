---
name: gizvfx
description: GizVFX - make game effects (fire, explosions, hits, lightning, ice, heal, portals, slashes, splats, bursts, waves, shields...) from a text description, as pixel sprites (GIF + sprite sheet + JSON) or painted smooth in 8 styles (ink, watercolor, comic, chalk, linocut, stencil, glitch, lineart). Ships JSON recipes and a layer language, no AI image generation. Use when the user asks for an effect/VFX or a new look for one. `/gizvfx update` updates the tool to the latest version from GitHub.
---
{{MARK}}

# GizVFX

The tool is installed at `{{DIR}}`.

## `/gizvfx update`

When the user says `/gizvfx update`, "update gizvfx" or similar, run:

```bash
python {{DIR}}/gizvfx.py update
```

Tell the user the result in a few lines: the old and new version, what the changelog lists as new, and whether the selftest passed. Notes:
- `python {{DIR}}/gizvfx.py update --check` only looks whether a newer version exists and changes nothing.
- If it refuses because the folder has local changes (exit code 3), show the files it listed and ask before running `update --force` (that discards changes to tracked files).
- It needs the network once (GitHub) and nothing else; saved recipes and the `gizvfx_ui` folder are never touched.
- After an update that lists new layer keys or commands, read `{{DIR}}/HANDOUT.md` again before writing recipes.

## Using it

```bash
python {{DIR}}/gizvfx.py list [WORD]
python {{DIR}}/gizvfx.py ui                    # local web page: the user edits and watches effects live (start it for them, or tell them to run it)
python {{DIR}}/gizvfx.py render ID|my.json -o palette=ice --out fx      # pixel; open fx/NAME_contact.png
python {{DIR}}/gizvfx.py painted ID|my.json --style watercolor --out fx # hi-res, transparent
python {{DIR}}/gizvfx.py recipe ID > my.json   # copy, edit; schema [LAYER] lists the keys
python {{DIR}}/gizvfx.py check my.json --report
python {{DIR}}/gizvfx.py fix my.json|ID|--all --out fx   # check + repair + write files + NAME_fix.txt, lists what is left (run it last)
```

For a description the library lacks: write a JSON recipe (do not hand-code Python). Read `{{DIR}}/HANDOUT.md` (the words-to-layers table and the recipe rules) before the first recipe, and always LOOK at the contact sheet.
