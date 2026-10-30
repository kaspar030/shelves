# Cluster Shelves — parametric hex-grid trays + clip-in accessories (µcad)

A CAD pipeline that turns a one-line manifest entry into printable STLs for a
homelab cluster of Raspberry Pi, ST Nucleo, Nordic nRF52840-DK, RP2040 Pico and
small mini-PC boards.

The whole system is built around **one universal honeycomb hex grid**:

* **Trays** are open-top boxes whose **floor *and* all four walls are
  hex-perforated** — for airflow, visibility, and as a universal mounting grid.
* **Boards** don't bolt to the tray. They clip into press-in **holders** that
  snap into the hex **floor**.
* **Cables** run up a **back-wall notch** that lines up through the stack, and
  are dressed with **cable combs / hooks** that snap into the hex **walls**.
* Every accessory mounts the same way: a **hex plug** that pushes into a grid
  cell and snaps. Holders, combs and hooks are just different fronts on that
  one connector.
* Trays **stack** via 4 solid corner posts: each carries a peg on top and a
  socket in its base, so a tray drops onto the one below and self-aligns. The
  posts are solid, so the pegs always stand on material (no floating bits).

```
        cable trunk runs up the back-wall notches
                       │
   ┌───────────────┐   │   ⬡⬡⬡⬡⬡  hex walls: airflow + clip-in cable combs/hooks
   │  tray_std     ⬡⬡⬡⬡│⬡  ◄── nucleo board on a bolt-in holder, clipped to floor
   ├───────────────┤   │
   │  tray_std     ⬡⬡⬡⬡│⬡  ◄── nRF52840-DK on its holder
   ├───────────────┤   │
   │  tray_low     ⬡⬡⬡ │   ◄── pico on a clip-in holder
   └───────────────┘   │
     pegs↑ sockets↓      hex floor: boards clip in anywhere on the grid
```

## What you get

| File / dir | Purpose |
|---|---|
| `shelves.mu` | Library root (declares the modules in `shelves/`). |
| `shelves/params.mu` | All master constants (footprint, hex pitch, plug, pegs). |
| `shelves/hexgrid.mu` | Honeycomb generator + the shared **cell coordinate system**. |
| `shelves/connector.mu` | The **hex plug** + plug groups (`PlugPair`, `PlugBed`, …). |
| `shelves/holders.mu` | `BoltHolder` / `ClipHolder` — board holders that clip to the floor. |
| `shelves/cables.mu` | `CableComb` / `CableHook` — cable management that clips to walls. |
| `shelves/tray.mu` | `Tray` — the stackable hex-grid box. |
| `shelves/devices/` | One profile per board (size, hole pattern, heights). |
| `shelves.toml` | Build manifest — declares which STLs to produce. |
| `scripts/build.py` | Pipeline: manifest → generated µcad → exported STL. |
| `lib.mu`, `build/` | Generated root source / exported STLs (git-ignored). |

## Quick start

```sh
cargo install mucad@0.6.0   # needs cmake + ninja for the geometry kernel
make all                    # generate + export everything to build/
ls build/                   # your STLs
```

Build one part, or finer mesh:

```sh
python3 scripts/build.py holder_nucleo
python3 scripts/build.py --resolution 0.05mm
make check                  # type-check the generated root + library
```

## The manifest (`shelves.toml`)

Each `[[shelf]]` block becomes `build/<name>.stl` (`name` must be a lowercase
identifier — it becomes a µcad statement name in the generated `lib.mu`):

```toml
# A stackable hex-grid box (device-agnostic — boards clip into the floor).
[[shelf]]
kind   = "tray"             # the one stackable box
name   = "tray_std"
height = "30mm"

# A board holder that clips into a tray floor.
[[shelf]]
kind   = "bolt_holder"      # "bolt_holder" (screws) | "clip_holder" (snap tabs)
device = "nucleo"           # rpi4|rpi_zero|pico|nucleo|nrf52840dk|minipc
name   = "holder_nucleo"

# A cable accessory that clips into a hex wall.
[[shelf]]
kind   = "cable_comb"       # "cable_comb" (teeth=N) | "cable_hook" (opening=…)
name   = "cable_comb_4"
teeth  = 4
```

Trays take optional `height` / `width` / `depth`. Holders read their
geometry from the device profile. Combs take `teeth`; hooks take `opening`.

## How the hex grid works (the core idea)

