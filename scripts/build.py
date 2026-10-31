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
ROOM_STEP = 10.0          # room differences below this don't beat fewer post variants
EDGE_GAP = 1.0            # minimum gap board <-> tray walls / corner posts

KINDS = {"tray", "holder", "cable_comb", "cable_clip"}


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
CLUSTER_D = 25.0          # holes closer than this share one (two-pad) post
POST_GAP = 0.5            # minimum gap between two post bodies


def rot(v, deg):
    a = math.radians(deg)
    return (v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a))


def convex_hull(pts):
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return pts
    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and ((h[-1][0] - h[-2][0]) * (p[1] - h[-2][1])
                                   - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0])) <= 0:
                h.pop()
            h.append(p)
        return h
    lower, upper = half(pts), half(reversed(pts))
    return lower[:-1] + upper[:-1]


def polys_overlap(a, b, gap):
    """Separating-axis test for convex polygons, `gap` counts as overlap."""
    for poly in (a, b):
        for i in range(len(poly)):
            ex, ey = poly[(i + 1) % len(poly)][0] - poly[i][0], poly[(i + 1) % len(poly)][1] - poly[i][1]
            n = math.hypot(ex, ey) or 1.0
            ax, ay = -ey / n, ex / n
            pa = [x * ax + y * ay for x, y in a]
            pb = [x * ax + y * ay for x, y in b]
            if max(pa) + gap <= min(pb) or max(pb) + gap <= min(pa):
                return False
    return True


@dataclass
class Post:
    board: tuple[int, ...]           # indexes of the board(s) it carries
    cell: tuple[int, int]
    holes: list[tuple[float, float]]  # hole centres in tray coordinates
    v: list[tuple[float, float]]     # hole offsets from the cell centre
    variant: int = 0
    angle: int = 0                   # post rotation (deg) relative to its variant

    def footprint(self):
        cx, cy = cell_xy(*self.cell)
        pts = [(cx + SHOULDER_R * math.cos(math.radians(a)), cy + SHOULDER_R * math.sin(math.radians(a)))
               for a in range(0, 360, 60)]
        for hx, hy in self.holes:
            pts += [(hx + POST_PAD_D / 2 * math.cos(math.radians(a)),
                     hy + POST_PAD_D / 2 * math.sin(math.radians(a))) for a in range(0, 360, 30)]
        return convex_hull(pts)


@dataclass
class Board:
    rotation: int                    # board rotation on the tray (deg)
    origin: tuple[float, float]      # board centre in tray coordinates
    size: tuple[float, float]        # rotated board size
    socket_room: list[tuple[str, float]]


@dataclass
class Layout:
    device: str
    lift: float
    boards: list[Board]
    posts: list[Post]
    variants: list[list[tuple[float, float]]]   # pad offsets per post variant


def _same_offsets(a, b, tol=0.25):
    if len(a) != len(b):
        return False
    if len(a) == 1:
        return math.dist(a[0], b[0]) < tol
    return ((math.dist(a[0], b[0]) < tol and math.dist(a[1], b[1]) < tol)
            or (math.dist(a[0], b[1]) < tol and math.dist(a[1], b[0]) < tol))


def group_variants(posts: list[Post]):
    """Posts are interchangeable if their pad offsets differ by a 60° rotation
    (the hex plug fits the cell in all six orientations)."""
    variants: list[list[tuple[float, float]]] = []
    for post in posts:
        for i, c in enumerate(variants):
            hit = next((k * 60 for k in range(6)
                        if _same_offsets([rot(v, k * 60) for v in c], post.v)), None)
            if hit is not None:
                post.variant, post.angle = i, hit
                break
        else:
            variants.append(list(post.v))
            post.variant, post.angle = len(variants) - 1, 0
    return variants


def hole_clusters(holes):
    """Group holes that are too close for separate posts (max. two per post)."""
    clusters, used = [], set()
    for i, h in enumerate(holes):
        if i in used:
            continue
        mate = next((j for j in range(i + 1, len(holes))
                     if j not in used and math.dist(h, holes[j]) < CLUSTER_D), None)
        clusters.append([i] if mate is None else [i, mate])
        used.update(clusters[-1])
    return clusters


def socket_fronts(dev: dict, rotation: int):
    w, d = dev["width"], dev["depth"]
    out = []
    for s in dev.get("socket", []):
        nx, ny = EDGE_NORMAL[s["edge"]]
        along = s["at"]
        edge_pt = {"left": (0, along), "right": (w, along),
                   "bottom": (along, 0), "top": (along, d)}[s["edge"]]
        front = (edge_pt[0] + nx * s["overhang"], edge_pt[1] + ny * s["overhang"])
        out.append((s["name"], rot((front[0] - w / 2, front[1] - d / 2), rotation), rot((nx, ny), rotation)))
    return out


