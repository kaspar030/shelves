#!/usr/bin/env python3
"""Cluster-shelf pipeline: manifest -> generated µcad -> exported STL.

Reads shelves.toml (what to build) and devices.toml (board data) and
generates a single µcad root, `lib.mu`, next to the `shelves.mu` library.
Each part becomes one named, `#[export]`ed statement in that root, and one
`mucad export lib.mu` writes every STL into build/.

Why one generated root in the repo root: µcad 0.6 resolves `mod shelves;`
relative to the source file (and a file named `lib.mu` resolves its modules
in its own directory), while the CLI no longer loads libraries from search
paths. So the root has to sit beside `shelves.mu`.

Board holders are four corner posts that plug into tray floor cells. For each
board, `plan_holder` picks the board rotation and position on the hex grid
that leaves the most room in front of the board's connectors, and the post
offsets that put a pad under each mounting hole. The plan (which cells to
use, how many of each post to print) is written to build/<name>_plan.txt.

Usage:
    scripts/build.py                # generate + export everything
    scripts/build.py --gen-only     # only (re)generate lib.mu (+ plans)
    scripts/build.py --preview      # also export preview_<holder>.stl
    scripts/build.py tray_std ...   # build only the named shelves
"""
from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROOT_SRC = ROOT / "lib.mu"
BUILD = ROOT / "build"
MANIFEST = ROOT / "shelves.toml"
DEVICES = ROOT / "devices.toml"

# --- Tray geometry (keep in sync with shelves/params.mu + shelves/tray.mu) --
TRAY_W, TRAY_D = 160.0, 100.0
FLOOR, WALL, POST = 2.0, 2.0, 10.0
HEX_AF, HEX_WALL, HEX_MARGIN = 14.0, 2.4, 4.0
SQRT3 = math.sqrt(3.0)
COL_PITCH = 0.75 * 2 * (HEX_AF / SQRT3) + HEX_WALL * SQRT3 / 2
ROW_PITCH = HEX_AF + HEX_WALL
SHOULDER_R = (HEX_AF + 2 * 1.5) / SQRT3   # CornerPost shoulder circumradius
POST_PAD_D = 6.0                          # CornerPost pad diameter

# Placement search
SOCKET_ROOM_CAP = 40.0    # more room than this in front of a socket is "enough"
ROOM_STEP = 5.0           # room differences below this don't beat fewer post variants
EDGE_GAP = 1.0            # minimum gap board <-> tray walls / corner posts

KINDS = {"tray", "holder", "cable_comb", "cable_hook"}


