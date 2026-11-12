# GizVFX handout for coding agents

GizVFX draws effects from code: a pixel sprite version (palette-limited, dithered, sprite sheet + GIF) and the **same recipe** painted smooth at 4x in eight styles (ink, watercolor, comic, chalk, linocut, stencil, glitch, lineart). No reference image, no AI call, no network. Python 3 + numpy + Pillow (+ scipy for the painted `poly` layer).

## 1. The prompt-to-effect loop

The user describes an effect in words ("a frost nova for my mage", "an ink slash"). Do not refuse and do not hand-code Python:

1. `python gizvfx.py list WORD` : is there a close one already?
2. Copy the nearest recipe (`recipe ID > my.json`) or start a new one; turn the words into layers with the table in section 3.
3. `python gizvfx.py render my.json --out fx` and OPEN `fx/my_contact.png`; fix numbers; `python gizvfx.py check my.json --report`.
4. If the user wants a painted look: `python gizvfx.py painted my.json --style watercolor --out fx` (section 4).

Defaults: `render` and `fix` draw at `--scale 4` (pixel sprites enlarged 4x for the GIF and contact sheet; the sprite sheet is enlarged too), `painted` at 4x smooth; `--out` is `gizvfx_out` (`gizvfx_fix` for `fix`); a one-shot GIF holds its last (blank) frame for 4 frame durations before it restarts. The GIF file stores identical neighbouring frames as one long frame, so its frame count (PIL `n_frames`) is not the sprite sheet's count plus 4: count frames from the sheet or the contact sheet. Contact sheets are grids about as wide as tall (about 2400 px at most; the tiles shrink to fit, so look at single frames of the GIF for fine detail). `list` marks each effect `recipe` (JSON: `recipe ID` prints it, you can copy it) or `code` (drawn by Python: cannot be copied, only used and recoloured). Output file names are the last part of the effect id; for your own recipe file that is its `"id"` (`shield.json` with `"id": "fx/shield-hit"` writes `shield-hit.gif`), or the file name when it has no `id`, e.g. `heal-cross.gif`; `--name` sets the whole file name (for `painted` too: `--name coin` writes `coin.gif`, without the style suffix). `painted --bg` sets the ground of the GIF and of the contact sheet.

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
| a trail of sparkles, snowflakes or embers left behind a flying bolt, orb or arrow | `particles` `mode: stream` with `drop: true` on the same `at` path as the thing that flies (a one-shot): each particle stays where the layer was when it was born; `speed` small, `life` 0.2-0.4 |
| a sea wave that rises, curls and crashes, a breaking wave, a swell | `wave` (`height` and `curl` 0..1 animatable: 0 a steep face, 1 a hollow barrel; `length` of the back slope behind the crest, `dir` 1 or -1, `foam`, `streaks`; the water line is at `at`, the crest is above it; the back slope reaches `length` px to the side, leave room). Give it an `id` and other layers can sit on its surface (below). See `recipe water/breaking-wave` and `water/surfer-wave` |
| a stretch of sea, a water surface, a pool, a puddle | `water` (`width`, `depth` animatable [10, 10, 0] drains it away, `ripple`, `wavelength`, `flow` whole cycles, `taper` ends, `foam`). Draw the wave first and the `water` after it, so the sea covers the wave's foot |
| wisps that fly from A to B, energy sucked into a portal | `particles` with `target` (and `curve`, one number of px, to bow them) |
| crystals, rocks, shards, spikes | `poly` (`shape: crystal | shard | rock | diamond | arrow | heart`, or `points`; animate `scale` and `rotate`) |
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
- Loops: use only `{"wave": [lo, hi, whole_cycles]}`, particles `stream` with whole `cycles`, orbits with whole `turns`, a `poly` `rotate` of a full turn (`[0, 360]`) and `funnel` `turns`. Things that run on window progress break the seam: `arc` `sweep`, `blob` `drift` and a `rise` that does not return (both are fine in a one-shot; the tool does not stop you in a loop, the seam just shows), `smear` on a one-way move. (`blob` `stagger` is ignored in loops for that reason.)
- `blob` bands: `depth` about 1.3 times the radius gives layered colour; a small depth gives a flat pale blob. `cover` below 0.3 looks like a mesh at 1x: prefer thin layers, a stepped `glow` or a `ring` to dithered fills.
- A value can have more than two keys: `"size": [0, 20, 0]` grows then shrinks in ONE layer (no second layer needed). `"$reach*0.5"` scales an option. `blob` takes `lit: [-1, -1]` for sphere-like shading, `bolt` takes `rim: "#hex"` (a colour: the lighter edge under the stroke; the generic `rim: [dx, dy]` is for the other layers) (cracks on dark ground), `beam` takes `shade: flat` (no stripes), `blob` takes `erode: [0, 0, 16]` (the body is eaten from its edge: the clean way to dissolve; avoid `cover`), `glow` and `rays` take `squash` (lying on the floor), `particles` take `shape: star` (twinkles).
- Options work everywhere a number is, including inside lists and paths: `"at": [[0, 0], [30, "-$h"], [60, 0]]`, a `brush` `path`, `poly` `points`, a `hatch` `size`. A shape that must change with an option (a wave height) is written with the option inside its points.
- `squash` is animatable on `ring`, `glow`, `orbit` and `rays`: `"squash": [1, 0.15, 1]` on a `ring` is a spinning coin or a turning disc.
- A path (`at` with 3 or more points) is walked over the layer's own `t` window, so two layers only move together when they have the same `t` (and the same `at`). Give a trail and the thing that makes it the same `t` window.
- A `ring` band reaches `thick`/2 on each side of its `radius`: with `thick` of at least 2 x `radius` the hole closes and it is a filled disc (an ellipse with `squash`: useful for a disc seen edge-on); a smaller `thick` is just a fat ring; `check --report` flags options that no layer uses (`FLAG option 'foam' is never used`).
- Option values may be negated or calculated with: one sign and one operator (`* + - /`) and a number, written without spaces: `"-$height"`, `"$cloud+4"`, `"$w/2"`; several operators chain left to right without precedence: `"$w*2+4"` is `$w*2` then `+4`. Two options in one expression (`$a+$b`) are not supported: make it a third option.
- `-o palette=NAME` recolours the layers that use the recipe's own palette. A layer that names its own `palette` (a ramp name or a role like `"@accent"`) keeps it; change those in the recipe.
- Options make a recipe reusable: `"options": {"radius": 24}` and `"radius": "$radius"` inside; the user then runs `-o radius=40`. `-o palette=NAME` recolours the whole thing.
- `python gizvfx.py check my.json --report` prints numbers and FLAG lines (mesh dithering, flat colour, lone pixels, empty frames, motion pops) with the fix for each; run it after every render, then still LOOK at the contact sheet. A motion pop on a hit that lands after a flight is intended.
- Limits (every recipe): at most 40 layers, canvas 8 to 256 px, particle `count` 400, other counts 64 (blob 60). A recipe someone sends you: `python gizvfx.py import FILE.json` validates it, applies the limits, runs `check` and the report, and keeps a copy under `~/.gizvfx/recipes` (it then shows in `gizvfx list`); a recipe never runs code, reads outside its own folder, or fetches anything.
- A one-shot `beam` thins to a white needle at the end unless it is told to dissolve: `erode: [0, 0, 4]` (works on `beam`, `bolt`, `ring`, `particles` and most layers, see `schema`) or a `width` that ends at 0. Particles `shape: star` draw a bright centre pixel and arms in the colour of `v`; with arms of one pixel the difference between `v` values is small, so use `color` for a fixed colour. `v` is a number or `[from, to]`; a key a layer does not take is an error naming the closest valid one.
- **Things that sit on a wave or float on the sea** (a surfboard, a gull, a buoy, a rope end): give the `wave` or `water` layer an `id` (`"id": "w"`), then any layer can use, instead of `at`: `"at": {"on": "w", "point": "slope", "u": 0.6, "dx": 0, "dy": -1.5, "tilt": true}`.
  - Wave points: `crest`, `lip` (the tip of the curl), `foot` (front), `trough` (back foot), `slope` (`u` 0 at the foot to 1 at the crest), `face` (the inner wall of the barrel), `barrel` (its middle). The point follows the wave while it rises and curls.
  - Water: `"at": {"on": "s", "x": 40, "tilt": true}` is the surface at `x` px from the middle of the sea; it follows the ripples (a float bobs and tilts).
  - `u`, `x`, `dx`, `dy` may be `[from, to]` (or longer) over the asking layer's own `t` window: `"u": [0.92, 0.35]` slides a lifebuoy down the slope while the wave changes.
  - `tilt: true` turns a `poly` to lie on the surface there. `drop: true` particles on such an `at` leave a trail from the point.
  - `bolt` and `beam` may use the same dict for `from` and `to` (a rope between the crest and the lifebuoy that follows both ends), particles for `target`. See `recipe water/rescue-wave`.
  - `dx` and `dy` are screen offsets added after the point is found (`dy` negative = up, straight up the screen, not along the surface normal). `x` of a water anchor is measured from the middle of the sea.
  - `point` itself cannot change over time. To move something from one place on the wave to another, animate `u` on `slope`, or give `dx` and `dy` as `[from, to]` lists, or use two layers with their own `t` windows.
  - Layers draw in list order, anchors or not: a `water` layer drawn after a float covers everything of the float below the water line (that is how a float sinks); draw it before to keep the float on top.
  - Not supported: a list of these dicts as a path, and anchors on any layer other than `wave` and `water`.
