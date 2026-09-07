# E51 — complementary blocks improve FUNCTION, but do not pass the gate

**Decision: no adoption and no held-out run.** None of the three frozen arms meets the positive mean-line-fraction criterion on both discovery slices. Shape union improves exact FUNCTION in both languages, but C++ mean fraction falls. Hit windows lose substantially more fraction. No configuration was changed after observing a slice.

## What the baseline diagnosis establishes

All 300 Lite cases have one old-side gold file under the existing parser. Raw cross-language FILE differences combine retrieval quality, gold-file count, and non-source patch content. The diagnostic source filter is declared in `lab/e51_mine.py`; it does not change the official metric.

| Slice | n | FILE | Source-only FILE | One-gold-file FILE (n) | Missing source lines in already retrieved files |
|---|---:|---:|---:|---:|---:|
| lite | 300 | 92.33 | 92.33 | 92.33 (300) | 85.4% |
| jsts | 580 | 46.38 | 54.59 | 72.76 (279) | 45.3% |
| java | 128 | 49.22 | 82.03 | 94.12 (51) | 64.3% |
| go | 428 | 64.95 | 69.63 | 88.30 (188) | 56.7% |
| rust | 239 | 60.25 | 76.57 | 97.56 (82) | 85.9% |
| c | 128 | 51.56 | 64.23 | 80.00 (65) | 38.9% |
| cpp | 129 | 65.89 | 82.95 | 100.00 (47) | 91.4% |

Source-only denominators exclude cases with no source gold (577 JS/TS, 123 C; the other rows keep their full denominator). The last column is **line-weighted**, not an instance success rate. The one-file comparison still differs in repositories and task difficulty; it is a diagnostic, not a controlled causal comparison.

## Full discovery results at the shipped token budget

| Slice | Arm | FILE | FUNCTION exact | LINE | Mean fraction | Mean tokens |
|---|---|---:|---:|---:|---:|---:|
| rust | baseline | 60.25 | 20.92 | 7.53 | 0.248645 | 8464 |
| rust | shape-union | 60.25 | 25.94 | 7.53 | 0.249442 | 8411 |
| rust | hit-windows | 60.25 | 25.52 | 6.28 | 0.214636 | 7820 |
| rust | wide-hit-windows | 65.27 | 25.52 | 5.86 | 0.210383 | 8172 |
| cpp | baseline | 65.89 | 20.93 | 8.53 | 0.310977 | 8515 |
| cpp | shape-union | 65.89 | 25.58 | 10.08 | 0.305416 | 8493 |
| cpp | hit-windows | 65.89 | 23.26 | 10.08 | 0.279906 | 8245 |
| cpp | wide-hit-windows | 68.99 | 23.26 | 10.08 | 0.281106 | 8358 |

All arms completed with zero engine errors and zero gold/predicted-file read failures in the exact scorer. The baseline reproduces the archived published Rust/C++ rows. Both packing-only arms keep FILE exactly unchanged; the wide arm adds the already-existing symbol graph and admission cap, so its FILE gains cannot be attributed to the window representation.

## Paired evidence and decision

| Slice | Arm | FUNCTION gains/losses | Raw exact McNemar p | Three-arm adjusted p | Fraction delta [paired bootstrap 95% CI] |
|---|---|---:|---:|---:|---|
| rust | shape-union | 15/3 | 0.007538 | 0.022614 | +0.000798 [-0.020050, +0.021462] |
| rust | hit-windows | 21/10 | 0.070756 | 0.212267 | -0.034008 [-0.072853, +0.003922] |
| rust | wide-hit-windows | 22/11 | 0.080143 | 0.240430 | -0.038262 [-0.078066, +0.001016] |
| cpp | shape-union | 8/2 | 0.109375 | 0.328125 | -0.005560 [-0.029048, +0.018776] |
| cpp | hit-windows | 9/6 | 0.607239 | 1.000000 | -0.031071 [-0.075203, +0.011726] |
| cpp | wide-hit-windows | 9/6 | 0.607239 | 1.000000 | -0.029871 [-0.074133, +0.013660] |

Rust shape-union FUNCTION passes the three-arm correction, but not the stricter 12-test discovery family (two languages × two exact depth endpoints × three arms: adjusted p≈.0905). C++ alone is underpowered. The intervals do not establish that the fraction losses are harmless: the predeclared gate requires nonnegative direction, not merely p>.05. Paired bootstrap resamples instances; repository clustering and prior use of these MSWE slices limit generalization.

No Java/Go/JS-TS/C replication or Python Verified run was justified under the protocol. The default-off research flags remain available to reproduce the tradeoffs. No claim of Python-level recall or a universal ceiling follows from this round.

## Oracle answer-size diagnostic

`gold_cost.json` serializes gold lines/functions alone using cl100k_base, without filenames or retrieval context. This is a workload measurement, **not a strict tokenizer lower bound or attainable recall ceiling**. Python Lite gold-function context has a 90th percentile of 1,054 tokens; Rust 8,522; C++ 18,763. Rust has 25/239 cases above 8,192; C++ 21/123 readable cases; Lite 0/300. Six C++ cases with unreadable non-UTF-8 gold fixtures are explicitly reported and excluded from cost summaries, not from retrieval scoring.

## Next mechanism

The small-window arms underfill actual output (Rust 7,820 tokens versus 8,464 baseline) while losing coverage. The packer charges overlapping candidates in full before merging output spans. E52 separately tests union-based budget accounting with the original structural representation; its frozen protocol is `e52-protocol.md`. This is a hypothesis, not an E51 adoption.

## Reproduction and integrity

- Protocol: `lab/research/wave6/e51-protocol.md`, committed before discovery.
- Mining and oracle diagnostics: `lab/results_regions/e51/{mining,gold_cost}.json` with per-instance records and input hashes.
- Raw discovery records, exact scores, paired statistics, binary SHA256/commit IDs, full instance lists, and scorer package versions: `lab/results_regions/e51/discovery/`.
- Main baseline binary: clean `ad13f2f`; E51 experimental binary: clean `d295b7b`. Flags-off payloads match on **368/368** discovery instances. The cached scorer produced byte-identical files to the original scorer on all four smoke arms.
- Frozen five-field evaluation snapshots and restore tool: `lab/results_regions/e51/inputs/` and `lab/e51_inputs.py`. Restored parquet bytes may differ, but the canonical evaluation rows are verified identical. Existing data is never overwritten.
- No paid/model-backed evaluations were used. Local benchmark clones were only read; separate private clones were checked out by the runner.
