# Cluster Shelves — parametric stackable trays/drawers with µcad

A small CAD pipeline that turns a one-line manifest entry into a printable STL
for a homelab cluster: **stackable trays/drawers** for Raspberry Pi, Pi Zero,
MCU devboards (Pico), and small mini-PCs.

Every tray shares a common **footprint** and a **corner peg/socket interlock**,
so trays in the same family stack into a clean self-aligning column. Each tray
is parameterised for its device (mount-hole pattern, standoff height, tray
height, footprint).

```
   ┌───────────────┐   pegs (×4) ── drop into ──┐
   │   rpi4_tray    │ ▲▲                        │
   ├───────────────┤                            ▼
   │  rpi4_drawer   │   sockets (×4) on underside
   ├───────────────┤
   │  zero_tray ... │
   └───────────────┘
```

## What you get

| File / dir | Purpose |
|---|---|
| `lib/` | The reusable µcad component library (the actual CAD). |
| `lib/devices/` | One profile per device: board size, hole pattern, heights. |
| `shelves.toml` | Build manifest — declares which STLs to produce. |
| `scripts/build.py` | Pipeline: manifest → generated µcad → exported STL. |
| `gen/` | Generated µcad sources (git-ignored). |
| `build/` | Exported `.stl` files (git-ignored). |
| `Makefile` | `make all`, `make check`, `make clean`, … |

## Quick start

```sh
# 1. install the µcad toolchain (needs cmake + ninja for the geometry kernel)
cargo install microcad

# 2. build every shelf in the manifest
make all          # == python3 scripts/build.py

# 3. find your STLs
ls build/
```

Build just one shelf, or override the export resolution:

```sh
python3 scripts/build.py rpi4_tray
python3 scripts/build.py --resolution 0.05mm      # finer mesh
make check                                        # type-check only
```

## The manifest (`shelves.toml`)

Each `[[shelf]]` block becomes `build/<name>.stl`:

```toml
[[shelf]]
device = "rpi4"        # profile in lib/devices/  (rpi4|rpi_zero|pico|minipc)
kind   = "tray"        # "tray" (open top) | "drawer" (adds a finger pull)
name   = "rpi4_tray"   # output base name
# optional overrides:
# height = "30mm"
# width  = "120mm"     # footprint — keep equal across a stack!
# depth  = "90mm"
# vents  = false       # floor ventilation slots (default true)
```

## Design model

* **Footprint.** All trays meant to stack together must share `width`/`depth`.
  By default a shelf inherits its device profile's footprint
  (`FOOTPRINT_W`/`FOOTPRINT_D`). The Pi-class devices all use `120 × 90 mm`;
  the mini-PC profile uses a larger one (so it forms its *own* column).
* **Interlock.** `lib/stack.µcad` adds 4 corner **pegs** on the rim (pointing
  up) and 4 corner **sockets** on the underside (slip-fit, `peg Ø + clearance`).
  Tray N's pegs drop into tray N+1's sockets.
* **Mounting.** `lib/mount.µcad` places 4 **standoffs** on the device's
  rectangular hole pattern, each with a blind pilot hole for a self-tapping
  screw. The board sits `standoff_h` above the floor for airflow.
* **Coordinate convention** (library-wide): X/Y centred on the footprint;
  **Z = 0 is the tray's bottom face**, growing upward — so models sit on the
  print bed with no manual repositioning.
* **Safety check.** `Tray` asserts the hole pattern (+ standoff body) fits
  inside the interior; if a board is too big for the footprint you get a clear
  error instead of a broken mesh.

## Adding a device

Create `lib/devices/<name>.µcad` with these public constants…

```µcad
pub const BOARD_W = 85mm;   pub const BOARD_D = 56mm;
pub const HOLE_DX = 58mm;   pub const HOLE_DY = 49mm;   // hole-centre spacing
pub const SCREW_D = 2.6mm;  pub const POST_D = 6mm;
pub const STANDOFF_H = 4mm; pub const TRAY_H = 26mm;
pub const FOOTPRINT_W = 120mm; pub const FOOTPRINT_D = 90mm;
```

…register it in `lib/devices/mod.µcad` (`pub mod <name>;`), add it to
`VALID_DEVICES` in `scripts/build.py`, then reference it from `shelves.toml`.

## µcad notes / gotchas (learned the hard way)

These are properties of µcad 0.5 worth knowing before editing `lib/`:

* **Modules resolve by directory.** `mod foo;` looks for `foo.µcad` or
  `foo/mod.µcad` *next to the current file*. A file can't reach `../lib`.
  This pipeline instead adds the repo root to `search_paths` in
  `.microcad.toml`, so generated files can `use lib::tray::*` from anywhere.
* **Default parameter values must be literals.** Default expressions are
  evaluated in the *caller's* scope, so `height = SOME_CONST` fails when called
  from another module. The library uses literal defaults (with a comment naming
  the canonical constant in `lib/params.µcad`).
* **Function calls use named arguments**: `peg_xs(footprint_w = w, inset = i)`.
  µcad `fn`s have no return-type annotation; the last expression is the result.
* **Array → multiplicity.** Passing an array to a transform makes N copies:
  `Cube(..).translate(x = [0mm, 10mm, 20mm])`. Two arrays (`x=[..], y=[..]`)
  produce the **Cartesian product** — handy for 4 corner features.
* **Primitives are centred on all axes.** `Cube`/`Cylinder` are centred at the
  origin; translate by `size/2` to sit them on a surface.
* `#[export("path.stl")]` on a top-level node lets one source emit several STLs.

## Printing tips

* PETG/ABS for trays that sit near warm SBCs; PLA is fine for cool MCU boards.
* Walls/floor are multiples of a 0.4 mm line width for clean slicing.
* Sockets are sized `peg Ø + 2 × clearance` (default 0.3 mm) for a slip fit;
  tighten `CLEARANCE` in `lib/params.µcad` if your printer runs loose.

## License

Code & models: MIT (see SPDX headers). The µcad standard library it builds on
is AGPL-3.0 — that applies to the toolchain, not to the STLs you produce.
