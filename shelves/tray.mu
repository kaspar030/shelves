// Copyright © 2026
// SPDX-License-Identifier: MIT
//
// The cluster-shelf tray: a single, stackable, hex-grid box.
//
// Floor AND all four walls are perforated with the shared honeycomb
// (shelves/hexgrid) for airflow + visibility, and as the universal mounting grid:
// boards clip into the FLOOR via holders (shelves/holders), and cable holders /
// accessories clip into any wall cell.
//
// Stacking: 4 solid corner posts run the full height. Each post carries a PEG
// on top and a SOCKET in its base; the peg of one tray drops into the socket of
// the tray above, self-aligning the column. Posts are solid, so the pegs always
// stand on material (never floating over the perforation).
//
// Cables: the wall hexes are large enough to pass RJ45 / USB plugs, so cables
// leave through the walls; they are dressed with wall-mounted cable holders.
//
// Coordinate convention (shared library-wide):
//   * X,Y centred on the footprint.
//   * Z=0 is the bottom face of the tray; it grows upward in +Z.

use std::geo2d::*;
use std::geo3d::*;
use std::ops::*;

use super::params::*;
use super::hexgrid::*;

// Wall hex layouts (`wall_align`), for a wall panel `height` tall standing on
// a `floor` thick floor:
//   "center"     the fitted rows, centred on the wall.
//   "raised"     lowest full hexes `bottom` above the floor; the staggered
//                column is cut open by the rim (half hexagons at the top).
//   "lowered"    highest full hexes `bottom` below the rim; the staggered
//                column is cut by the floor (half hexagons at the bottom).
//   "continuous" the honeycomb is anchored to the tray bottom: even-column
//                hexes end 0.05mm above each multiple of the row pitch
//                (16.4mm). With tray heights that are multiples of 16.4mm
//                they open cleanly at the rim, the stacked tray's floor
//                (plus a 0.45mm strip fused onto it) forms the web, and the
//                pattern runs on through the whole stack in any order.
// (fns can't call user fns in µcad 0.6, so the pitches are spelled out.)
fn field_rows(align: String, fitted: Integer, height: Length, floor: Length, af: Length, wall: Length) {
    rp = af + wall;
    z0 = 0.05mm - af / 2;
    if align == "continuous" { std::math::int((floor + height + af / 2 - z0) / rp) + 2 } else { fitted }
}

fn field_shift(align: String, height: Length, rows: Integer, floor: Length, af: Length, wall: Length, bottom: Length) {
    rp = af + wall;
    lowest = -(rows - 1) / 2 * rp - rp / 4 - af / 2;
    highest = (rows - 1) / 2 * rp + rp / 4 + af / 2;
    z0 = 0.05mm - af / 2;   // continuous: centre of the first even hex
    if align == "raised" { -height / 2 + bottom - lowest }
    else if align == "lowered" { height / 2 - bottom - highest }
    else if align == "continuous" { z0 - floor - height / 2 + (rows - 1) / 2 * rp + rp / 4 }
    else { 0mm }
}

fn pick_rows(fitted: Integer, rows: Integer) {
    if rows > 0 { rows } else { fitted }
}

// A perforated rectangular panel in the XY plane, `width` centred on x = 0
// and `height` from y = 0 up (anchored at its lower edge, so callers place
// that edge exactly), extruded `thick` centred on z = 0. The hex columns are
// fitted into `field_w` (<= width, e.g. to keep them clear of corner posts)
// with `margin` as extra border; the field is centred on the panel and moved
// up by `shift`.
part HexPanel(
    width: Length,
    height: Length,
    thick: Length,
    margin: Length,
    af: Length,
    wall: Length,
    field_w: Length,
    shift = 0mm,
    rows = 0,          // 0 = as many as fit
) {
    cols = fit_cols(span = field_w, margin = margin, af = af, wall = wall);
    n_rows = pick_rows(fitted = fit_rows(span = height, margin = margin, af = af, wall = wall), rows = rows);
    (Rect(width = width, height = height, x = -width / 2, y = 0mm)
        - HexField(cols = cols, rows = n_rows, af = af, wall = wall).translate(y = height / 2 + shift))
        .extrude(height = thick)
        .translate(z = -thick / 2);
}

