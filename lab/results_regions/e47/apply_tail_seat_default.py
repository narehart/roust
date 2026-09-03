#!/usr/bin/env python3
"""E47 adoption patch: make the tiered pass-1 seat the default (tokens 40,
after rank 16). Apply ONLY when no harness arm is live (a rebuild follows).
--tail-seat-tokens 0 restores the pre-E47 flat 120-token seat."""
import pathlib
R = pathlib.Path("/Users/nicholasarehart/programming-projects/bgrep/roust-rs/src")
core = (R/"core.rs").read_text()
old = "static TAIL_SEAT_TOKENS: std::sync::atomic::AtomicI64 = std::sync::atomic::AtomicI64::new(0);"
new = "static TAIL_SEAT_TOKENS: std::sync::atomic::AtomicI64 = std::sync::atomic::AtomicI64::new(40); // E47 adopted default; 0 = pre-E47"
assert core.count(old) == 1; core = core.replace(old, new, 1)
core = core.replace("// evidence exactly as it can any other file. 0 = off (byte-identical).",
                    "// evidence exactly as it can any other file. ADOPTED default 40 (E47);\n// `--tail-seat-tokens 0` restores the pre-E47 flat seat.", 1)
(R/"core.rs").write_text(core)
main = (R/"main.rs").read_text()
old_m = "    #[arg(long, default_value_t = 0)]\n    tail_seat_tokens: i64,"
new_m = "    #[arg(long, default_value_t = 40)]\n    tail_seat_tokens: i64,"
assert main.count(old_m) == 1; main = main.replace(old_m, new_m, 1)
main = main.replace("    /// file still counts as retrieved; pass 2 can re-expand it on evidence.\n    /// 0 = off.",
                    "    /// file still counts as retrieved; pass 2 can re-expand it on evidence.\n    /// Adopted default 40 (E47); 0 restores the pre-E47 flat 120-token seat.", 1)
(R/"main.rs").write_text(main)
print("tail seat default flipped to 40 / after 16")