- Coordinates: `wave` `at` is the water line under the crest; the back slope reaches `length` px to the left of it (`dir: -1` mirrors everything), the front foot about 0.3 x `height` + the barrel to the right. `water` `at` is the MIDDLE of the stretch, it reaches `width`/2 each way. When `check` says the edge is touched, `water` layers wider than the canvas are named.
- `palettes` entries may use options: `"palettes": {"rope": "$ringc"}` with `"options": {"ringc": "fire"}`; a layer says `"palette": "@rope"`.
- `rotate`, `scale` and every key marked animatable take a number or a list `[from, to, ...]` over the layer's window (a layer's own `ease` shapes it); a key that a layer does not use is an error naming the closest valid one, not ignored. `poly` is drawn with several steps of the palette ramp (darker at the edge, lighter inside and towards `lit`), or one flat hex colour with `color`; a part with its own colours (a hull, a sail) is a separate `poly` layer.
- **A charge-up loop, then a release** (the loop keeps going until the player acts, then the release plays): make two recipes. The loop recipe (`"loop": true`) is the idle effect you export for the game to repeat. The one-shot release `include`s it for its first part (`{"type": "include", "recipe": "idle.json", "repeat": 2, "t": [0, 0.5]}`; a `.json` path is looked up next to your recipe file; `repeat` plays it that many times in the window) and then adds the pillar, the creature, the burst in later windows. In the game: play the loop sheet until the trigger, then the release sheet. A single recipe cannot wait for a trigger, because a recipe has a fixed length. Mind the speed: an included recipe's time is stretched over the window, so each pass takes `window x release duration / repeat` seconds. For the idle loop to keep its own speed, set the release `duration` to `idle duration x repeat / window length` (idle 1.6 s, `repeat` 2, window `[0, 0.5]` gives 6.4 s). To fade the idle part out at the hand-over instead of cutting it, give the `include` layer an `erode` list such as `[0, 0, 4]`, or let the release layers cover it.
- `flash`: `"flash": [0.3, 0.55, [0.8, 1.5]]` makes the layer flare toward white at those moments (`t` 0..1 of the whole effect; a pair is `[t, strength]`) and fade over about 8% of the effect, with a little extra light in the pixel renderer. Use it for the reaction to a hit: a shield ring that brightens when a spark lands, a pillar that surges. Time it by hand to the moment the other layer arrives. It flares toward white, so on a light ground (`painted --bg` light) it is hard to see: use a dark ground to judge it, or flash a layer that has a dark colour.
- `clip`: `"clip": "pillar"` (the `id` of another layer) draws a layer only where that layer has pixels at the same moment: a creature silhouette inside a pillar of light, a texture inside a bubble. The clipped layer still covers the target where it is drawn, so draw it after the target; a missing or self-referring `id` is an error naming the layer.
- Option values may be chained left to right without spaces: `"$height*0.25+3"` (no precedence).
- `--bg` for painted GIFs: a glow on empty ground keeps its hue (soft yellow for a holy glow) on light, mid-tone and dark grounds; a light ground (`#f4efe4`) suits `comic`, `ink` and `watercolor`, a dark ground suits `lineart` and glow-heavy effects. A glow is faint by design on a very light ground: raise its `strength`.
- Draw order is layer order: a `glow` after a body whitens it, so put glows first. `poly` is centred on `at` unless `anchor: base` (then its lowest point sits on `at`: use it for anything standing on the floor). `poly` and `blob` on dark palettes (stone, ice, smoke) often need `bias` around -0.2, or they come out flat pale.
- Thrown things and fountains: `particles` with `lob: true`, `angle` upward, `speed` S: each follows a parabola and lands back at its spawn height at the end of its life; the peak is about S/4 px. Aim a thrown boulder with `at` on a curve (3+ points) instead.
- `ease` can be a list, one name per key step: `"size": [0, 20, 0], "ease": ["out", "in"]`. A recipe can say `"style": {"outline": "auto", "rim": [-1, -1], "shadow": [1, 1]}` for a consistent drawn look over the whole effect, and `"palettes": {"hot": "fire", "soot": "smoke"}` with `"palette": "@soot"` per layer.
- `beam` is drawn as one distance field: `core: 0.6` widens the bright centre, no second thin beam needed. `funnel` takes `profile`, `bend`, `ripple` (keys bottom to top) for a curved column. `arc` uses `tail` (not `trail`).
- Mistakes come back as one line naming the layer, the wrong key and the closest right one (exit 2).
- Honest limit: layers draw clean, readable game-sprite effects, not hand-painted detail. Judge `_contact.png` as you would any art, change numbers (counts, sizes, windows, bias), render again; two or three rounds is normal.
- Share a recipe by sending the JSON file. The same file renders the same frames anywhere (`gizvfx render my.json`).


