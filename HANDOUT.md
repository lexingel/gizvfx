# GizVFX handout for coding agents

GizVFX draws effects from code: a pixel sprite version (palette-limited, dithered, sprite sheet + GIF) and the **same recipe** painted smooth at 4x in eight styles (ink, watercolor, comic, chalk, linocut, stencil, glitch, lineart). No reference image, no AI call, no network. Python 3 + numpy + Pillow (+ scipy for the painted `poly` layer).

## 1. The prompt-to-effect loop

The user describes an effect in words ("a frost nova for my mage", "an ink slash"). Do not refuse and do not hand-code Python:

1. `python gizvfx.py list WORD` : is there a close one already?
2. Copy the nearest recipe (`recipe ID > my.json`) or start a new one; turn the words into layers with the table in section 3.
3. `python gizvfx.py render my.json --out fx` and OPEN `fx/my_contact.png`; fix numbers; `python gizvfx.py check my.json --report`.
4. If the user wants a painted look: `python gizvfx.py painted my.json --style watercolor --out fx` (section 4).

Commands: `fix ID|FILE.json|--all` (check + repair + write, see below), `list [WORD]`, `show ID`, `palettes`, `schema [LAYER]`, `recipe ID`, `render ID|FILE.json`, `painted ID|FILE.json`, `check [ID ...] [--report]`, `import FILE.json`, `gallery out.png`, `selftest`. Run from any folder; paths resolve from `gizvfx.py`.

## 2. Shipped effects

```bash
python gizvfx.py list                       # id, loop or once, duration, size, one line each, then the palette names
python gizvfx.py show fire/torch            # its options and defaults
python gizvfx.py render fire/torch -o palette=ice -o seed=3 --out fx --scale 4
python gizvfx.py render ice/frost-nova -o radius=52 -o spikes=18 --bg none --out fx     # transparent GIF: glow edges are cut at 50% alpha
python gizvfx.py check                      # all effects; exit 1 on a failure
```

- Options: `palette` (a name from `gizvfx list`, or hex colours dark to bright: `-o palette='#102,#215,#43a'`), `seed`, `light` (glow strength), `flip` (face left), `colors` (default 24: one shared palette for the whole animation, 0 = off; the glow otherwise makes hundreds of shades), `hard` (true = glow is dithered on/off, no half-transparent pixels; use only if the engine cannot blend alpha), plus each effect's own (`show`). An unknown option or palette is a one-line error, exit 2.
- Loops (`loop`) are seamless: the last frame leads into the first. One-shots end on an empty frame; the GIF holds four blank frames before it restarts.
- Always open `NAME_contact.png` (a labelled grid of frames) and judge at the given zoom, as for any art. Glow is baked into the sheet as translucent pixels: it reads as additive over dark scenes; render with another `palette` or `light=0.3` for bright ones.
- Rain and snow are tiles that wrap on both axes (they touch the edges on purpose).
- The effects are drawn from functions of time and a seed, so the same command gives the same frames; `gizvfx check` verifies it. Python: `from gizvfx import engine; frames = engine.render("fire/torch", {"palette": "ice"})` returns RGBA PIL images.
- Quality: clean game-sprite level, not hand-painted. 13 effects drawn in Python plus the recipes in `gizvfx list`. If the user wants something that is not listed, write a recipe (section 3): that is the normal way to get a new effect.

## 3. An effect nobody drew yet: describe it in a prompt, write a recipe, look, fix

When the user asks for an effect that is not in `gizvfx list`, do not refuse and do not hand-code Python. Write a **recipe**: a small JSON file of layers. `gizvfx schema` prints every layer and key; `gizvfx recipe ID` prints a shipped one to copy.

```bash
python gizvfx.py list meteor              # 1. nearest existing effect? (searches names, tags, one-liners)
python gizvfx.py recipe explosions/meteor-impact > my.json     # 2. copy the closest recipe, or start from scratch (below)
python gizvfx.py schema particles          # the keys of one layer (no argument: all of them)
python gizvfx.py render my.json --out fx --scale 4             # 3. draw it, then OPEN fx/my_contact.png
python gizvfx.py check my.json             # 4. deterministic, loops close, one-shots end empty, nothing cropped
```

