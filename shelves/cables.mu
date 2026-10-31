// Copyright © 2026
// SPDX-License-Identifier: MIT
//
// Cable-management accessories that clip into a tray WALL (the floor works
// too). Both ride on a `PlugRow`: two plugs in same-height cells two columns
// apart, which exist on every wall layout.
//
// WHERE THE CABLES GO: out through the wall hexes (large enough for RJ45 and
// USB plugs), dressed along the walls with `CableComb` (several cables side by
// side) or `CableClip` (a bundle). Cables run vertically (along Y).
//
// Local frame: X along the wall, Y up the wall, Z out of the wall; z = 0 is
// the wall face, the plugs hang into -Z.
//
// Both parts are solid prisms over the plug footprint (no baseplate), printed
// OUTER face down with the plugs pointing up: the slot / channel openings sit
// on the bed and only short bridges remain.

use std::geo2d::*;
use std::geo3d::*;
use std::ops::*;

use super::hexgrid::*;
use super::connector::*;

const SQRT3 = 1.7320508075688772;

// The body outline: hull of the two plug shoulders and a `w` x `h` rectangle.
sketch CableFootprint(w: Length, h: Length, af: Length, wall: Length, shoulder: Length) {
    cp = col_pitch(af = af, wall = wall);
    {
        Hex(radius = (af + 2 * shoulder) / SQRT3).translate(x = [-cp, cp]);
        Rect(width = w, height = h);
    }.hull();
}

// Cable comb: `teeth` vertical channels that cables are pressed into from the
// front; the mouth is narrower than the channel, so cables snap in and stay.
pub part CableComb(
    teeth = 4,
    slot_w = 4mm,          // cable diameter the channel accepts
    mouth = 3.2mm,         // channel mouth (< slot_w: retains the cable)
    tooth_w = 2.4mm,       // wall between channels
    lip = 1.2mm,           // mouth depth
    base_t = 2.4mm,        // solid layer between the wall and the channels
    shoulder = 1.5mm,
    af = 14.0mm,
    wall = 2.4mm,
    surface_t = 2.0mm,
) {
    pitch = slot_w + tooth_w;
    comb_w = teeth * pitch + tooth_w;
    height = base_t + slot_w + lip;
    len = 3 * af;          // longer than the footprint: cuts run straight through

    xs = ([0 .. teeth - 1] - (teeth - 1) / 2) * pitch;
    channels = Cube(size_x = slot_w, size_y = len, size_z = slot_w)
        .translate(x = xs, z = base_t + slot_w / 2);
    mouths = Cube(size_x = mouth, size_y = len, size_z = lip + 1mm)
        .translate(x = xs, z = base_t + slot_w + (lip + 1mm) / 2 - 0.01mm);

    CableFootprint(w = comb_w, h = af, af = af, wall = wall, shoulder = shoulder)
        .extrude(height = height)
      - channels - mouths;

    PlugRow(af = af, wall = wall, surface_t = surface_t);
}

// Cable clip: one vertical channel for a bundle, closed by two lips that
// leave an entry gap; the bundle is pushed in past the lips.
pub part CableClip(
    opening = 12mm,        // channel width and depth (bundle diameter)
    gap = 6mm,             // entry gap between the lips
    bar = 2mm,             // lip thickness
    base_t = 2.4mm,
    shoulder = 1.5mm,
    af = 14.0mm,
    wall = 2.4mm,
    surface_t = 2.0mm,
) {
    height = base_t + opening + bar;
    len = 3 * af;

    channel = Cube(size_x = opening, size_y = len, size_z = opening)
        .translate(z = base_t + opening / 2);
    entry = Cube(size_x = gap, size_y = len, size_z = bar + 1mm)
        .translate(z = base_t + opening + (bar + 1mm) / 2 - 0.01mm);

    CableFootprint(w = opening + 4 * bar, h = af, af = af, wall = wall, shoulder = shoulder)
        .extrude(height = height)
      - channel - entry;

    PlugRow(af = af, wall = wall, surface_t = surface_t);
}
