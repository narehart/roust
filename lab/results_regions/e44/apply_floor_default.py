#!/usr/bin/env python3
"""E45 adoption patch: flip the packer budget floor default 0.3 -> 0.15.
Apply ONLY when no harness arm is live (a rebuild follows and swaps the shared
binary). --pack-floor stays as the override; 0.3 restores the pre-E45 engine."""
import struct, pathlib
R = pathlib.Path("/Users/nicholasarehart/programming-projects/bgrep/roust-rs/src")
core = (R/"core.rs").read_text()
old = "static PACK_FLOOR_BITS: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0x3FD3333333333333); // 0.3f64"
bits15 = struct.unpack("<Q", struct.pack("<d", 0.15))[0]
new = f"static PACK_FLOOR_BITS: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0x{bits15:016X}); // 0.15f64 (E45 adopted; was 0.3)"
assert core.count(old) == 1; core = core.replace(old, new, 1)
core = core.replace(
 "// E45: the packer's per-file BUDGET FLOOR. Both packing passes weight a\n// region by `(PACK_FLOOR + scores[file])`; with the shipped 0.3 every",
 "// E45 (ADOPTED default 0.15, PR pending): the packer's per-file BUDGET FLOOR.\n// Both packing passes weight a region by `(PACK_FLOOR + scores[file])`; at\n// the pre-E45 0.3 every", 1)
(R/"core.rs").write_text(core)
main = (R/"main.rs").read_text()
old_m = "    #[arg(long, default_value_t = 0.3)]\n    pack_floor: f64,"
new_m = "    #[arg(long, default_value_t = 0.15)]\n    pack_floor: f64,"
assert main.count(old_m) == 1; main = main.replace(old_m, new_m, 1)
main = main.replace("/// E45: the packer's per-file budget floor (0.3 = shipped). Every region",
                    "/// E45 (adopted): the packer's per-file budget floor (0.15; 0.3 restores\n    /// the pre-E45 engine). Every region", 1)
(R/"main.rs").write_text(main)
print(f"default flipped to 0.15 (bits 0x{bits15:016X})")
