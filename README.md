# Cluster Shelves — parametric hex-grid trays + clip-in accessories (µcad)

A CAD pipeline that turns a few manifest lines into printable STLs for a
homelab cluster of Raspberry Pi 4 / Zero, RP2040 Pico, ST Nucleo-64 and
Nordic nRF52840-DK boards.

The whole system is built around **one universal honeycomb hex grid**:

* **Trays** are 160 × 100 mm open-top boxes whose **floor *and* all four walls
  are hex-perforated** — for airflow, visibility, and as a mounting grid.
* **Boards** sit on four **corner posts**. Each post snaps into one floor cell
  with a hex plug and carries one board mounting hole on top (self-tapping
  screw). No baseplate, so every post prints flat without supports.
* **Cables** leave through the wall hexes (large enough to push RJ45 and USB
  plugs through) and are dressed with **cable combs / hooks** that snap into
  the walls.
* Trays **stack** via 4 solid corner posts: each carries a peg on top and a
  socket in its base, so a tray drops onto the one below and self-aligns.

```
   ┌───────────────┐   ⬡⬡⬡⬡⬡  hex walls: airflow, cables, clip-in combs/hooks
   │  tray_std     │   ◄── Raspberry Pi 4 on four corner posts
   ├───────────────┤
   │  tray_std     │   ◄── nRF52840-DK
   ├───────────────┤
   │  tray_low     │   ◄── Pico (raised walls: full hexes + open half hexes)
   └───────────────┘
     pegs↑ sockets↓      hex floor: posts snap into any cell
```

## What you get

| File / dir | Purpose |
|---|---|
| `shelves.mu` | Library root (declares the modules in `shelves/`). |
| `shelves/params.mu` | Master constants (footprint, hex pitch, plug, pegs). |
| `shelves/hexgrid.mu` | Honeycomb generator + the shared **cell coordinate system**. |
| `shelves/connector.mu` | The snap-in **hex plug** + plug groups (`PlugPair`, …). |
| `shelves/holders.mu` | `CornerPost` — one board corner, plugs into a floor cell. |
| `shelves/cables.mu` | `CableComb` / `CableHook` — cable management for the walls. |
| `shelves/tray.mu` | `Tray` — the stackable hex-grid box. |
| `devices.toml` | Board data: outline, holes, connectors, required lift. |
| `shelves.toml` | Build manifest — declares which STLs to produce. |
| `scripts/build.py` | Pipeline: plans holders, generates µcad, exports STLs. |
| `lib.mu`, `build/` | Generated root source / STLs + holder plans (git-ignored). |

## Quick start

```sh
cargo install mucad@0.6.0   # needs cmake + ninja for the geometry kernel
make all                    # generate + export everything to build/
ls build/                   # your STLs + build/holder_*_plan.txt
```

Build one part, a finer mesh, or assembly previews:

```sh
python3 scripts/build.py holder_rpi4
python3 scripts/build.py --resolution 0.05mm
make preview                # also build/preview_holder_*.stl (tray+posts+board)
make check                  # type-check the generated root + library
```

## The manifest (`shelves.toml`)

`name` must be a lowercase identifier — it becomes a µcad statement name in
the generated `lib.mu`.

```toml
# A stackable hex-grid box -> build/tray_low.stl
[[shelf]]
kind   = "tray"
name   = "tray_low"
height = "20mm"
raised_walls = true     # full hexes low on the wall, half hexes open at the rim

# Corner posts for one board -> build/holder_rpi4_a.stl, _b.stl, + _plan.txt
[[shelf]]
kind   = "holder"
device = "rpi4"         # a key of devices.toml
name   = "holder_rpi4"
tray   = "tray_std"     # tray it goes in (used for --preview)

# A cable accessory that clips into a hex wall.
[[shelf]]
kind   = "cable_comb"   # "cable_comb" (teeth=N) | "cable_hook" (opening=…)
name   = "cable_comb_4"
teeth  = 4
```

## Board holders (corner posts)

A board is held by four `CornerPost`s. Each post is a prism: the hull of a hex
**shoulder** (a bit larger than the floor hole, so it rests on the web) and a
round **pad** under the board hole. Below it hangs the snap **plug**.

Board holes rarely sit over cell centres, so the pad is offset from the plug.
`scripts/build.py` plans every board:

* it tries all four board rotations and every position on the floor grid,
  and picks the one that leaves the **most room in front of the board's
  connectors** (boards are not centred — the connector sides get the space);
* each hole gets the nearest usable floor cell; the post offset is the hole's
  offset from that cell centre;
* posts whose offsets differ only by a multiple of 60° are the **same part**
  (the hex plug fits a cell in six orientations), so a rectangular hole pattern
  usually needs two post variants, printed twice each.

The result is `build/<name>_plan.txt`: how many of each post to print, which
floor cell each goes into and how it is turned, and the room left in front of
every connector. **Print posts upside down** (pad on the bed, plug up): no
supports needed.

## Board data (`devices.toml`)

