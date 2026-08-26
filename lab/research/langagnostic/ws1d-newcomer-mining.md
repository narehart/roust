# WS1d — newcomer-ranking mining: what separates gold newcomers from boilerplate?

Campaign #56, future-direction 2. Mining only; no engine change. The WS1 arc
(REJECT → additive-but-inert → mention-gate falsified) left one open question:
of the 499 gold files outside the indexer's extension allowlist, is there a
deterministic signal that admits them while rejecting the ~100:1 boilerplate?
This note answers it with three measurements and closes the line.

Sources: `lab/results_regions/ws1_ceiling_records.jsonl` (the 135
ceiling-blocked instances and their 499 out-of-allowlist gold files),
per-instance `git ls-tree` at each base commit, and
`lab/ws1d_newcomer_rank.py` (committed).

## 1. What the gold newcomers actually are

| extension | count |
|---|---|
| `.json` | 316 |
| `.md` | 158 |
| `.preview` | 12 |
| (no extension) | 5 |
| `.svelte` | 4 |
| `.cts` / `.diff` / `.mjs` / `.yaml` | 1 each |

Two immediate observations. First, **six of these are ordinary code files that
simply are not in `CODE_EXTENSIONS`** — `.svelte` (4), `.mjs`, `.cts`. Adding
those three extensions is a trivial, separately-gateable change with none of
the WS1 risk profile, and it is the only actionable item in this note.

Second, the mass is documentation and JSON fixtures: 307 of the 316 `.json`
gold files live under `docs/`, as do 86 of the 158 `.md`. Repo concentration is
extreme — 325 of 379 distinct (repo, path) gold newcomers are
`mui__material-ui`, 29 `sveltejs__svelte`, 18 `iamkun__dayjs`. Any rule fitted
here is fitted to Material-UI's documentation layout.

## 2. Path-shape discriminators: high recall, catastrophic precision

| rule | gold admitted | verdict |
|---|---|---|
| under a docs-like root dir (`docs/`, `documentation/`, `sites/`, `website/`) | 353/379 (93.1%) | see below |
| repo-root file | 11/379 (2.9%) | — |
| classic boilerplate basename (README/CONTRIBUTING/package.json/…) | 10/379 (2.6%) | correctly rare |

93% recall from one path rule looks promising until the denominator is
measured. At three Material-UI base commits:

```
files=12362  non-code newcomers=2003  docs-dir newcomers=1793  gold=1
files=12363  non-code newcomers=2003  docs-dir newcomers=1793  gold=1
files=12371  non-code newcomers=2006  docs-dir newcomers=1793  gold=1
```

**Admitting docs-dir newcomers admits 1,793 files to reach 1 gold file** — a
worse noise ratio than the ~100:1 that already sank WS1, because the gold
newcomers live *inside* the densest noise population rather than beside it.
The path-shape discriminator is therefore refuted: its recall is real and its
precision is unusable. This also explains the whole WS1 arc uniformly — the
failures were never about *finding* the gold newcomers, they were about the
gold newcomers being indistinguishable from their 1,792 neighbours.

## 3. Lexical ranking within the newcomer pool: the real ceiling

If admission rules cannot separate, ranking might. Measured on 40 ceiling
instances, scoring every non-code newcomer by path-token overlap with the
issue text (a deliberately cheap proxy — no file reads, no content scoring):

| gold newcomer reached | instances |
|---|---|
| rank 1 | 1/40 |
| top 5 | 6/40 |
| top 10 | 11/40 |
| top 20 | 16/40 |

Median gold rank 31.5 out of a median 2,004-file newcomer pool. The signal is
real — the top 1.6% of the pool — but it is nowhere near sharp enough for a
small admission quota, which is exactly what the packer can afford: WS1b
measured that there is no leftover budget on 547 of 579 MSWE instances and
none at all on Lite, and that manufacturing budget via `--newcomer-reserve`
costs FUNCTION −3.0 / LINE −2.0 on Python.

**Ceiling arithmetic.** A top-5 own-pool admission would reach gold on ~15% of
the 135 blocked instances ≈ 20 instances ≈ +3.4pp MSWE FILE, and would admit
4 non-gold newcomers per instance everywhere else, paid for out of region
budget on all 580 instances plus both Python benches. WS1b already measured
that trade at a smaller dose and it was negative.

## Verdict

**NO-GO for the newcomer-ranking line.** Three independent rounds
(admission by extension, admission by budget reserve, admission by mention)
plus this one (admission by path shape, ranking by lexical overlap) all fail
for the same measured reason: gold newcomers are documentation-shaped files
sitting in documentation directories with thousands of siblings, and no
deterministic signal available to us separates them at usable precision.

The 76.7 JS/TS FILE ceiling should be recorded as a **corpus property of
Multi-SWE-bench's JS/TS slice** — a slice where a quarter of gold "code" is
Material-UI documentation — rather than an engine defect to be closed. It is
reported as such in the README's cross-language note.

**One actionable item**, unrelated to the ranking problem: add `.svelte`,
`.mjs`, `.cts` to `CODE_EXTENSIONS`. These are code files that the allowlist
misses; they account for 6 of the 499 and carry none of the boilerplate
risk. Gate as an ordinary extension addition (defaults byte-identity on
repos without them, MSWE jsts arm, Lite/Verified no-regression).