pub part Tray(
    // outer footprint (defaults are literals; see shelves/params.mu)
    width = 160mm,             // = params::FOOTPRINT_W
    depth = 100mm,             // = params::FOOTPRINT_D
    height = 30mm,             // total wall height above the floor
    // construction
    wall = 2.0mm,              // perforated-panel thickness (thinner = airier)
    floor = 2.0mm,             // = params::FLOOR
    // hex grid
    af = 14.0mm,               // = params::HEX_AF
    hexwall = 2.4mm,           // web between holes (thinner = more open)
    margin = 4.0mm,            // solid border per face (smaller = airier)
    // stacking corner posts
    post = 10.0mm,             // corner-post footprint (square)
    // wall hex layout: "center" | "raised" | "lowered" | "continuous"
    // (see field_shift above)
    wall_align = "center",
    wall_bottom = 1.5mm,       // web below/above the full hexes (raised/lowered)
) {
    wall_h = height - floor;
    // Peg/socket centres sit on the corner posts (post centred in each corner).
    peg_inset = post / 2;
    px = width / 2 - peg_inset;
    py = depth / 2 - peg_inset;

    // ---- Floor: a perforated panel sitting at z = 0 .. floor ----------------
    floor_panel = HexPanel(
        width = width, height = depth, thick = floor,
        margin = margin, af = af, wall = hexwall, field_w = width,
    ).translate(y = -depth / 2, z = floor / 2);

    // Joints overlap instead of touching: this geometry kernel leaves
    // non-manifold edges where faces only coincide (and 90° rotations add
    // float noise, so "coincide" is never exact). So the walls sit `inset`
    // inside the outer edge, reach `sink` down into the floor, end inside the
    // corner posts, and are built `over` too tall and cut with the whole box
    // to `height`. Hexes cut down to the panel's lower edge end inside the
    // floor. The hex fields stay clear of the corner posts.
    inset = 0.3mm;
    sink = 0.5mm;
    over = 1mm;
    panel_h = sink + wall_h + over;
    wall_rows = field_rows(align = wall_align,
                           fitted = fit_rows(span = wall_h, margin = margin, af = af, wall = hexwall),
                           height = wall_h, floor = floor, af = af, wall = hexwall);
    // field_shift is relative to the wall's centre; the panel's centre is
    // (over - sink) / 2 higher
    shift = field_shift(align = wall_align, height = wall_h, rows = wall_rows, floor = floor,
                        af = af, wall = hexwall, bottom = wall_bottom) - (over - sink) / 2;

    // ---- Walls: four perforated panels standing in the floor ---------------
    front_back = HexPanel(
        width = width - 2 * inset - 2mm, height = panel_h, thick = wall,
        margin = margin, af = af, wall = hexwall,
        field_w = width - 2 * post + 2 * margin, shift = shift, rows = wall_rows,
    ).rotate(x = 90°);
    fb = front_back
        .translate(z = floor - sink)
        .translate(y = [-(depth / 2 - inset - wall / 2), depth / 2 - inset - wall / 2]);

    left_right = HexPanel(
        width = depth - 2 * inset - 2mm, height = panel_h, thick = wall,
        margin = margin, af = af, wall = hexwall,
        field_w = depth - 2 * post + 2 * margin, shift = shift, rows = wall_rows,
    ).rotate(x = 90°).rotate(z = 90°);
    lr = left_right
        .translate(z = floor - sink)
        .translate(x = [-(width / 2 - inset - wall / 2), width / 2 - inset - wall / 2]);

    // ---- Solid corner posts (full height) ----------------------------------
    // Each post is flush with the tray's outer corner and runs from z=0 to the
    // rim. The peg stands on top; the socket is bored into the base.
    // (extruded from exactly z = 0 and cut to height with the rest below)
    posts = Rect(width = post, height = post)
        .extrude(height = 2 * height)
        .translate(x = [-px, px], y = [-py, py]);

    // ---- Stacking sockets: bored UP into the post bases ---------------------
    sockets = Cylinder(diameter = SOCKET_D, height = SOCKET_DEPTH)
        .translate(z = SOCKET_DEPTH / 2)
        .translate(x = [-px, px], y = [-py, py]);

    // Assemble the box (the floor leaves room for the posts, so their faces
    // meet instead of overlapping), cut it to height with a box centred on
    // z = 0 (its top is exactly `height`: 2h - h is exact), carve the sockets.
    (((floor_panel - posts) | fb | lr | posts)
        & Cube(size_x = width + 2mm, size_y = depth + 2mm, size_z = 2 * height))
        - sockets;

    // ---- Stacking pegs on top of the posts ---------------------------------
    // (starts 0.5mm inside the post, so it fuses whatever the float rounding)
    Cylinder(diameter = PEG_D, height = PEG_H + 0.5mm)
        .translate(z = height - 0.5mm + (PEG_H + 0.5mm) / 2)
        .translate(x = [-px, px], y = [-py, py]);
}