Per board: outline, thickness, mounting holes, pilot-hole size, `lift` (floor
to board underside, to clear pins and parts underneath) and every edge
connector (edge, position, width, height, overhang). The `verified` field says
where the numbers come from. **The Nucleo-64 and nRF52840-DK hole and
connector positions are approximations — measure your board.**

## How the hex grid works (the core idea)

* **Honeycomb**: flats top/bottom, across-flats `HEX_AF = 14mm`, web
  `HEX_WALL = 2.4mm` between holes. Nearest-neighbour hole centres are exactly
  `HEX_AF + HEX_WALL = 16.4mm` apart → a uniform 2.4mm web everywhere.
* **Cell coordinate system** (`shelves/hexgrid`): `cell_x(col)` /
  `cell_y(col,row)` give the exact centre of any hole; `scripts/build.py`
  mirrors the same formulas to place posts.
* **The plug** (`shelves/connector`): a hex tube sized `HEX_AF − PLUG_CLEAR`,
  split into four fingers by two slots, with a snap **barb** (lead-in taper,
  flat retention face) that catches the underside of the floor. Being
  hexagonal it can't rotate in its cell.

## Where the cables go

* Out through the **wall hexes** — 14mm across flats, enough for RJ45 and
  USB-A plugs.
* Dressed along any wall with **`CableComb`** (several cables side by side) or
  **`CableHook`** (a J-hook for a bundle). Both clip into two vertically
  adjacent wall cells.

## Adding a device

Add a `[<key>]` table to `devices.toml` (see the existing entries) and a
`kind = "holder"` entry with `device = "<key>"` to `shelves.toml`. Run
`make preview` and look at `build/preview_<name>.stl` before printing.

## µcad 0.6 notes / gotchas (learned the hard way)

Properties of µcad 0.6 worth knowing before editing `shelves/`:

* **The CLI is `mucad`**, sources use the `.mu` extension, and `lib` is a
  reserved keyword (hence the library is called `shelves`).
* **Modules resolve relative to the file**: in `foo.mu`, `mod bar;` loads
  `foo/bar.mu`; in a file named `lib.mu` it loads `bar.mu` next to it. A
  directory module needs `bar.mu` + `bar/` — sub-modules of a `bar/mod.mu`
  are looked up in `bar/mod/` and don't resolve. Config `search_paths` only
  locate `std`, so the generated root `lib.mu` must live next to `shelves.mu`.
* **Functions can only call builtins**, not other user `fn`s (they fail with
  "cannot be called"). Parts/sketches can call `fn`s. Hence the pitch
  formulas are inlined in `hexgrid.mu` / `holders.mu`.
* **`const`s must be literal** — `const B = A + 1mm` is rejected, so derived
  constants (`SOCKET_D`, `SOCKET_DEPTH`) are spelled out with a comment.
* **`Ngon` / `std::geo2d::Hexagon` don't render** ("Built-in `Ngon` cannot be
  rendered"); `shelves::hexgrid::Hex` builds the hexagon from three rotated
  `Rect` strips instead.
* **Default parameter values must be literals** — default expressions evaluate
  in the *caller's* scope, so `x = SOME_CONST` fails cross-module. Library
  defaults are literals (with a comment naming the constant in `params.mu`).
* **Functions take named arguments**; no return-type annotation (last
  expression is the result).
* **No modulo operator** — parity is `col - 2*int(col/2)`.
* **Integer ranges**: `[0 .. n-1]`; arrays multiply geometry (multiplicity),
  and two arrays (`x=[..], y=[..]`) give the Cartesian product.
* **`std::math::int` floors toward −∞** (`int(-0.1) == -1`), so clamp counts.
* **Manifold unions**: coaxial aligned hex prisms whose edges touch produce
  non-manifold geometry — end one solid inside the other (see `Plug`).
  Touching-but-not-overlapping solids leave coincident faces — overlap mating
  parts by a small epsilon.
* **An `if` in a part/sketch body yields a model**, not a value — put value
  choices in a `fn` (e.g. `min_len` in `holders.mu`).
* **3D `hull()` exports an empty mesh**; 2D `hull()` works, so hull sketches
  and extrude them.
* **Extrude grows +Z from 0**; translate by `−thick/2` to centre a panel before
  rotating it into a wall.
* `#[export("path.stl")]` on a named statement (`name = Part(..);`) emits one
  STL; the path is relative to the source file's directory. One `mucad export`
  writes all of them.

## Printing tips

* PETG/ABS for trays near warm SBCs; PLA fine for cool MCU boards.
* Walls/floor/webs are multiples of a 0.4 mm line for clean slicing.
* Corner posts print **upside down** (pad on the bed, plug pointing up).
* Plug fit is `HEX_AF − PLUG_CLEAR` (0.35 mm); the barb sticks out
  `PLUG_BARB` (0.35 mm) past the shaft. PLA works, PETG flexes more kindly.
  Tune both in `Plug` (`shelves/connector.mu`) to match your printer.
* All shipped STLs are verified **watertight / manifold**.

## License

Code & models: MIT (SPDX headers). The µcad toolchain is AGPL-3.0 (its
standard library is MIT) — that covers the toolchain, not the STLs you produce.
