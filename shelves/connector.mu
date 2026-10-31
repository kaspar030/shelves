// Copyright © 2026
// SPDX-License-Identifier: MIT
//
// The universal connector: a hex PLUG that pushes into a hex grid cell (floor
// or wall) and snaps. Every accessory (board holders, cable holders) mounts by
// carrying one or more of these on a baseplate.
//
// Geometry:
//   * A plug points in -Z below an accessory body that sits at z = 0.
//   * Shaft: a slotted hex tube sized (hole_af - clearance) so it slides into a
//     cell; being hexagonal it cannot rotate in the hex hole.
//   * Barb: a slightly larger hex flange near the tip, tapered toward the tip
//     (lead-in) and flat on top to catch the BACK side of the surface.
//   * Fingers: the shaft is a slotted tube so the barb can flex through.

use std::geo2d::*;
use std::geo3d::*;
use std::ops::*;

use super::params::*;
use super::hexgrid::*;

const SQRT3 = 1.7320508075688772;

// A single snap plug, tip pointing -Z. z = 0 is the TOP face of the surface
// the plug passes through (the accessory body sits on it at z >= 0).
//   surface_t : thickness of the floor/wall the plug passes through.
//
// The shaft is a hex TUBE split by two crossing slots into four fingers, so
// the barb can flex inward while it passes the hole and snap out behind it.
// The barb is widest at its top (flat retention face, just below the surface)
// and tapers to just under shaft size at the tip (lead-in).
//
// Print orientation: the accessory body flat on the bed, plug pointing UP. The
// only overhang is the barb's retention face (`barb`, < 0.5mm).
pub part Plug(
    af = 14.0mm,           // = HEX_AF (hole across-flats)
    clear = 0.35mm,        // = PLUG_CLEAR
    barb = 0.35mm,         // = PLUG_BARB
    barb_h = 1.2mm,        // = PLUG_BARB_H
    surface_t = 2.0mm,     // surface thickness to pass through
    tube = 1.6mm,          // finger (tube wall) thickness
    slot = 1.6mm,          // width of the two finger slots
) {
    af_shaft = af - clear;
    r_shaft = af_shaft / SQRT3;
    r_bore  = (af_shaft - 2 * tube) / SQRT3;
    r_barb  = (af_shaft + 2 * barb) / SQRT3;

    // The tip IS the barb: a hex frustum from just under shaft size at the tip
    // (lead-in) up to barb size at its flat top (retention face, with a small
    // play below the surface). The straight shaft runs from 0.5mm inside the
    // body down to 0.2mm inside the barb, so no faces or edges coincide.
    barb_top = -surface_t - 0.15mm;
    tip = barb_top - barb_h - 0.6mm;
    r_tip = r_shaft - 0.3mm;
    taper = r_barb / r_tip;
    barb_part = Hex(radius = r_tip)
        .extrude(height = barb_top - tip, scale = (x = taper, y = taper))
        .translate(z = tip);
    shaft_bottom = barb_top - 0.2mm;
    shaft = Hex(radius = r_shaft)
        .extrude(height = 0.5mm - shaft_bottom)
        .translate(z = shaft_bottom);

    // Fingers: everything below z = -0.3mm is split by two crossing slots.
    finger_len = -0.3mm - tip;
    slots = Cube(size_x = af * 2, size_y = slot, size_z = finger_len + 1mm)
        .translate(z = tip - 1mm + (finger_len + 1mm) / 2)
        .rotate([0°, 90°]);

    (shaft | barb_part)
        - Hex(radius = r_bore).extrude(height = 2mm - tip).translate(z = tip - 1mm)
        - slots;
}

// Two plugs side by side in the SAME row, two column-pitches apart (same
// column parity, so both land in cells at the same height), centred on the
// origin. Works on the one-row tray walls and locks rotation. The accessory's
// origin goes midway between the two cells.
pub part PlugRow(
    af = 14.0mm,
    wall = 2.4mm,
    surface_t = 2.0mm,
) {
    cp = col_pitch(af = af, wall = wall);
    Plug(af = af, surface_t = surface_t).translate(x = [-cp, cp]);
}
