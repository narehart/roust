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

## Result: two cache layers, output byte-identical, up to 4.3x faster warm queries

Chosen design: (2), a lazy per-file side cache at `<repo>/.roust/blocks.json`
(separate file, so the index cache key is untouched; atomic temp+rename
flush at exit; `--no-cache` neither reads nor writes it). Two layers landed
in two commits:

1. **block spans** (`55f48b0`): python/ts/grammar/shape block spans keyed by
   `rel|fnv1a64(text)|mode`. Query-dependent window blocks are not cached.
2. **per-block tokenization** (`c72dbbc`): for every candidate span the
   packer needs `tokenize(seg)` (query-term intersection) and the cl100k
   `count_tokens(seg)`; both depend only on the file text and the span, so
   they are keyed `rel|hash` -> per-file vocab + `a-b` -> (token count,
   vocab ids). The vocab dedups tokens across a file's blocks, which keeps the
   file at 140-400 KB per repo after a query. `structural_def_entries`
   (anchor seating) is cached the same way. Profiling showed layer 1 alone
   bought little: the expensive part of the "structural" pass was never the
   tree-sitter parse, it was re-tokenizing every block of every returned
   file on every query.

Five-repo proof (`roust_pre_e50` = E49 binary; every arm sha256-identical on
stdout; cold = first query after deleting `blocks.json`, warm = min of 3):

| repo | pre-E50 | blocks-only cold / warm | full cache cold / warm | blocks.json |
|---|---|---|---|---|
| cli/cli (Go) q1 | 676 ms | 682 / 602 | 674 / **572** | 151 KB |
| clap-rs/clap (Rust) | 381 ms | 381 / 276 | 374 / **132 (2.9x)** | 205 KB |
| nlohmann/json (C++) | 660 ms | 661 / 508 | 669 / **153 (4.3x)** | 401 KB |
| apache/dubbo (Java) | 408 ms | 358 / 324 | 364 / **272** | 141 KB |
| cli/cli (Go) q2 | 657 ms | 693 / 610 | 682 / **553** | 156 KB |

Cold queries are unchanged (the cache is filled on the same pass that would
have computed the values anyway). Go moves least because its query time is
dominated by index load and candidate generation on a 711-file corpus, not
by the packer.

Full-slice identity (C, 128 instances, shipped defaults, vs the E49 arm
`lab/results_regions/e49/c_memo.jsonl`):

- layer 1 (`lab/results_regions/e50/c_blockcache.jsonl`): payload-identical
  128/128, regions identical 128/128, FILE 51.56 -> 51.56, tokens 8448 -> 8448.
- layer 2 (`lab/results_regions/e50/c_tokcache.jsonl`): payload-identical 128/128, regions identical 128/128, FILE 51.56 -> 51.56, tokens 8448 -> 8448.

Harness wall time is flat (171 s -> 167 s): each eval instance is a fresh
subprocess against a repo that other instances also touch, so the cache
warms across instances, but the harness is dominated by Python-side gold
loading and scoring, not by the engine. The speedup is a per-query, warm-repo
property, which is exactly the shape of agent usage (many queries against
the same checkout).

Rules kept: no change to any score, no change to the index cache key, no
new flag. Test suite 113/113.

## Latency benchmark, pre-E49 engine vs E50 (`lab/latency/latency_v2*.json`)

`lab/latency/bench_latency.py`, seven disposable repo copies, engines
`a1db4f6` (main before E49) and `c72dbbc` (this branch), same machine,
back to back. Query p50 `query_ms`: requests 1006 -> 61, flask 1057 -> 65,
django 2212 -> 126, clap 1187 -> 69, nlohmann/json 2026 -> 85, cli/cli
1696 -> 495, this working tree (3,902 files) 2432 -> 194. Bundles are
identical (e.g. requests: 8455 tokens, top score 17.3366 on both engines).
Full table in the README latency section.
