// Copyright © 2026
// SPDX-License-Identifier: MIT
//
// Shared parameters & design constants for the cluster-shelf system.
//
// All trays in this system share a common *footprint grid* and a common
// *stacking interlock* so that any tray can stack on any other tray
// regardless of which device it was generated for.

// ---------------------------------------------------------------------------
// Global footprint
// ---------------------------------------------------------------------------
// Every tray has the same outer width & depth so the stack is a clean column.
// Sized to comfortably fit a Raspberry Pi class board plus wiring margin.
// Override per-build if you want a wider family.
pub const FOOTPRINT_W = 120mm;
pub const FOOTPRINT_D = 90mm;

// Wall / floor thicknesses (FDM-friendly: multiples of a 0.4mm nozzle line).
pub const WALL = 2.4mm;
pub const FLOOR = 2.0mm;

// General fit clearance between mating printed parts.
pub const CLEARANCE = 0.3mm;

// ---------------------------------------------------------------------------
// Hex grid (universal mounting surface)
// ---------------------------------------------------------------------------
// Floor AND walls are perforated with this honeycomb. The same hex cell is the
// mounting grid: accessories clip in with matching hex plugs. Changing these
// re-flows the whole system (grid + every plug) consistently.
pub const HEX_AF   = 14.0mm;   // hex hole across-flats size
pub const HEX_WALL = 2.4mm;    // web between holes (thin = airier; also sets plug pitch)
pub const HEX_MARGIN = 4.0mm;  // solid border kept around each perforated face

// Plug interface (shelves/connector.mu). A plug is a hex prism sized to the hole
// minus clearance, with a snap barb that catches the back face of the surface.
pub const PLUG_CLEAR = 0.35mm;       // gap between plug and hole wall (slip fit)
pub const PLUG_BARB  = 0.45mm;        // how far the barb juts past the hole edge
pub const PLUG_BARB_H = 1.2mm;       // barb height (along insertion axis)
pub const PLUG_LEADIN = 0.8mm;       // chamfer lead-in at the plug tip

// ---------------------------------------------------------------------------
// Stacking interlock
// ---------------------------------------------------------------------------
// Each tray has 4 corner pegs pointing UP and 4 matching sockets pointing
// DOWN. Peg of tray N drops into the socket of tray N+1.
pub const PEG_D = 6.0mm; // peg diameter
pub const PEG_H = 5.0mm; // how far the peg protrudes above the rim
pub const PEG_INSET = 9.0mm; // peg centre inset from the outer wall

// Socket = peg diameter + clearance (slip fit). µcad 0.6 consts must be
// literals, so keep these in sync by hand:
//   SOCKET_D     = PEG_D + 2 * CLEARANCE
//   SOCKET_DEPTH = PEG_H + 0.4mm
pub const SOCKET_D = 6.6mm;
pub const SOCKET_DEPTH = 5.4mm;

// ---------------------------------------------------------------------------
// Ventilation
// ---------------------------------------------------------------------------
pub const VENT_SLOT_W = 4.0mm;
pub const VENT_SLOT_GAP = 6.0mm;
