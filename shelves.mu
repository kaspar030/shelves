// Copyright © 2026
// SPDX-License-Identifier: MIT
//
// Cluster-shelf component library.
//
// Usage from a root file next to this one (e.g. the generated `lib.mu`):
//   mod shelves;
//   use shelves::tray::*;
//   Tray(height = 30mm);
//   use shelves::holders::*;
//   BoltHolder(board_w = 70mm, board_d = 82mm, hole_dx = 60mm, hole_dy = 72mm);

pub mod params;
pub mod hexgrid;
pub mod connector;
pub mod holders;
pub mod cables;
pub mod tray;
pub mod devices;

// Convenience re-exports so callers can `use shelves::*;`
pub use params::*;
pub use tray::Tray;
