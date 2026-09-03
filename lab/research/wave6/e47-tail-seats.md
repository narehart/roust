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

## Exact metrics at cap 32 + stub 40 (vs shipped AND vs the plain cap-32 arm)

| slice | n | FILE | FUNCTION | G/L vs cap32 | McNemar | G/L vs shipped | LINE | fraction | tokens |
|---|---|---|---|---|---|---|---|---|---|
| **Go** | 428 | 64.95 -> **70.79** | 28.97 -> **32.71** | **34/1** | **p<.001** | **19/3** | 16.59 -> **17.99** | .4102 -> **.4138** | flat |
| Rust | 239 | 60.25 -> **65.27** | 19.67 -> 19.25 | 4/0 | p=.125 | 2/3 | 7.53 -> 7.11 | .2431 -> .2361 | flat |
| Java | 128 | 49.22 -> **51.56** | 36.72 -> **39.06** | **9/0** | **p=.004** | 3/0 | 14.06 -> **14.84** | .4152 -> **.4282** | flat |
| C++ | 129 | 65.89 -> **68.99** | 17.83 -> **20.16** | 4/0 | p=.125 | 3/0 | 6.98 -> **8.53** | .2988 -> **.3072** | flat |
| C | 128 | 51.56 -> **56.25** | 28.12 -> 28.12 | 2/0 | p=.50 | 0/0 | 13.28 -> 12.50 | .2251 -> .2167 | flat |
| JS/TS | 580 | 46.38 -> **52.07** | 31.21 -> 29.66 | **8/0** | **p=.008** | **4/13, p=.049** | 14.14 -> 12.59 | .2616 -> .2421 | flat |

Three readings, all measured:

* **Go, Java, C++: above shipped on every column at shipped tokens** -- the
  combination E46 could only buy with +12-15% tokens, now at +0%. Go's
  FUNCTION +3.74 (19 gained / 3 lost vs shipped, p=.001) is the largest
  FUNCTION gain of the campaign on any slice.
* **Rust, C: FILE up, depth a measured null vs shipped** (2/3 and 0/0).
* **JS/TS: FILE +5.69 but FUNCTION still 1.55 UNDER shipped (4 gained / 13
  lost, p=.049).** The stub recovers part of its cap-32 tax (8 gained / 0
  lost vs the plain cap-32 arm) but JS/TS carries the largest tax in the
  set and the stub alone does not close it. At cap 32 JS/TS still needs
  budget (E46: ~10.7k) -- or a smaller cap -- and that must be stated
  rather than averaged away.

So the cap-32 operating point is now free on four slices, depth-null on two
(Rust, C: null) and depth-negative on one (JS/TS). **None of this is the
adoption question**: cap 32 is not proposed as a default. The stub alone at
the shipped cap 16 is, and its rows are the E47 ship round below.

## Ship round: stub 40 / after 16 ALONE at shipped settings (cap 16, 8192, no symbol graph)

What a default flip actually ships. Baselines E36/E37 `*_base`.

| slice | n | FILE | fraction delta | gain/loss | Wilcoxon | tokens |
|---|---|---|---|---|---|---|
| **Java** | 128 | 49.22 (0 flips) | **+.0176** | **17/0** | **p=.0003** | 8762 -> 8764 |
| **C++** | 129 | 65.89 (0 flips) | **+.0122** | **25/6** | **p=.0010** | 8510 -> 8515 |
| **Rust** | 239 | 60.25 (0 flips) | **+.0055** | **33/17** | **p=.026** | 8464 -> 8464 |
| C | 128 | 51.56 (0 flips) | -.0002 | 8/4 | p=.47 | 8447 -> 8448 |
| **Go** | 428 | 64.95 (0 flips) | **+.0132** | **62/28** | **p=.0002** | 8467 -> 8468 |
| JS/TS | 580 | running | | | | |
| Lite | 300 | 92.33 (0 flips) | +.0099 | 14/1 | p=.0097 | 8559 -> 8560 |
| Verified | 407 | 92.38 (0 flips) | +.0173 | 27/7 | p=.0002 | 8558 -> 8559 |

Four significant positives and one null so far on the non-Python slices
(JS/TS running), both Python gates significant, FILE pinned on all, tokens
within +5.

### Ship round, exact metrics vs shipped (FILE pinned, tokens flat, everywhere)

| slice | n | FUNCTION | G/L | McNemar | LINE | fraction |
|---|---|---|---|---|---|---|
| **Go** | 428 | 28.97 -> **32.94** | **20/3** | **p<.001** | 16.59 -> **18.46** | .4102 -> **.4234** |
| **Java** | 128 | 36.72 -> **39.84** | 4/0 | p=.125 | 14.06 -> **14.84** | .4152 -> **.4328** |
| **C++** | 129 | 17.83 -> **20.93** | 4/0 | p=.125 | 6.98 -> **8.53** | .2988 -> **.3110** |
| **Rust** | 239 | 19.67 -> **20.92** | 3/0 | p=.25 | 7.53 -> 7.53 | .2431 -> **.2486** |
| C | 128 | 28.12 -> 28.12 | 0/0 | -- | 13.28 -> 13.28 | .2251 -> .2249 |
| JS/TS | 580 | 31.21 -> **31.55** | 4/2 | p=.69 | 14.14 -> 14.14 | .2616 -> **.2635** |
| **Lite** | 300 | 54.67 -> **57.67** | **11/2** | **p=.022** | 44.00 -> **46.00** | .5273 -> **.5372** |
| **Verified** | 407 | 47.17 -> **48.89** | **8/1** | **p=.039** | 35.14 -> **37.84** | .4764 -> **.4937** |

Eight populations scored, 2,339 instances: **FUNCTION 54 gained / 8 lost
pooled**, LINE up on five and flat on three, fraction up on seven and flat
on one (C, -.0002), **not a single cell below shipped**, FILE pinned on all
eight, tokens within +5 everywhere. Go alone is +3.97 FUNCTION (20 gained /
3 lost, p<.001) -- the largest FUNCTION gain on any slice in the campaign,
at zero cost. JS/TS, the slice that resisted every other lever, is +0.34
FUNCTION and +.0019 fraction here (4/2, a null in the right direction).

## Adoption verdict: flip the default to 40 tokens after rank 16

This is the cleanest adoption case the campaign has produced: it cannot
change FILE, it costs nothing, and on the exact metrics it wins on seven
populations and draws on the eighth. `--tail-seat-tokens 0` restores the
pre-E47 flat 120-token seat exactly. The JS/TS ship-round row also matters
for what it rules out: the stub does not hurt the slice with the most files
per bundle at shipped settings; it only fails to help it at cap 32.

