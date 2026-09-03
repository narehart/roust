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

## Rust smoke: pass on every criterion

sg + cap 32 @ 8192, tail seat after rank 16, n = 239:

| arm | FILE | FUNCTION | LINE | fraction | frac G/L | Wilcoxon | tokens |
|---|---|---|---|---|---|---|---|
| shipped (cap 16) | 60.25 | 19.67 | 7.53 | .2431 | -- | -- | 8464 |
| sg32 @ 8192 | 65.27 | 17.57 | 6.28 | .2103 | -- | -- | 8577 |
| **+ tail seat 40** | 65.27 (0 flips) | **19.25** | 7.11 | **.2361** | **46/17** | **p<1e-4** | **8578** |
| + tail seat 60 | 65.27 (0 flips) | 18.83 | 7.53 | .2327 | 39/16 | p=.0001 | 8578 |
| sg32 @ 9216 (E46) | 65.27 | 20.50 | 7.11 | .2397 | 51/7 | p<1e-4 | 9597 |

* Identity: FILE 65.27 -> 65.27, zero per-instance flips, both stubs.
* Tokens: 8577 -> 8578. Zero cost.
* Depth: fraction +.0258, FUNCTION +1.68 (4 gained / 0 lost vs the 8192
  arm), LINE +0.83; against SHIPPED, FUNCTION is a measured null (2/3,
  p=1.0) and the fraction is within .007.
* Dose: 40 beats 60 on fraction and FUNCTION; 60 beats 40 on LINE by one
  instance. Wide replication uses 40.

The stub returns ~80% of what the +13% budget bought (fraction .2361 vs
.2397 at 9216), for nothing. The pass criteria set above are all met.

## Wide replication, tail seat 40 after rank 16, sg + cap 32 @ 8192

| slice | n | FILE | fraction delta | gain/loss | Wilcoxon | tokens |
|---|---|---|---|---|---|---|
| Rust | 239 | 65.27 (0 flips) | +.0258 | 46/17 | p<1e-4 | 8577 -> 8578 |
| **Java** | 128 | 51.56 (0 flips) | **+.0343** | **22/1** | **p=.0001** | 9049 -> 9055 |
| C | 128 | 56.25 (0 flips) | +.0064 | 15/8 | p=.20 | 8602 -> 8605 |
| **Go** | 428 | 70.79 (0 flips) | **+.0397** | **91/28** | **p<1e-4** | 8592 -> 8595 |
| **JS/TS** | 580 | 52.07 (0 flips) | **+.0145** | **67/32** | **p=.0002** | 8749 -> 8749 |
| **C++** | 129 | 68.99 (0 flips) | **+.0172** | **29/8** | **p=.0001** | 8602 -> 8607 |

Six for six on direction, five of six significant (C is 15/8, p=.20), FILE
pinned on all six by construction, tokens within +6 everywhere. Java -- the
slice with the largest depth tax at cap 32 -- gets the largest refund.
Exact FUNCTION/LINE chained.

## Python dual gate at SHIPPED settings (cap 16, budget 8192, no symbol graph)

At the shipped cap the bundle still carries ~30 files, so the stub fires on
files ranked 16+ even with no breadth change. This is what a default would
ship. Baselines are E36's, equal to the published references.

| gate | n | FILE | FUNCTION | LINE | fraction | frac G/L | Wilcoxon | tokens |
|---|---|---|---|---|---|---|---|---|
| Lite | 300 | 92.33 (0 flips) | 54.67 -> **57.67** | 44.00 -> **46.00** | .5273 -> **.5372** | 14/1 | **p=.0097** | 8559 -> 8560 |
| Verified | 407 | 92.38 (0 flips) | 47.17 -> **48.89** | 35.14 -> **37.84** | .4764 -> **.4937** | 27/7 | **p=.0002** | 8558 -> 8559 |

Paired FUNCTION: Lite **11 gained / 2 lost, McNemar p=.022**; Verified
**8 gained / 1 lost, p=.039**. Both gates significantly positive on FUNCTION
and on fraction, LINE up 2.0 and 2.7 points, FILE pinned, tokens flat.

For scale: the E12 pad-lines/len-exp adoption (PR #40) moved Lite FUNCTION
41 -> 53.3 and was the largest depth gain on record; nothing since has moved
Lite FUNCTION by more than one point. This moves it **+3.0 on Lite and +1.7
on held-out Verified, at zero cost, with a mechanism that cannot touch FILE.**

## Why it works, stated plainly

Every returned file was being given a 120-token seat regardless of rank.
Roughly half the returned files are additions below rank 16, and at shipped
settings those seats consume ~1,700 tokens -- a fifth of the budget --
mostly on files that never held gold lines. The stub keeps each such file
present (one header span, so FILE is unchanged) and hands the freed budget
to pass 2, which spends it where the query terms are. The gain is largest
exactly where the tax was largest (Java, Go).