## 4. Painted (hi-res) version of a recipe

`python gizvfx.py painted ID|my.json [--scale 4] [--style STYLE] [--bg #hex|none] [--intensity 0..2] [--hold N]` draws the **same recipe** smooth at 4x the size with a real alpha channel: no palette limit, no dither, bristle lanes with a paint body, soft grain, anti-aliased hatch lines and halftone dots.

Output in `--out`: `NAME_painted.gif` for the default style `ink`, `NAME_STYLE.gif` for any other (`NAME_chalk.gif`), so two styles can share a folder; `NAME_painted_sheet.png` + `.json` (transparent frames, one row) and `NAME_painted_contact.png` (a wrapped grid on a light ground: open this one).

Styles (default `ink`):
- `ink`: the brush look.
- `watercolor`: wet edges, granulation, a soft bleed (heals, poison, mist, washes).
- `comic`: flat colour with a black outline (hits, bursts, claw marks, anything that must read at a glance).
- `chalk`: broken, dusty coverage (dust, smoke, rough scribbles).
- `linocut`: black ink with gouge cuts; the bright core becomes bare paper (reads on light backgrounds).
- `stencil`: spray paint, a hard core and a mist of overspray dots (splats, graffiti hits).
- `lineart`: only a thin bright outline with a glow (magic, energy; best on dark backgrounds).
- `glitch`: a broken screen with sliced rows, an RGB split and scanlines, different in every frame (the only style that changes with time). `--intensity` sets how wrecked it is; `--hold N` is how many frames each glitch pose lasts (1 = new every frame, 4 = stutter).

