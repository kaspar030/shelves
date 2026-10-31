// Copyright © 2026
// SPDX-License-Identifier: MIT
//
// Board holders: four separate CORNER POSTS per board instead of a baseplate.
// Each post plugs into one hex cell of a tray floor and carries one board
// mounting hole on top; the board is screwed down with self-tapping screws.
//
//   * The post body is a prism: the 2D hull of a hex shoulder (centred on the
//     plug, a bit larger than the hole, so it rests on the floor web) and a
//     round pad at the board hole, offset (vx, vy) from the plug centre.
//   * Because a board hole rarely sits exactly over a cell centre, the offset
//     is chosen per board by scripts/build.py, which also tells you which
//     cells to use. Posts at diagonally opposite corners are the same part
//     rotated 180°, and the hex plug fits the cell in every 60° rotation.
//
// Coordinate convention: z = 0 is the top face of the tray floor; the body
// rises to z = lift (the underside of the board), the plug hangs below.
//
// Print orientation: upside down — the flat top (pad) on the bed, plug
// pointing up. No overhangs except the plug's small barb face.

use std::geo2d::*;
use std::geo3d::*;
use std::ops::*;

use super::hexgrid::*;
use super::connector::*;

const SQRT3 = 1.7320508075688772;

// (An `if` in a part body yields a model, so value choices live in fns.)
fn min_len(a: Length, b: Length) {
    if a < b { a } else { b }
}

pub part CornerPost(
    vx: Length,           // board-hole offset from the plug centre (X)
    vy: Length,           // board-hole offset from the plug centre (Y)
    lift: Length,         // floor top -> board underside
    post_d = 6.0mm,       // pad diameter under the board hole
    screw_d = 2.5mm,      // self-tapping pilot hole
    screw_depth = 6.0mm,  // pilot hole depth (capped by the post height)
    shoulder = 1.5mm,     // how far the shoulder overlaps the hole rim
    af = 14.0mm,          // = HEX_AF
    surface_t = 2.0mm,    // = FLOOR
) {
    r_shoulder = (af + 2 * shoulder) / SQRT3;
    depth = min_len(a = screw_depth, b = lift - 1mm);

    {
        Hex(radius = r_shoulder);
        Circle(radius = post_d / 2, center = (x = vx, y = vy));
    }.hull().extrude(height = lift)
      - Cylinder(diameter = screw_d, height = depth + 1mm)
        .translate(x = vx, y = vy, z = lift - depth + (depth + 1mm) / 2);

    Plug(af = af, surface_t = surface_t);
}
