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
//   CornerPost(vx = 2mm, vy = 5mm, lift = 4mm);

pub mod params;
pub mod hexgrid;
pub mod connector;
pub mod holders;
pub mod cables;
pub mod tray;

// Convenience re-exports so callers can `use shelves::*;`
pub use params::*;
pub use tray::Tray;