Turn the description into layers (each line is one layer type):

| The user says | Layer |
|---|---|
| a flash, a hit star, spikes | `star` (+ a small `disc`) |
| a shockwave, ripple or ring on the floor | `ring` with `squash` 0.35 to 0.45 |
| sparks, embers, debris, droplets | `particles` mode `burst`; `gravity` makes them fall; `shape: streak` for speed lines |
| rising bubbles, smoke wisps, drifting embers (a loop) | `particles` mode `stream` with whole `cycles` |
| a fireball, a smoke cloud, an explosion body, a gas cloud | `blob`; animate `scale` and `bias` (hot to cool) |
| lightning, a crack, a tether | `bolt` (`grow`, `branches`, `flicker`) |
| a laser, a jet, a spear, a column of light | `beam` (`extend`, `tip`); a flame jet is a `stream` with `angle` near 0 |
| a glow, an aura, a pulse | `glow` with `{"wave": [lo, hi, cycles]}` |
| orbiting motes, a magic circle | `orbit`, `ring` |
| light rays, a spiky burst | `rays` |
| a sword swoosh | `arc` (a circle only: no `squash`) |
| a tornado, whirlwind, pillar of swirling stripes | `funnel` (`turns` whole for loops, `lean` to sway) |
| a brush stroke, ink swipe, claw marks, a sword cut that looks painted | `brush` (`path` of 3+ points, `width`, `tail` 0.4-0.8 = how long the stroke is, `dry` 0-1 = the old end breaks into bristle streaks, `lanes`, `head` 0.05-0.95 = where it is fattest: 0.25 fat at the old end and a point at the head, like claws or blades). The head runs past the end of the path and the tail catches up, so a one-shot ends empty. One stroke per layer; stagger `t` for several |
| shading made of parallel lines (a hatched shadow under a hit) | `hatch` (`size` [rx, ry] ellipse, `angle`, `spacing`, `tone` animatable: share of lines drawn, `cross` second set of lines, `fade` + `fade_dir` thinner along a direction) |
| a comic hit burst, a spiky star, a pop frame | `burst` (`radius` animatable e.g. `[0, 26, 22, 0]`, `inner` 0.2-0.9, `points`, `rotate`, `jitter`; filled with the ramp and a dark outline) |
| speed lines, a dash, lines flying out of an impact | `speedlines` (`count`, `length`, `width`; `radial: true` + `r0` fly out from the centre, otherwise parallel lines with `angle`, `spread`, `travel`; they grow, move and shrink away) |
| a paint or slime splat with droplets and drips | `splat` (`radius`, `drops`, `reach`, `drips`, `drip_len`; bursts out, runs, then dries away) |
| comic dots, a spatter or burst of dots that shrink away | `halftone` (`size`, `cell`, `angle`, `tone` = dot size, `fade` + `fade_dir`) |
| wisps that fly from A to B, energy sucked into a portal | `particles` with `target` (and `curve` to bow them) |
| crystals, rocks, shards, spikes | `poly` (`shape: crystal | shard | rock | diamond | arrow`, or `points`; animate `scale` and `rotate`) |
| the user's own small sprite (a coin, a leaf) | `stamp` (a PNG of at most 32x32 next to the recipe file; `scale` 1 to 4) |
| an existing effect inside a new one, at another place or time | `include` (`recipe` id or .json path, `options`, `palette`; at most 2 deep; only recipes, not the Python effects) |
| a projectile on a curve, a spiral, a homing swoop | `at` with 3 or more points `[[x,y],[x,y],[x,y],...]` (a smooth curve), `spin: [radius, turns]` |
| a flame silhouette, a ground dust ring, a puddle, bubbles | `blob` `mode: flame` / `mode: ring` (`drift`, `stagger`); `particles` `shape: bubble` (pops), `shard` |
| a comet tail, a sword smear, a wisp's trail | `smear: [length, taper]` on any moving layer (a fading, shrinking trail of copies of itself) |
| a clean outline, a lit edge, a dissolve for ring/beam/particles | `outline: "auto"`, `rim: [-1, -1]`, `erode: [0, 0, 6]` on any layer |
| anything that snakes or sways along its path | `wobble: [ax, ay, whole_cycles]` on the layer |

