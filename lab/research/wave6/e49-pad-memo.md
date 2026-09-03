# E49 — the query was 64% padding bookkeeping (a pure-performance fix)

## How it was found

The directive asks for "fast". A warm-cache profile on cli/cli (711 files)
showed the index load at 90 ms and the query pipeline at ~1.5 s -- the
cache was fine; the per-query work was not. Ablation by flag:

| flag | query_ms | note |
|---|---|---|
| default | 1626 | |
| `--budget 2048` | 860 | pass-2 loop scales with budget, as designed |
| `--max-additions 0` | 1368 | admission is not the cost |
| `--no-structural-blocks` | 1154 | tree-sitter is ~30% |
| **`--pad-lines 0`** | **581** | **padding is 64% of the query** |

`--pad-lines 5` is the adopted E12 default (Lite FUNCTION 41 -> 53.3), so
it stays. Its *implementation* was the problem.

## The mechanism

`pack_regions`' E12b de-escalation guard shrinks padding one line at a time
on the lowest-gain span when the padded bundle exceeds budget, and after
**every single-line shave** it called `build_padded`, which re-split every
selected file's text and re-tokenized every merged span from scratch -- up
to (origins x pad_lines) full rebuilds per query, each O(total bundle text).

## The fix

Split each file's lines once, and memoize `(file, span) -> (text, tokens)`.
Between consecutive shaves only one origin moved, so nearly every span is a
memo hit. **Pure caching: no decision, order, or tie-break changes.**

## Proof of identity, then speed

Bundle SHA-256 old vs new binary, and warm median wall time (3 runs):

| repo | bundle | old | new | speedup |
|---|---|---|---|---|
| cli/cli (Go), query A | identical | 1646 ms | 686 ms | 2.4x |
| cli/cli (Go), query B | identical | 1496 ms | 679 ms | 2.2x |
| clap-rs/clap (Rust) | identical | 3394 ms | 380 ms | **8.9x** |
| nlohmann/json (C++) | identical | 4090 ms | 677 ms | 6.0x |
| apache/dubbo (Java) | identical | 2669 ms | 381 ms | 7.0x |

All 113 engine tests pass unchanged. Full-slice identity (C, 128 instances,
payload + regions dict vs the pre-fix binary): IDENTITY_PLACEHOLDER
