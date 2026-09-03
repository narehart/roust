# E50 — structural blocks are the next per-query cost (profile after E49)

Quiet-machine ablation on the memoized binary (`lab/results_regions/e49/profile.py`):

| repo | default | `--pad-lines 0` | `--no-structural-blocks` | `--budget 2048` | `--max-additions 0` |
|---|---|---|---|---|---|
| cli/cli (Go, 711 files) | 590 ms | 559 | 551 | 574 | 549 |
| clap-rs/clap (Rust) | 343 ms | 307 | **193 (−44%)** | 299 | 288 |
| nlohmann/json (C++) | 619 ms | 562 | **262 (−58%)** | 589 | 620 |

After E49, padding is ~5-10% of a query and no single stage dominates on Go.
On Rust and C++ the tree-sitter structural-block pass over the returned
files is 40-60% of the query: every query re-parses the full text of every
returned file to derive block spans that depend only on that file's content.

## Plan

Cache block spans per file. Two candidate designs, to be chosen after
reading the call sites:
1. compute at index time for every indexable file and persist in the cache
   payload (re-keys the cache; cold index cost up, amortized over queries);
2. lazy per-file memo written back into the cache on first use.
Either is output-identical by construction (same spans from the same text).
