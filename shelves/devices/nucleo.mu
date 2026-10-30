// Device profile: ST Nucleo-64 (e.g. NUCLEO-F401RE / L476RG class).
// Board: ~70 x 82.5 mm. Mounting: 4 holes; the spacing below is a practical
// rectangular approximation — verify against your exact Nucleo variant and
// adjust HOLE_DX / HOLE_DY if needed.
// Holder style: BOLT (clean M3 mount holes).
// SPDX-License-Identifier: MIT

pub const BOARD_W = 70mm;
pub const BOARD_D = 82.5mm;
pub const BOARD_T = 1.6mm;
pub const HOLE_DX = 60mm;
pub const HOLE_DY = 72mm;
pub const SCREW_D = 3.2mm;    // M3 self-tap / clearance
pub const POST_D  = 6mm;
pub const STANDOFF_H = 5mm;   // clears solder tails on the underside
pub const TRAY_H = 30mm;
pub const FOOTPRINT_W = 120mm;
pub const FOOTPRINT_D = 90mm;