def room_ahead(front, normal, region, others):
    """Free distance from a connector front to the region border, or to the
    first other board in its way."""
    (fx, fy), (nx, ny) = front, normal
    x0, x1, y0, y1 = region
    r = (x1 - fx if nx > 0.5 else fx - x0 if nx < -0.5 else y1 - fy if ny > 0.5 else fy - y0)
    for bx0, bx1, by0, by1 in others:
        if bx0 <= fx <= bx1 and by0 <= fy <= by1:
            return -1.0       # the connector sticks into the other board
        if abs(nx) > 0.5 and by0 < fy < by1:
            d = bx0 - fx if nx > 0 else fx - bx1
        elif abs(ny) > 0.5 and bx0 < fx < bx1:
            d = by0 - fy if ny > 0 else fy - by1
        else:
            continue
        if d >= 0:
            r = min(r, d)
    return r


INNER = (-(TRAY_W / 2 - WALL), TRAY_W / 2 - WALL, -(TRAY_D / 2 - WALL), TRAY_D / 2 - WALL)


def plan_group(dev: dict, group, region=INNER, step: float = 1.0):
    """Best position of a rigid group of boards inside `region`.

    `group` lists the boards as (dx, dy, rotation): centre offset from the
    group centre and rotation. Holes closer than CLUSTER_D share a post, also
    across neighbouring boards. Returns (score, boards, posts) or None."""
    w, d = dev["width"], dev["depth"]
    holes, owner, socks, rects = [], [], [], []
    for k, (dx, dy, r) in enumerate(group):
        rw, rd = (w, d) if r in (0, 180) else (d, w)
        rects.append((dx - rw / 2, dx + rw / 2, dy - rd / 2, dy + rd / 2))
        for h in dev["holes"]:
            hx, hy = rot((h[0] - w / 2, h[1] - d / 2), r)
            holes.append((hx + dx, hy + dy))
            owner.append(k)
        for nm, (fx, fy), n in socket_fronts(dev, r):
            socks.append((k, nm, (fx + dx, fy + dy), n))
    clusters = hole_clusters(holes)
    gx0, gx1 = min(r[0] for r in rects), max(r[1] for r in rects)
    gy0, gy1 = min(r[2] for r in rects), max(r[3] for r in rects)
    rx0, rx1, ry0, ry1 = region
    lo_x, hi_x = rx0 + EDGE_GAP - gx0, rx1 - EDGE_GAP - gx1
    lo_y, hi_y = ry0 + EDGE_GAP - gy0, ry1 - EDGE_GAP - gy1
    if lo_x > hi_x or lo_y > hi_y:
        return None

    # Candidate group centres: a grid, plus the positions that put the hole
    # pattern's centre on a point of symmetry of the hex grid (a cell centre
    # or the midpoint of two cells). For a symmetric hole pattern those make
    # opposite posts identical (180° apart).
    hc = (sum(h[0] for h in holes) / len(holes), sum(h[1] for h in holes) / len(holes))
    n_x, n_y = int((hi_x - lo_x) / step), int((hi_y - lo_y) / step)
    centres = [(lo_x + i * step, lo_y + j * step) for i in range(n_x + 1) for j in range(n_y + 1)]
    cells = [cell_xy(*c) for c in USABLE]
    centres += sorted({(round((a[0] + b[0]) / 2 - hc[0], 4), round((a[1] + b[1]) / 2 - hc[1], 4))
                       for a in cells for b in cells})
    mid = ((rx0 + rx1) / 2, (ry0 + ry1) / 2)
    px, py = TRAY_W / 2 - POST - EDGE_GAP, TRAY_D / 2 - POST - EDGE_GAP
    best = None
    for cx, cy in centres:
        if not (lo_x - 1e-6 <= cx <= hi_x + 1e-6 and lo_y - 1e-6 <= cy <= hi_y + 1e-6):
            continue
        placed = [(x0 + cx, x1 + cx, y0 + cy, y1 + cy) for x0, x1, y0, y1 in rects]
        if any((x0 < -px or x1 > px) and (y0 < -py or y1 > py) for x0, x1, y0, y1 in placed):
            continue      # hits a tray corner post
        room = [(k, nm, room_ahead((fx + cx, fy + cy), n, region, placed[:k] + placed[k + 1:]))
                for k, nm, (fx, fy), n in socks]
        if any(r < EDGE_GAP for _, _, r in room):
            continue
        # leximin: compare the most cramped connector first, then the next
        bucket = tuple(sorted(int(min(r, SOCKET_ROOM_CAP) // ROOM_STEP) for _, _, r in room))
        if best is not None and bucket < best[0][0]:
            continue
        posts = []
        for cl in clusters:
            hs = [(holes[i][0] + cx, holes[i][1] + cy) for i in cl]
            cell = nearest_cell(sum(h[0] for h in hs) / len(hs), sum(h[1] for h in hs) / len(hs))
            if cell is None or cell not in USABLE:
                break
            ccx, ccy = cell_xy(*cell)
            posts.append(Post(tuple(sorted({owner[i] for i in cl})), cell, hs, [(h[0] - ccx, h[1] - ccy) for h in hs]))
        if len(posts) != len(clusters) or len({p.cell for p in posts}) != len(posts):
            continue
        fps = [p.footprint() for p in posts]
        if any(polys_overlap(a, b, POST_GAP) for i, a in enumerate(fps) for b in fps[i + 1:]):
            continue
        n_var = len(group_variants(posts))
        max_v = max(math.hypot(*v) for p in posts for v in p.v)
        score = (bucket, -n_var, -round(max_v, 1), -abs(cx - mid[0]) - abs(cy - mid[1]))
        if best is None or score > best[0]:
            boards = [Board(r, (dx + cx, dy + cy), ((w, d) if r in (0, 180) else (d, w)),
                            [(nm, rr) for k2, nm, rr in room if k2 == k])
                      for k, (dx, dy, r) in enumerate(group)]
            best = (score, boards, posts)
    return best


def plan_holder(key: str, dev: dict, count: int = 1) -> Layout:
    """Lay out `count` boards in one tray as a row along X or Y, all turned
    the same way or alternating by 180°, with the gap between them varied;
    keep the layout with the most room in front of the connectors."""
    w, d = dev["width"], dev["depth"]
    groups = []
    for r in (0, 90, 180, 270):
        if count == 1:
            groups.append([(0.0, 0.0, r)])
            continue
        for rots in ([r] * count, [r if i % 2 == 0 else (r + 180) % 360 for i in range(count)]):
            for axis in (0, 1):
                along = [(w if rr in (0, 180) else d) if axis == 0 else (d if rr in (0, 180) else w)
                         for rr in rots]
                for gap in range(0, 42, 2):
                    total = sum(along) + gap * (count - 1)
                    if total > (TRAY_W if axis == 0 else TRAY_D) - 2 * WALL - 2 * EDGE_GAP:
                        break
                    pos, cur = [], -total / 2
                    for a in along:
                        pos.append(cur + a / 2)
                        cur += a + gap
                    # boards centred on the row, or shifted across it so their
                    # hole patterns line up (lets neighbours share posts)
                    for align in (False, True):
                        if align and len(set(rots)) == 1:
                            continue
                        perp = []
                        for rr in rots:
                            hc = [rot((h[0] - w / 2, h[1] - d / 2), rr) for h in dev["holes"]]
                            c = sum(h[1 - axis] for h in hc) / len(hc)
                            perp.append(-c if align else 0.0)
                        groups.append([(p, q, rr) if axis == 0 else (q, p, rr)
                                       for p, q, rr in zip(pos, perp, rots)])
    best = None
    for g in groups:
        res = plan_group(dev, g, step=1.0 if count == 1 else 2.0)
        if res is not None and (best is None or res[0] > best[0]):
            best = res
    if best is None:
        raise ValueError(f"{key}: {count} board(s) don't fit the {TRAY_W:g}x{TRAY_D:g} tray grid")
    _, boards, posts = best
    return Layout(key, dev["lift"], boards, posts, group_variants(posts))


def plan_text(dev: dict, lay: Layout, name: str) -> str:
    letters = "abcdefghijklmnop"
    lines = [f"{dev['name']}  ({lay.device}, data: {dev.get('verified', '?')})",
             f"{len(lay.boards)} board(s) of {dev['width']:g} x {dev['depth']:g} mm; "
             f"lift (floor top -> board underside): {lay.lift:g} mm", ""]
    for k, b in enumerate(lay.boards):
        lines.append(f"board {k + 1}: rotated {b.rotation}°, centre at x={b.origin[0]:+.0f} "
                     f"y={b.origin[1]:+.0f} mm (tray centre = 0,0)")
    lines += ["", "posts to print:"]
    for i, v in enumerate(lay.variants):
        n = sum(1 for p in lay.posts if p.variant == i)
        offs = ", ".join(f"({o[0]:+.2f}, {o[1]:+.2f})" for o in v)
        lines.append(f"  {name}_{letters[i]}.stl  x{n}   (hole offset{'s' if len(v) > 1 else ''} {offs} mm)")
    lines += ["", "where they go (floor cell col,row from the front-left; rotate as given):"]
    for p in lay.posts:
        hs = " + ".join(f"({h[0]:+6.1f}, {h[1]:+6.1f})" for h in p.holes)
        who = "+".join(str(b + 1) for b in p.board)
        lines.append(f"  board {who}: hole {hs} -> cell {p.cell[0]},{p.cell[1]}"
                     f"  post {letters[p.variant]} rotated {p.angle}°")
    lines += ["", "room in front of each connector (to the wall or the next board):"]
    for k, b in enumerate(lay.boards):
        for nm, r in b.socket_room:
            lines.append(f"  board {k + 1}: {nm:38s} {r:5.1f} mm")
    tallest = max((s["height"] for s in dev.get("socket", [])), default=0.0)
    need = FLOOR + lay.lift + dev["thickness"] + tallest
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
    if "wall_align" in shelf:
        args.append(f'wall_align = "{shelf["wall_align"]}"')
    return "shelves::tray::Tray" + _args(args)


def render_tray(shelf: dict) -> str:
    return _statement(shelf["name"], "kind=tray", tray_call(shelf))


def render_cable(shelf: dict) -> str:
    if shelf["kind"] == "cable_comb":
        call = f"shelves::cables::CableComb(teeth = {shelf.get('teeth', 4)})"
    else:
        call = f"shelves::cables::CableClip(opening = {shelf.get('opening', '12mm')})"
    return _statement(shelf["name"], f"kind={shelf['kind']}", call)


def post_call(dev: dict, lay: Layout, v) -> str:
    v1, v2 = v[0], v[-1]
    return "shelves::holders::CornerPost" + _args([
        f"vx = {mm(v1[0])}", f"vy = {mm(v1[1])}", f"vx2 = {mm(v2[0])}", f"vy2 = {mm(v2[1])}",
        f"lift = {mm(lay.lift)}", f"screw_d = {mm(dev['screw_d'])}", f"post_d = {mm(POST_PAD_D)}",
    ])


def render_holder(shelf: dict, dev: dict, lay: Layout, preview: dict | None) -> str:
    name = shelf["name"]
    out = ""
    for i, v in enumerate(lay.variants):
        out += _statement(f"{name}_{'abcdefghijklmnop'[i]}", f"kind=holder, device={lay.device}",
                          post_call(dev, lay, v))
    if preview is not None:
        out += _statement(f"preview_{name}", "assembly preview: tray + posts + boards",
                          preview_call(preview, dev, lay))
    return out


def preview_call(tray: dict, dev: dict, lay: Layout) -> str:
    """Tray + placed posts + board slabs with connector blocks."""
    parts = [tray_call(tray).replace("\n", " ")]
    for p in lay.posts:
        cx, cy = cell_xy(*p.cell)
        parts.append(f"{post_call(dev, lay, lay.variants[p.variant])}"
                     f".rotate({p.angle}°).translate(x = {mm(cx)}, y = {mm(cy)}, z = {mm(FLOOR)})")
    t = dev["thickness"]
    zb = FLOOR + lay.lift
    w, d = dev["width"], dev["depth"]
    for b in lay.boards:
        rw, rd = b.size
        ox, oy = b.origin
        parts.append(f"std::geo3d::Cube(size_x = {mm(rw)}, size_y = {mm(rd)}, size_z = {mm(t)})"
                     f".translate(x = {mm(ox)}, y = {mm(oy)}, z = {mm(zb + t / 2)})")
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
            c = rot((centre[0] - w / 2, centre[1] - d / 2), b.rotation)
            if b.rotation in (90, 270):
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
            lay = plan_holder(key, devices[key], int(shelf.get("count", 1)))
            text = plan_text(devices[key], lay, name)
            (BUILD / f"{name}_plan.txt").write_text(text, encoding="utf-8")
            worst = min((r for b in lay.boards for _, r in b.socket_room), default=0)
            print(f"plan {name}: {len(lay.boards)} board(s), {len(lay.posts)} posts in "
                  f"{len(lay.variants)} variant(s), min connector room {worst:.0f}mm")
            tray = next((t for t in all_shelves if t["name"] == shelf.get("tray", "tray_std")), {})
            src += render_holder(shelf, devices[key], lay, tray if args.preview else None)
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
