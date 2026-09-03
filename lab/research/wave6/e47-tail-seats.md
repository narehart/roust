# E47 — tiered pass-1 seats (breadth without the seat tax)

## The constant behind the tax

E45/E46 established that at a fixed budget breadth and depth are coupled
through the mandatory one-seat-per-returned-file, and priced the coupling:
sg + cap 32 needs ~9,216 tokens (+12-15%) to hold shipped depth. Reading
`pack_regions` pass 1 turns that into a literal number: every returned file
gets a flat `floor_tok = 120` allowance off the top, with
`spare = budget/2 - 120 * n_files` distributed by score share. At cap 32
(42.5 files) `spare` is negative, so **every file gets exactly 120 tokens in
pass 1 -- ~5,000 of 8,192 -- before pass 2 packs any depth.** The seat is
the tax, and 120 is its rate.

## Mechanism

`--tail-seat-tokens T --tail-seat-after K` (default off, byte-identical):
files at index >= K in the returned order (lexical picks first, then
additions by rank) get a pass-1 allowance of T instead of 120. The block is
trimmed to its header (pass 1 already trims to the allowance, min 4 lines),
so the file still carries >= 1 span and **still counts as retrieved** --
FILE is pinned by construction -- and pass 2 can re-expand the file on
lexical evidence exactly as it can any other. Stub by default, expand on
evidence. Language-agnostic: it acts on whatever block the existing
structural/window pass produced.

Arithmetic: 12 tail files x (120 - 40) = ~960 tokens returned to pass 2 at
cap 32 -- almost exactly the +13% that E46 found the depth-neutral point
needs. So the hypothesis is sharp: **cap-32 breadth at shipped depth at
shipped tokens.**

## Pass criteria (set before the numbers)

* FILE identical to `rust_sg32` instance-for-instance (identity gate).
* Tokens within +/-2% of the 8192 arm.
* FUNCTION / LINE / fraction move TOWARD shipped (19.67 / 7.53 / .2431 from
  17.57 / 6.28 / .2103); the exact metrics decide, not the proxy.
* Failure mode to watch: gold LINES that live in a tail file's trimmed seat
  and are not re-expanded by pass 2 -- that would show as FUNCTION/LINE
  losses concentrated in tail files.

## Rust smoke (running)

sg + cap 32 @ 8192, tail seat 40 and 60 tokens, after rank 16.
