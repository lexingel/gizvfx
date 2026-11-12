# What GizVFX does

GizVFX draws game effects from code. You give it an effect name, or a short description turned into a small JSON file, and it writes animation files you can drop into a game: a GIF, a sprite sheet with a JSON index, and a contact sheet to look at. It runs on your machine. It uses no reference image, no AI model and no network.

## Two looks from one recipe

Every effect is a list of layers (glow, ring, particles, bolt, beam and so on) with values that change over time. GizVFX can draw that same list two ways.

**Pixel.** A small sprite with a limited palette. Glow is dithered, and the whole animation shares one palette of 24 colors by default. This is what you want for a pixel-art game.

**Painted.** The same recipe drawn at four times the size with real transparency and no palette limit. Eight styles change how it looks: ink, watercolor, comic, chalk, linocut, stencil, glitch and lineart. Painted output is not pixel art. Use it for HD or non-pixel projects. The pigment is drawn on a transparent background, so it reads best on light backgrounds.

## What ships with it

There are 44 effects: 13 drawn in Python (torch, fireball, small explosion, hit spark, shockwave, lightning bolt, frost nova, heal, magic circle, coin sparkle, slash, rain, snow) and 31 JSON recipes (energy orb, poison cloud, tornado, smite, portal, teleport, shield bubble, meteor impact, ink slash, claw scratch, paint splat, pop burst, speed dash and others). The 31 recipes have a painted version in all eight styles. The 13 Python effects are pixel only.

## Making a new effect

If the effect you want is not in the list, you describe it in words and an agent writes a recipe. `HANDOUT.md` has a table that maps phrases to layers: "a shockwave on the floor" becomes a flattened `ring`, "sparks" become `particles`, "a swirling column" becomes a `funnel`, "an ink swipe" becomes a `brush`. You render it, look at the contact sheet, change some numbers and render again. Two or three rounds is normal.

A recipe is plain data. It never runs code, reads files outside its own folder or fetches anything, and a recipe has at most 40 layers on a canvas of 8 to 256 pixels. You can send the JSON file to someone and they get the same frames, because everything random comes from a seed.

## Checking and fixing

`check` tests whether an effect gives the same frames twice, whether a loop closes, whether a one-shot ends on an empty frame and whether anything touches the canvas edge. With `--report` it also measures mesh dithering, flat color, lone pixels, empty frames and jumps in motion, and names a fix for each flag.

`fix` goes one step further. It repairs what a machine can repair: a cropped canvas is enlarged, one-pixel holes are filled, lone pixels are removed, more than 40 colors are cut to 24, and a one-shot that does not end empty fades out over its last three frames. It writes the files and a `NAME_fix.txt`, then lists what you still have to fix by hand, and separately a few advisory notes (a motion jump, flat color). Only the first list makes the exit code 1. Your original recipe is never changed.

## Commands

```bash
python gizvfx.py list [WORD]                  # the effects
python gizvfx.py render fire/torch -o palette=ice --out fx
python gizvfx.py painted melee/ink-slash --style watercolor --out fx
python gizvfx.py recipe holy/smite > my.json  # copy a recipe, edit it
python gizvfx.py schema                       # every layer and key
python gizvfx.py check my.json --report
python gizvfx.py fix my.json --out fx
```

## Limits

The pixel look is clean game-sprite quality, not hand-painted detail. Fix cannot resize an effect drawn in Python code, so those can still touch the edge. It does not repair a loop that fails to close, mesh dithering, flat color or motion jumps; it points them out with the change to make. Painted output has no pixel palette and is meant for HD projects, and it reads best on light backgrounds.

## Requirements and license

Python 3.10 or newer with numpy and Pillow (scipy for one painted layer). The code is AGPL-3.0-or-later and the documentation is CC BY 4.0. The painting styles were inspired by reading cloveric/claude-drawing (MIT); no code was copied.