What is drawn natively smooth: `brush hatch halftone burst speedlines splat glow disc ring particles blob star orbit beam funnel bolt rays poly`, plus `smear`, `erode`, `outline` and `rim`. `include` is drawn by the same painted renderer (its time stretched over the layer's window) and smoothly upscaled, then styled. So every recipe has a painted version; the 13 Python effects do not.

Glows are added as light on top of everything and fall off in the same bands as in the pixel renderer, with soft edges. The outermost pixel of a painted frame is always empty.

Check it: `python -c "from gizvfx import painted; print(painted.check('melee/ink-slash'))"` (deterministic, one-shot ends empty, nothing touches the edge).

Known looks: a `smear` trail is drawn as 24 softened copies (a streak, not stacked discs; in `comic`, `linocut` and `stencil` the trail copies have no outline of their own). A `bolt` is pale by design and fades almost to white on a light background: use `--bg` with a mid or dark colour, or the `lineart` and `glitch` styles, for it. A `glow` keeps its hue on any ground but is faint on a very light one.

It is not pixel art: use it for HD or non-pixel projects, and `gizvfx render` for pixel sprites. Pigment is drawn on transparent, so it reads best on light backgrounds (except `lineart` and `glitch`).

## 5. `fix`: check, repair, write

`python gizvfx.py fix ID|my.json ... [--all] [--out DIR] [--painted STYLE]` renders the effect, repairs what a machine can repair, writes the GIF, sprite sheet, JSON and contact sheet to `--out` plus `NAME_fix.txt`, and prints what is left. Exit 1 when something is left. The original recipe is never changed.

Repaired: a cropped effect gets a bigger canvas (`NAME.fixed.json` is the new recipe; glow counts); one-pixel holes are filled (skipped when there are so many that it is dithering); lone pixels are removed when `check --report` flags them; more than 40 colours are limited to 24; a one-shot that does not end empty fades out over its last 3 frames.
When the canvas is cropped, `fix` draws the effect once on a big canvas, measures what it really covers and cuts the canvas to that plus 8 px (one step, not repeated growing). `fix --apply` writes the fixed recipe over yours (the old one is kept as `NAME.json.bak`); without it your recipe is never touched and the line says so. `NAME.fixed.json` is written only when the canvas had to change (the other repairs are in the GIF and sheet only, never in your recipe); it is the recipe to keep, the GIF and sheet beside it are drawn from it. A canvas is at most 256 px: when the effect still touches the edge at that size, `fix` stops growing it and lists that as something to fix by hand (make the effect smaller or move the pivot). `check` and `fix` name the edge (top, bottom, left, right) and the first frame that touches it.
Exit code: 0 when nothing must be fixed by hand, 1 when something must be (cropped Python effect, no empty end, loop seam, painted check). Advisory `note:` lines never change the exit code.
To fix by hand (the fix is named in the line): loop that does not close and Python-code effects that touch the edge (they cannot be resized). Notes (advisory): mesh dithering, flat colour, empty frames, lone pixels, motion pops; a motion pop on a hit that lands after a flight is meant. `--painted STYLE` also runs the painted check for that style (recipes only).