Rules that save rounds:
- Coordinates are pixels from `pivot`, y down; `angle` 0 = right, 90 = down, -90 = up. Put the pivot where the effect is anchored (feet for ground effects, centre for orbs) and leave 8 px of canvas around everything, or `check` reports cropping.
- Windows: a layer draws only inside `t: [start, end]` (fractions of the duration). A one-shot is a few overlapping windows: flash 0 to 0.25, body 0 to 0.8, aftermath to 1. **Everything must shrink or fade to nothing by t = 1** (`thick: [3, 0]`, `size: [x, 0]`, `strength: [k, 0]`, `scale: [1, 0]`), or `check` says "does not end empty".
- When one body continues in a second layer (a blob that grows, then shrinks), give both layers the same `"seed"` or they draw different shapes.
- Loops: use only `{"wave": [lo, hi, whole_cycles]}`, particles `stream` with whole `cycles`, orbits with whole `turns`, a `poly` `rotate` of a full turn (`[0, 360]`) and `funnel` `turns`. Things that run on window progress break the seam: `arc` `sweep`, `blob` `drift` and a `rise` that does not return, `smear` on a one-way move. (`blob` `stagger` is ignored in loops for that reason.)
- `blob` bands: `depth` about 1.3 times the radius gives layered colour; a small depth gives a flat pale blob. `cover` below 0.3 looks like a mesh at 1x: prefer thin layers, a stepped `glow` or a `ring` to dithered fills.
- A value can have more than two keys: `"size": [0, 20, 0]` grows then shrinks in ONE layer (no second layer needed). `"$reach*0.5"` scales an option. `blob` takes `lit: [-1, -1]` for sphere-like shading, `bolt` takes `rim: "#hex"` (cracks on dark ground), `beam` takes `shade: flat` (no stripes), `blob` takes `erode: [0, 0, 16]` (the body is eaten from its edge: the clean way to dissolve; avoid `cover`), `glow` and `rays` take `squash` (lying on the floor), `particles` take `shape: star` (twinkles).
- Options make a recipe reusable: `"options": {"radius": 24}` and `"radius": "$radius"` inside; the user then runs `-o radius=40`. `-o palette=NAME` recolours the whole thing.
- `python gizvfx.py check my.json --report` prints numbers and FLAG lines (mesh dithering, flat colour, lone pixels, empty frames, motion pops) with the fix for each; run it after every render, then still LOOK at the contact sheet. A motion pop on a hit that lands after a flight is intended.
- Limits (every recipe): at most 40 layers, canvas 8 to 256 px, particle `count` 400, other counts 64 (blob 60). A recipe someone sends you: `python gizvfx.py import FILE.json` validates it, applies the limits, runs `check` and the report, and keeps a copy under `~/.gizvfx/recipes` (it then shows in `gizvfx list`); a recipe never runs code, reads outside its own folder, or fetches anything.
- Draw order is layer order: a `glow` after a body whitens it, so put glows first. `poly` is centred on `at` unless `anchor: base` (then its lowest point sits on `at`: use it for anything standing on the floor). `poly` and `blob` on dark palettes (stone, ice, smoke) often need `bias` around -0.2, or they come out flat pale.
- Thrown things and fountains: `particles` with `lob: true`, `angle` upward, `speed` S: each follows a parabola and lands back at its spawn height at the end of its life; the peak is about S/4 px. Aim a thrown boulder with `at` on a curve (3+ points) instead.
- `ease` can be a list, one name per key step: `"size": [0, 20, 0], "ease": ["out", "in"]`. A recipe can say `"style": {"outline": "auto", "rim": [-1, -1], "shadow": [1, 1]}` for a consistent drawn look over the whole effect, and `"palettes": {"hot": "fire", "soot": "smoke"}` with `"palette": "@soot"` per layer.
- `beam` is drawn as one distance field: `core: 0.6` widens the bright centre, no second thin beam needed. `funnel` takes `profile`, `bend`, `ripple` (keys bottom to top) for a curved column. `arc` uses `tail` (not `trail`).
- Mistakes come back as one line naming the layer, the wrong key and the closest right one (exit 2).
- Honest limit: layers draw clean, readable game-sprite effects, not hand-painted detail. Judge `_contact.png` as you would any art, change numbers (counts, sizes, windows, bias), render again; two or three rounds is normal.
- Share a recipe by sending the JSON file. The same file renders the same frames anywhere (`gizvfx render my.json`).