* **Honeycomb**: flats top/bottom, across-flats `HEX_AF = 14mm`, web
  `HEX_WALL = 2.4mm` between holes. Nearest-neighbour hole centres are exactly
  `HEX_AF + HEX_WALL = 16.4mm` apart → a uniform 2.4mm wall everywhere. (The web
  width also sets the plug pitch, so it is one shared constant — change it once
  and the grid *and* every accessory's plugs stay aligned.)
* **Cell coordinate system** (`shelves/hexgrid`): `cell_x(col)` / `cell_y(col,row)`
  give the exact centre of any hole. Both `HexField` (the perforation) and the
  plug groups use these same functions, so **a holder's plugs land exactly in
  the holes** — alignment is correct by construction.
* **The plug** (`shelves/connector`): a hex prism sized `HEX_AF − PLUG_CLEAR`, with
  a tapered snap **barb** that catches the back face of the surface. The barb is
  rotated 30° vs the shaft so the union stays watertight, and sized so adjacent
  plugs (one row-pitch apart) don't collide.
* **Anti-rotation**: a single plug can spin, so accessories use **two or more**
  plugs (`PlugPair` = two stacked cells; `PlugBed` = a cols×rows block).

## Board mounting

| Holder | Use for | How |
|---|---|---|
| `BoltHolder` | Nucleo, nRF52840-DK, Pi-class | board screws onto standoffs over its mount-hole pattern |
| `ClipHolder` | Pico, small MCU boards | board snaps under 4 printed corner clips — no screws |

Both ride on a `PlugBed` sized to the board, so they clip anywhere on a tray
floor and lift the board for airflow / underside-component clearance.

## Where the cables go

* The **back (−Y) wall** of every tray has a **cable-trunk notch**. Stacked
  trays line their notches up into a vertical channel; the main bundle runs up
  the back of the column.
* Branch cables are dressed along any wall with **`CableComb`** (several cables
  side-by-side, press-fit slots) or **`CableHook`** (a J-hook for a loop /
  bundle). Both clip into two vertically-adjacent wall cells.
* The hex perforation itself lets you zip-tie or route a cable through any cell.

## Adding a device

Create `shelves/devices/<name>.mu` with these public constants…

```µcad
pub const BOARD_W = 70mm;   pub const BOARD_D = 82.5mm;  pub const BOARD_T = 1.6mm;
pub const HOLE_DX = 60mm;   pub const HOLE_DY = 72mm;    // mount-hole spacing
pub const SCREW_D = 3.2mm;  pub const POST_D = 6mm;
pub const STANDOFF_H = 5mm; pub const TRAY_H = 30mm;
pub const FOOTPRINT_W = 120mm; pub const FOOTPRINT_D = 90mm;
```

…register it in `shelves/devices.mu` and add it to `VALID_DEVICES` in
`scripts/build.py`. The supplied Nucleo / nRF52840-DK / mini-PC hole spacings
are practical approximations — **measure your exact board and adjust**.

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
  defaults are literals (with a comment naming the constant in `params.µcad`).
* **Functions take named arguments**; no return-type annotation (last
  expression is the result).
* **No modulo operator** — parity is `col - 2*int(col/2)`.
* **Integer ranges**: `[0 .. n-1]`; arrays multiply geometry (multiplicity),
  and two arrays (`x=[..], y=[..]`) give the Cartesian product.
* **`std::math::int` floors toward −∞** (`int(-0.1) == -1`), so clamp counts.
* **Manifold unions**: coaxial aligned hex prisms share edges and produce
  non-manifold geometry — offset one by 30°. Touching-but-not-overlapping
  solids leave coincident faces — overlap mating parts by a small epsilon.
* **Extrude grows +Z from 0**; translate by `−thick/2` to centre a panel before
  rotating it into a wall.
* `#[export("path.stl")]` on a named statement (`name = Part(..);`) emits one
  STL; the path is relative to the source file's directory. One `mucad export`
  writes all of them.

## Printing tips

* PETG/ABS for trays near warm SBCs; PLA fine for cool MCU boards.
* Walls/floor/webs are multiples of a 0.4 mm line for clean slicing.
* Plug fit is `HEX_AF − PLUG_CLEAR` (0.35 mm); loosen/tighten `PLUG_CLEAR` in
  `shelves/params.mu` to match your printer. Snap barb is `PLUG_BARB` (0.45 mm).
* All shipped STLs are verified **watertight / manifold**.

## License

Code & models: MIT (SPDX headers). The µcad toolchain is AGPL-3.0 (its
standard library is MIT) — that covers the toolchain, not the STLs you produce.