# --- Floor hex grid (mirrors shelves/hexgrid.mu) -----------------------------
def fit_cols(span: float, margin: float) -> int:
    usable = span - 2 * margin - 2 * HEX_AF / SQRT3
    return max(1, int(usable // COL_PITCH) + 1)


def fit_rows(span: float, margin: float) -> int:
    usable = span - 2 * margin - HEX_AF + ROW_PITCH / 2
    return max(1, int(usable // ROW_PITCH))


FLOOR_COLS = fit_cols(TRAY_W, HEX_MARGIN)
FLOOR_ROWS = fit_rows(TRAY_D, HEX_MARGIN)


def cell_xy(col: int, row: int) -> tuple[float, float]:
    x = (col - (FLOOR_COLS - 1) / 2) * COL_PITCH
    y = (row - (FLOOR_ROWS - 1) / 2) * ROW_PITCH - ROW_PITCH / 4 + (col % 2) * ROW_PITCH / 2
    return x, y


def _cell_usable(col: int, row: int) -> bool:
    """A post fits on this cell: its shoulder stays inside the walls and off
    the corner posts."""
    x, y = cell_xy(col, row)
    r = SHOULDER_R
    if abs(x) > TRAY_W / 2 - WALL - r or abs(y) > TRAY_D / 2 - WALL - r:
        return False
    in_post_x = abs(x) > TRAY_W / 2 - POST - r
    in_post_y = abs(y) > TRAY_D / 2 - POST - r
    return not (in_post_x and in_post_y)


USABLE = {(c, r) for c in range(FLOOR_COLS) for r in range(FLOOR_ROWS) if _cell_usable(c, r)}


def nearest_cell(x: float, y: float) -> tuple[int, int] | None:
    best = None
    c0 = round(x / COL_PITCH + (FLOOR_COLS - 1) / 2)
    for c in (c0 - 1, c0, c0 + 1):
        if not 0 <= c < FLOOR_COLS:
            continue
        r = round((y + ROW_PITCH / 4 - (c % 2) * ROW_PITCH / 2) / ROW_PITCH + (FLOOR_ROWS - 1) / 2)
        r = min(max(r, 0), FLOOR_ROWS - 1)
        cx, cy = cell_xy(c, r)
        d = math.hypot(x - cx, y - cy)
        if best is None or d < best[0]:
            best = (d, (c, r))
    return best[1] if best else None


# --- Holder planning ---------------------------------------------------------
EDGE_NORMAL = {"left": (-1, 0), "right": (1, 0), "bottom": (0, -1), "top": (0, 1)}


def rot(v, deg):
    a = math.radians(deg)
    return (v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a))


@dataclass
class Corner:
    hole: tuple[float, float]    # hole centre in tray coordinates
    cell: tuple[int, int]
    v: tuple[float, float]       # hole offset from the cell centre
    variant: int = 0
    angle: int = 0               # post rotation (deg) relative to its variant


@dataclass
class Plan:
    device: str
    rotation: int                # board rotation on the tray (deg)
    origin: tuple[float, float]  # board centre in tray coordinates
    size: tuple[float, float]    # rotated board size
    corners: list[Corner]
    variants: list[tuple[float, float]]   # canonical offset per variant
    socket_room: list[tuple[str, float]]
    lift: float


def _group_variants(offsets, tol=0.25):
    """Posts are interchangeable if their offsets differ by a 60° rotation
    (the hex plug fits the cell in all six orientations)."""
    variants: list[tuple[float, float]] = []
    assign = []
    for v in offsets:
        for i, c in enumerate(variants):
            hit = next((k * 60 for k in range(6)
                        if math.dist(rot(c, k * 60), v) < tol), None)
            if hit is not None:
                assign.append((i, hit))
                break
        else:
            variants.append(v)
            assign.append((len(variants) - 1, 0))
    return variants, assign


def plan_holder(key: str, dev: dict) -> Plan:
    w, d = dev["width"], dev["depth"]
    holes = [tuple(h) for h in dev["holes"]]
    sockets = dev.get("socket", [])
    inner_x, inner_y = TRAY_W / 2 - WALL, TRAY_D / 2 - WALL
    best = None

    for rotation in (0, 90, 180, 270):
        rw, rd = (w, d) if rotation in (0, 180) else (d, w)
        # board-frame point -> offset from the board centre, rotated
        to_c = lambda p: rot((p[0] - w / 2, p[1] - d / 2), rotation)  # noqa: E731
        rhole = [to_c(h) for h in holes]
        socks = []
        for s in sockets:
            nx, ny = EDGE_NORMAL[s["edge"]]
            along = s["at"]
            edge_pt = {"left": (0, along), "right": (w, along),
                       "bottom": (along, 0), "top": (along, d)}[s["edge"]]
            front = (edge_pt[0] + nx * s["overhang"], edge_pt[1] + ny * s["overhang"])
            socks.append((s["name"], to_c(front), rot((nx, ny), rotation)))

        # Candidate board centres: a 1mm grid, plus the positions that put
        # the hole pattern's centre on a point of symmetry of the hex grid
        # (a cell centre or the midpoint of two cells). For a rectangular
        # hole pattern those make opposite posts identical (180° apart).
        hc = (sum(h[0] for h in rhole) / len(rhole), sum(h[1] for h in rhole) / len(rhole))
        centres = [(float(ix), float(iy))
                   for ix in range(int(-(inner_x - rw / 2)), int(inner_x - rw / 2) + 1)
                   for iy in range(int(-(inner_y - rd / 2)), int(inner_y - rd / 2) + 1)]
        cells = [cell_xy(*c) for c in USABLE]
        centres += sorted({(round((a[0] + b[0]) / 2 - hc[0], 4), round((a[1] + b[1]) / 2 - hc[1], 4))
                           for a in cells for b in cells})
        for cx, cy in centres:
            if abs(cx) > inner_x - rw / 2 or abs(cy) > inner_y - rd / 2:
                continue
            # board clear of walls and corner posts
            x0, x1, y0, y1 = cx - rw / 2, cx + rw / 2, cy - rd / 2, cy + rd / 2
            if x0 < -inner_x + EDGE_GAP or x1 > inner_x - EDGE_GAP:
                continue
            if y0 < -inner_y + EDGE_GAP or y1 > inner_y - EDGE_GAP:
                continue
            px, py = TRAY_W / 2 - POST - EDGE_GAP, TRAY_D / 2 - POST - EDGE_GAP
            if (x0 < -px or x1 > px) and (y0 < -py or y1 > py):
                continue
            # room in front of each socket
            room = []
            for name, (fx, fy), (nx, ny) in socks:
                fx, fy = fx + cx, fy + cy
                r = (inner_x - fx if nx > 0.5 else fx + inner_x if nx < -0.5
                     else inner_y - fy if ny > 0.5 else fy + inner_y)
                room.append((name, r))
            if any(r < EDGE_GAP for _, r in room):
                continue
            # a post under every hole
            corners = []
            for hx, hy in rhole:
                hx, hy = hx + cx, hy + cy
                cell = nearest_cell(hx, hy)
                if cell is None or cell not in USABLE:
                    break
                ccx, ccy = cell_xy(*cell)
                corners.append(Corner((hx, hy), cell, (hx - ccx, hy - ccy)))
            if len(corners) != len(rhole) or len({c.cell for c in corners}) != len(corners):
                continue
            variants, assign = _group_variants([c.v for c in corners])
            worst_room = min((r for _, r in room), default=SOCKET_ROOM_CAP)
            max_v = max(math.hypot(*c.v) for c in corners)
            score = (int(min(worst_room, SOCKET_ROOM_CAP) // ROOM_STEP), -len(variants), -round(max_v, 1),
                     -abs(cx) - abs(cy))
            if best is None or score > best[0]:
                for c, (vi, ang) in zip(corners, assign):
                    c.variant, c.angle = vi, ang
                best = (score, Plan(key, rotation, (cx, cy), (rw, rd), corners,
                                    variants, room, dev["lift"]))
    if best is None:
        raise ValueError(f"{key}: board does not fit the {TRAY_W:g}x{TRAY_D:g} tray grid")
    return best[1]


def plan_text(dev: dict, plan: Plan, name: str) -> str:
    letters = "abcdefgh"
    lines = [
        f"{dev['name']}  ({plan.device}, data: {dev.get('verified', '?')})",
        f"board {dev['width']:g} x {dev['depth']:g} mm, rotated {plan.rotation}°, "
        f"centre at x={plan.origin[0]:+.0f} y={plan.origin[1]:+.0f} mm (tray centre = 0,0)",
        f"lift (floor top -> board underside): {plan.lift:g} mm",
        "",
        "posts to print:",
    ]
    for i, v in enumerate(plan.variants):
        n = sum(1 for c in plan.corners if c.variant == i)
        lines.append(f"  {name}_{letters[i]}.stl  x{n}   (hole offset {v[0]:+.2f}, {v[1]:+.2f} mm)")
    lines += ["", "where they go (floor cell col,row from the front-left; rotate as given):"]
    for c in plan.corners:
        lines.append(f"  hole at ({c.hole[0]:+6.1f}, {c.hole[1]:+6.1f}) -> cell {c.cell[0]},{c.cell[1]}"
                     f"  post {letters[c.variant]} rotated {c.angle}°")
    if plan.socket_room:
        lines += ["", "room in front of each connector (to the tray wall):"]
        for nm, r in plan.socket_room:
            lines.append(f"  {nm:38s} {r:5.1f} mm")
    tallest = max((s["height"] for s in dev.get("socket", [])), default=0.0)
    need = FLOOR + plan.lift + dev["thickness"] + tallest
    lines += ["", f"top of the tallest connector: {need:.1f} mm above the tray bottom"]
    return "\n".join(lines) + "\n"


# --- µcad generation ---------------------------------------------------------
HEADER = """// GENERATED by scripts/build.py from shelves.toml — do not edit by hand.
mod shelves;
"""


def _statement(name, origin, call, export=True) -> str:
    attr = f'#[export("build/{name}.stl")]\n' if export else ""
    return f"\n// {origin}\n{attr}{name} = {call};\n"


def _args(args: list[str]) -> str:
    return "(\n    " + ",\n    ".join(args) + ",\n)"


def mm(v: float) -> str:
    return f"{v:.3f}mm"


def tray_call(shelf: dict) -> str:
    args = [f"width = {shelf.get('width', f'{TRAY_W:g}mm')}",
            f"depth = {shelf.get('depth', f'{TRAY_D:g}mm')}",
            f"height = {shelf.get('height', '30mm')}"]
    if shelf.get("raised_walls"):
        args.append("raised_walls = true")
    return "shelves::tray::Tray" + _args(args)


def render_tray(shelf: dict) -> str:
    return _statement(shelf["name"], "kind=tray", tray_call(shelf))


def render_cable(shelf: dict) -> str:
    if shelf["kind"] == "cable_comb":
        call = f"shelves::cables::CableComb(teeth = {shelf.get('teeth', 4)})"
    else:
        call = f"shelves::cables::CableHook(opening = {shelf.get('opening', '12mm')})"
    return _statement(shelf["name"], f"kind={shelf['kind']}", call)


def post_call(dev: dict, plan: Plan, v) -> str:
    return "shelves::holders::CornerPost" + _args([
        f"vx = {mm(v[0])}", f"vy = {mm(v[1])}", f"lift = {mm(plan.lift)}",
        f"screw_d = {mm(dev['screw_d'])}", f"post_d = {mm(POST_PAD_D)}",
    ])


def render_holder(shelf: dict, dev: dict, plan: Plan, preview: dict | None) -> str:
    name = shelf["name"]
    out = ""
    for i, v in enumerate(plan.variants):
        out += _statement(f"{name}_{'abcdefgh'[i]}", f"kind=holder, device={plan.device}",
                          post_call(dev, plan, v))
    if preview is not None:
        out += _statement(f"preview_{name}", "assembly preview: tray + posts + board",
                          preview_call(preview, dev, plan))
    return out


def preview_call(tray: dict, dev: dict, plan: Plan) -> str:
    """Tray + placed posts + a board slab with connector blocks."""
    parts = [tray_call(tray).replace("\n", " ")]
    for c in plan.corners:
        cx, cy = cell_xy(*c.cell)
        parts.append(f"{post_call(dev, plan, plan.variants[c.variant])}"
                     f".rotate({c.angle}°).translate(x = {mm(cx)}, y = {mm(cy)}, z = {mm(FLOOR)})")
    t = dev["thickness"]
    zb = FLOOR + plan.lift
    rw, rd = plan.size
    ox, oy = plan.origin
    parts.append(f"std::geo3d::Cube(size_x = {mm(rw)}, size_y = {mm(rd)}, size_z = {mm(t)})"
                 f".translate(x = {mm(ox)}, y = {mm(oy)}, z = {mm(zb + t / 2)})")
    w, d = dev["width"], dev["depth"]
    for s in dev.get("socket", []):
        nx, ny = EDGE_NORMAL[s["edge"]]
        depth_in = 8.0   # how far the connector block reaches onto the board
        length = depth_in + s["overhang"]
        along = s["at"]
        if nx:
            ex = (w if nx > 0 else 0) + nx * (s["overhang"] - length / 2)
            centre, sx, sy = (ex, along), length, s["width"]
        else:
            ey = (d if ny > 0 else 0) + ny * (s["overhang"] - length / 2)
            centre, sx, sy = (along, ey), s["width"], length
        c = rot((centre[0] - w / 2, centre[1] - d / 2), plan.rotation)
        if plan.rotation in (90, 270):
            sx, sy = sy, sx
        parts.append(f"std::geo3d::Cube(size_x = {mm(sx)}, size_y = {mm(sy)}, size_z = {mm(s['height'])})"
                     f".translate(x = {mm(c[0] + ox)}, y = {mm(c[1] + oy)}, "
                     f"z = {mm(zb + t + s['height'] / 2)})")
    return "{\n    " + ";\n    ".join(parts) + ";\n}"


def load_toml(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def mucad() -> str:
    exe = shutil.which("mucad")
    if not exe:
        sys.exit("`mucad` not found on PATH. Install with: cargo install mucad@0.6.0")
    return exe


def main() -> int:
    ap = argparse.ArgumentParser(description="Build cluster shelves with µcad.")
    ap.add_argument("names", nargs="*", help="Only build these shelf names.")
    ap.add_argument("--gen-only", action="store_true", help="Generate sources, do not export.")
    ap.add_argument("--preview", action="store_true", help="Also export holder assembly previews.")
    ap.add_argument("--resolution", default=None, help="Export resolution, e.g. 0.05mm or 200%%.")
    args = ap.parse_args()

    BUILD.mkdir(exist_ok=True)
    shelves = all_shelves = load_toml(MANIFEST).get("shelf", [])
    devices = load_toml(DEVICES)
    if not shelves:
        sys.exit("shelves.toml contains no [[shelf]] entries")
    if args.names:
        wanted = set(args.names)
        shelves = [s for s in shelves if s["name"] in wanted]
        missing = wanted - {s["name"] for s in shelves}
        if missing:
            sys.exit(f"unknown shelf name(s): {', '.join(sorted(missing))}")

    # 1. Plan holders and generate the root source.
    src = HEADER
    for shelf in shelves:
        name, kind = shelf["name"], shelf["kind"]
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", name):
            sys.exit(f"{name!r}: shelf names must be lowercase identifiers")
        if kind not in KINDS:
            sys.exit(f"{name}: unknown kind {kind!r}")
        if kind == "tray":
            src += render_tray(shelf)
        elif kind == "holder":
            key = shelf.get("device")
            if key not in devices:
                sys.exit(f"{name}: unknown device {key!r} (see devices.toml)")
            plan = plan_holder(key, devices[key])
            text = plan_text(devices[key], plan, name)
            (BUILD / f"{name}_plan.txt").write_text(text, encoding="utf-8")
            print(f"plan {name}: {len(plan.variants)} post variant(s), "
                  f"rotated {plan.rotation}°, see build/{name}_plan.txt")
            tray = next((t for t in all_shelves if t["name"] == shelf.get("tray", "tray_std")), {})
            src += render_holder(shelf, devices[key], plan, tray if args.preview else None)
        else:
            src += render_cable(shelf)
    ROOT_SRC.write_text(src, encoding="utf-8")
    print(f"gen  {ROOT_SRC.relative_to(ROOT)}")

    if args.gen_only:
        return 0

    # 2. Export every part in one go (each statement carries its #[export]).
    cmd = [mucad(), "export"]
    if args.resolution:
        cmd += ["-r", args.resolution]
    cmd.append(ROOT_SRC.name)
    res = subprocess.run(cmd, cwd=ROOT)
    if res.returncode != 0:
        print("\nexport failed.", file=sys.stderr)
        return 1
    print(f"\nOK — exported to {BUILD.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
