# Manga Cargo Cube — A1 mini

A **true 216 mm cube** — same on every axis — printed in 12 parts that lock
together with no glue, no screws and no supports. Sci-fi cargo crate detailing:
corner castings, bolted seam straps, octagonal machined panels with X-bracing,
louver vent banks, hazard-striped rails and a framed front hatch.

![preview](docs/cube_preview.png)

```
python3 -m pip install -r requirements.txt
python3 src/manga_cube.py --out stl          # writes all 12 STLs
PYTHONPATH=src python3 src/verify_cube.py    # parts, fit, locks, printability
PYTHONPATH=src python3 src/render_cube.py --out docs
```

## Why 12 parts

A 216 mm cube has no piece that fits the A1 mini's 180 mm plate whole. Any
2-way split of a cube over 180 mm leaves at least one piece carrying a
full-width cross-section, and the largest square that fits inside a 180 mm cube
is only ~191 mm — so **all three axes have to be split**. 2 × 2 × 2 is the
coarsest split that works: eight 108 mm octants, plus four spline keys.

216 mm is the smallest cube that still swallows a standing Viz shonen volume
(190.5 mm) behind a 12 mm floor and a 10 mm ceiling, with 3.5 mm to spare.

## How it locks

The hard part is that **four pieces in a closed ring cannot all use the same
sliding joint** — the last one would have to slide two directions at once. So
the two tiers lock differently:

**Lower ring** — the four base octants butt together, then four dovetail
spline keys drop down the vertical seams. Each key is a *bowtie* in section,
widest at both roots and pinched at the seam, so neither octant can pull away
sideways. Once the cap is on, the keys are trapped and cannot back out.

**Cap** — each upper octant locks to the body **on its own**: set it down 8 mm
forward, lower it so two dovetail tenons drop into their pockets, then slide it
back. The channels are blind, so it stops exactly flush. Because no cap piece
depends on its neighbours, the ring-of-four problem never arises.

`verify_cube.py` proves the mechanism rather than assuming it: for every cap
octant it sweeps the descent and the slide for collisions, confirms the blind
channel stops it (43 mm³ of interference if pushed 1 mm past flush), and
confirms it cannot be lifted — 0.60 mm of play before the dovetail bites. It
also pulls a base octant sideways and checks it fouls its key.

## Assembly

1. Butt the four `base_*` octants together on a flat surface.
2. Drop `key_1`–`key_4` down the vertical seams (three long, one short in the
   hatch sill). The lower ring is now locked laterally.
3. For each `cap_*` octant: set it on its quarter 8 mm forward, lower it, slide
   it back until it stops. It is now locked down and the keys beneath are
   captive.

Loading works either way — through the front hatch, or by sliding one cap
octant forward and lifting it off.

## Specification

| | |
| --- | --- |
| Assembled | 216 × 216 × 216 mm, true cube |
| Parts | 8 octants at 108 mm + 4 spline keys |
| Capacity | 6 volumes at 20 mm |
| Walls / floor / ceiling | 12 / 12 / 10 mm |
| Front hatch | 126 × 124 mm, self-supporting head |
| Cap lock | 8 dovetail tenons, 8 mm travel, blind channels, 0.20 mm fit |
| Material | 2197 cm³ solid across all parts |

## Printing

No supports anywhere. All relief is cut into the envelope, openings flare 45°,
and both wide recesses are narrow grooves instead, so nothing bridges more than
10 mm. `verify_cube.py` asserts this against each part in its own orientation.

- **Supports:** off · **Layer:** 0.2 mm · **Walls:** 3 · **Infill:** 10–15%
- **Orientation:** as exported. Base octants sit floor-down, cap octants are
  already flipped crown-down, keys stand on end.
- **Filament:** roughly 1.0–1.3 kg for the set. A 12 mm wall prints mostly
  hollow, so this is well under the 2197 cm³ solid figure — but it is an
  estimate, so slice it for real numbers. Expect a long queue of 12 prints.

If the dovetails or keys are tight on your printer, raise `FIT`; if they
rattle, lower it. 0.20 mm per side is the starting point.

## Changing it

Everything lives in the `PARAMETERS` block of `src/manga_cube.py`.

- `SIDE` — the cube. Below ~213 mm the book no longer fits standing
- `BAY`, `BOOK_*` — the bay and the media it is cut for
- `RELIEF_FRAME` / `_BEVEL` / `_FIELD` / `_VENT` — the four relief planes.
  `RELIEF_VENT` must stay well clear of `WALL` or the louvers cut through
- `POST_L`, `STRAP_W`, `BAND_H`, `VENT_N`, `BOLT_R`, `STRIPE_PITCH` — greebling
- `TRAVEL`, `DT_*`, `KEY_*`, `FIT` — the locks

Four rules the code depends on:

- All exterior relief is **cut from** the envelope, never added to a smaller
  body, so no detailing can push a part past the plate.
- The seam straps and the tier band sit at the full envelope **on purpose**:
  every split line lands under one, so a joint reads as a bolted strap.
- `skin_side()` exists because `profile()` insets in Z as well as X and Y, so a
  plain `skin()` carries full-width slabs at the crown and base. Cutting with
  those shaves the ends; clipping them off in Z instead lands a cut plane on
  the inset profile's end face and detaches them into separate bodies.
- `cleanup()` drops hairline boolean debris, and `weld()` collapses the ~1e-5 mm
  slivers that would otherwise leave the exported STL non-watertight even
  though the solid is manifold. Both refuse to touch real geometry.

Earlier designs — a one-piece 178 mm cube and a two-part 178 × 178 × 205 mm
crate — are in git history on this branch.
