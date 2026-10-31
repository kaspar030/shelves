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

// Vertical shift of a wall's hex field. Centred (0) by default; `raised`
// moves it up so the lowest full hexes sit `bottom` above the panel's lower
// edge and the staggered column is cut open by the rim (half hexagons).
fn field_shift(raised: Bool, height: Length, rows: Integer, af: Length, wall: Length, bottom: Length) {
    rp = af + wall;   // row_pitch (fns can't call user fns in µcad 0.6)
    lowest = -(rows - 1) / 2 * rp - rp / 4 - af / 2;
    if raised { -height / 2 + bottom - lowest } else { 0mm }
}

// A perforated rectangular panel in the XY plane, extruded `thick` in +Z,
// centred on the origin. The hex columns are fitted into `field_w` (<= width,
// e.g. to keep them clear of corner posts) with `margin` as extra border, and
// the field is moved up by `shift`.
part HexPanel(
    width: Length,
    height: Length,
    thick: Length,
    margin: Length,
    af: Length,
    wall: Length,
    field_w: Length,
    shift = 0mm,
) {
    cols = fit_cols(span = field_w, margin = margin, af = af, wall = wall);
    rows = fit_rows(span = height, margin = margin, af = af, wall = wall);
    // Extrude is centred on the panel plane (z = -thick/2 .. +thick/2) so that
    // after rotation the wall thickness straddles its placement plane.
    (Rect(width = width, height = height)
        - HexField(cols = cols, rows = rows, af = af, wall = wall).translate(y = shift))
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
    // wall hex layout: centred, or raised (full hexes low, half hexes open
    // at the rim) — useful when the wall is too low for a staggered row.
    raised_walls = false,
    wall_bottom = 1.5mm,       // web under the lowest full wall hexes (raised)
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
    ).translate(z = floor / 2);

    // Wall hex fields stay clear of the corner posts.
    wall_rows = fit_rows(span = wall_h, margin = margin, af = af, wall = hexwall);
    shift = field_shift(raised = raised_walls, height = wall_h, rows = wall_rows,
                        af = af, wall = hexwall, bottom = wall_bottom);

    // ---- Walls: four perforated panels standing on the floor ---------------
    front_back = HexPanel(
        width = width, height = wall_h, thick = wall,
        margin = margin, af = af, wall = hexwall,
        field_w = width - 2 * post + 2 * margin, shift = shift,
    ).rotate(x = 90°);
    fb = front_back
        .translate(z = floor + wall_h / 2)
        .translate(y = [-(depth / 2 - wall / 2), depth / 2 - wall / 2]);

    left_right = HexPanel(
        width = depth, height = wall_h, thick = wall,
        margin = margin, af = af, wall = hexwall,
        field_w = depth - 2 * post + 2 * margin, shift = shift,
    ).rotate(x = 90°).rotate(z = 90°);
    lr = left_right
        .translate(z = floor + wall_h / 2)
        .translate(x = [-(width / 2 - wall / 2), width / 2 - wall / 2]);

    // ---- Solid corner posts (full height) ----------------------------------
    // Each post is flush with the tray's outer corner and runs from z=0 to the
    // rim. The peg stands on top; the socket is bored into the base.
    posts = Cube(size_x = post, size_y = post, size_z = height)
        .translate(z = height / 2)
        .translate(x = [-px, px], y = [-py, py]);

    // ---- Stacking sockets: bored UP into the post bases ---------------------
    sockets = Cylinder(diameter = SOCKET_D, height = SOCKET_DEPTH)
        .translate(z = SOCKET_DEPTH / 2)
        .translate(x = [-px, px], y = [-py, py]);

    // Assemble the box, then carve the stacking sockets.
    (floor_panel | fb | lr | posts) - sockets;

    // ---- Stacking pegs on top of the posts ---------------------------------
    Cylinder(diameter = PEG_D, height = PEG_H)
        .translate(z = height + PEG_H / 2)
        .translate(x = [-px, px], y = [-py, py]);
}