## 4. Painted (hi-res) version of a recipe

`--style ink|watercolor|comic|chalk|linocut|stencil|glitch|lineart` (default ink); `--intensity 0..2` and `--hold N` shape `glitch` (how wrecked it is, and how many frames each glitch pose lasts: 1 = new every frame, 4 = stutter) changes the look of the same recipe: `watercolor` wet edges, granulation and a soft bleed (heals, poison, mist, washes); `comic` flat colour with a black outline (hits, bursts, claw marks, anything that must read at a glance); `chalk` broken, dusty coverage (dust, smoke, rough scribbles); `linocut` is black ink with gouge cuts (the bright core becomes bare paper; reads on light backgrounds); `stencil` is spray paint: a hard core and a mist of overspray dots (splats, graffiti hits); `lineart` keeps only a thin bright outline with a glow (magic, energy; best on dark backgrounds); `glitch` is a broken screen: sliced rows, an RGB split and scanlines, different in every frame (the only style that changes with time); `ink` is the brush look. In the skill claude-drawing the styles that suit effects best are comic (burst frames, speed lines, puffs), ink wash, watercolor, chalk/crayon, spray stencil (splats, drips), linocut (white gouge cuts), CRT/VHS (glitch overlays) and cartoon sparkle/puff vocabulary; all of these but the single-line draw-on trail are built (CRT/VHS became `glitch`; a single-line trail is `lineart` or a thin `brush`).

`python gizvfx.py painted ID [--scale 4] [--bg #hex|none]` draws the **same recipe** smooth at 4x the size with a real alpha channel (no palette limit, no dither): bristle lanes with a paint body, soft grain, anti-aliased hatch lines and halftone dots. Output: `NAME_painted.gif` and `NAME_painted_sheet.png` + `.json` (transparent frames). `brush hatch halftone burst speedlines splat glow disc ring particles blob star orbit beam funnel bolt rays poly` are drawn natively smooth; `include` is drawn by the same painted renderer (its time stretched over the layer's window) and smoothly upscaled, then styled, so every shipped recipe has a fully native painted version; glows are added as light on top of everything and fall off in the same bands as in the pixel renderer (with soft edges) (a soft glow stays soft in every style; `smear`, `erode`, `outline` and `rim` work in the painted version too). The outermost recipe pixel of a painted frame is always empty. `python -c "from gizvfx import painted; print(painted.check('melee/ink-slash'))"` checks it (deterministic, one-shot ends empty, nothing touches the edge). It is not pixel art: use it for HD or non-pixel projects, and `gizvfx render` for pixel sprites. Pigment is drawn on transparent, so it reads best on light backgrounds.


## 5. `fix`: check, repair, write

`python gizvfx.py fix ID|my.json ... [--all] [--out DIR] [--painted STYLE]` renders the effect, repairs what a machine can repair, writes the GIF, sprite sheet, JSON and contact sheet to `--out` plus `NAME_fix.txt`, and prints what is left. Exit 1 when something is left. The original recipe is never changed.

Repaired: a cropped effect gets a bigger canvas (`NAME.fixed.json` is the new recipe; glow counts); one-pixel holes are filled (skipped when there are so many that it is dithering); lone pixels are removed when `check --report` flags them; more than 40 colours are limited to 24; a one-shot that does not end empty fades out over its last 3 frames.
Left for you (with the fix named in the line): loop that does not close, mesh dithering, flat colour, empty frames, motion pops, Python-code effects that touch the edge (they cannot be resized). `--painted STYLE` also runs the painted check for that style (recipes only).
