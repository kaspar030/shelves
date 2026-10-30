// Copyright © 2026
// SPDX-License-Identifier: MIT
//
// Cable-management accessories that clip into the hex grid (typically a WALL,
// but the floor works too). All ride on the same PlugPair interface as the
// board holders, so they go into any two vertically-adjacent hex cells.
//
// WHERE THE CABLES GO (the system answer):
//   * Each tray's BACK (-Y) wall has a cable-trunk NOTCH (see shelves/tray) — the
//     main bundle runs vertically up the back of the stack through the aligned
//     notches.
//   * Individual cables branch off the trunk and are dressed along the walls
//     with `CableComb` (several cables side by side) or `CableHook` (a loop /
//     bundle). Both clip into the hex wall wherever you want them.
//
// Print orientation: baseplate flat on the bed (z = 0 .. base_t), plugs hang
// below (−Z) to push into the wall; the comb/hook faces +Y (away from wall).

use std::geo2d::*;
use std::geo3d::*;
use std::ops::*;

use super::params::*;
use super::hexgrid::*;
use super::connector::*;

// A baseplate sized to two vertically-adjacent cells, with a PlugPair under it.
part CableBase(
    plate_w: Length,
    base_t: Length,
    af: Length,
    wall: Length,
    surface_t: Length,
) {
    rp = row_pitch(af = af, wall = wall);
    Cube(size_x = plate_w, size_y = rp + af, size_z = base_t)
        .translate(z = base_t / 2);
    PlugPair(af = af, wall = wall, surface_t = surface_t);
}

// Cable comb: a row of `teeth` open-topped slots that cables snap down into.
// Cables sit in the slots; the slight overhang at the slot mouth retains them.
pub part CableComb(
    teeth = 4,
    slot_w = 4mm,          // cable diameter the slot accepts
    tooth_w = 2.4mm,       // wall between slots
    depth = 8mm,           // how far the comb stands off the wall (+Y)
    base_t = 2.4mm,
    af = 14.0mm,
    wall = 2.4mm,
    surface_t = 2.4mm,
) {
    pitch = slot_w + tooth_w;
    comb_w = teeth * pitch + tooth_w;
    height = slot_w + 4mm;

    CableBase(plate_w = comb_w, base_t = base_t, af = af, wall = wall, surface_t = surface_t);

    // A solid block standing off the wall, with `teeth` slots cut from the top.
    block = Cube(size_x = comb_w, size_y = depth, size_z = height)
        .translate(y = depth / 2, z = base_t + height / 2);

    // Slots: open-topped channels (cut from the top down), one per tooth gap.
    slot_xs = ([0 .. teeth - 1] - (teeth - 1) / 2) * pitch;
    slots = Cube(size_x = slot_w, size_y = depth + 2mm, size_z = slot_w)
        .translate(y = depth / 2, z = base_t + height - slot_w / 2 + 1mm)
        .translate(x = slot_xs);

    block - slots;
}

// Cable hook: a J that a bundle drops into and is retained by a return lip.
pub part CableHook(
    opening = 12mm,        // clear opening for the bundle
    reach = 16mm,          // how far the hook stands off the wall (+Y)
    bar = 3mm,             // material thickness of the hook
    base_t = 2.4mm,
    af = 14.0mm,
    wall = 2.4mm,
    surface_t = 2.4mm,
) {
    CableBase(plate_w = af, base_t = base_t, af = af, wall = wall, surface_t = surface_t);

    // upright back, top arm reaching out, and a short return lip pointing down.
    h = opening + 2 * bar;
    back = Cube(size_x = af, size_y = bar, size_z = h)
        .translate(y = bar / 2, z = base_t + h / 2);
    top = Cube(size_x = af, size_y = reach, size_z = bar)
        .translate(y = reach / 2, z = base_t + h - bar / 2);
    lip = Cube(size_x = af, size_y = bar, size_z = bar * 2)
        .translate(y = reach - bar / 2, z = base_t + h - bar * 1.5);

    back | top | lip;
}
