# Benchmarks

<!-- site:sub Every published roust number, what it measures, and the committed artifact it came from. -->

Every number roust publishes is produced by a committed artifact in this
repository. This page is the index: what each benchmark measures, what roust
scores, and where the raw records live. Nothing here is self-reported by the
engine — all of it comes from harnesses in `parity/` scored by
`lab/agentless_metric_v4.py` and its per-corpus variants.

## Metric <!-- note: what FILE, FUNCTION and LINE actually mean -->

roust reports the Agentless "% correct location" metric at three
granularities, plus a continuity measure:

- **FILE** — every gold file appears in the returned set.
- **FUNCTION** — the gold AST function spans are a subset of the predicted
  spans. Exact containment, not overlap.
- **LINE** — all-or-nothing coverage of the gold lines.
- **line mean-fraction** — the average share of gold lines covered, reported
  because all-or-nothing LINE hides partial progress.

One convention matters for comparisons: engine errors count as **wrong** at
every level and share the denominator with successes. Excluding them from a
level's denominator flatters that level, which is why the artifacts record the
convention explicitly.

## Python <!-- note: SWE-bench Lite and held-out Verified -->

```text title="SWE-bench, Agentless metric"
                            FILE   FUNCTION   LINE   fraction
roust — Lite (300)          92.33     57.67   46.00     .537
roust — Verified (407)      92.38     48.89   37.84     .494
Agentless GPT-4o            69.70     52.00   35.30        —
archex (BM25 default)       56.00     38.30   25.70        —
archex (vector/hybrid)      57.30     40.70   27.70        —
```

Verified is held out: no adoption decision was ever made on it. It exists to
catch tuning-set mirages, and it has — twice.

Two caveats on the comparison rows, both in the baselines' favour. The
Agentless figures are from its own paper on its own harness, not a re-run
here. And the archex FUNCTION numbers exclude two timed-out instances from
their denominator, where roust counts its own errors as wrong; scoring archex
by roust's convention would give 38.0 rather than 38.3.

Artifacts: `lab/results_regions/ws2c/agentless_metric_ws2c_lite300_cfamily.json`,
`lab/results_regions/ws2c/agentless_metric_ws2c_ver407_cfamily.json`.

## Complete split <!-- note: all 2,294 instances, fine-grained -->

```text title="SWE-bench full split (2,294 instances)"
FILE 85.66   FUNCTION 38.88   LINE 28.07   fraction .438
```

We are not aware of another system reporting fine-grained localization on the
complete split; published work uses Lite, Verified, or a bespoke subset. This
table predates the trace-boost and structural-block adoptions, so it is a
lower bound on the current engine — a re-measurement is scheduled.

Artifact: `lab/results_regions/agentless_metric_full2294.json`.

## Languages <!-- note: eight slices, one structural mechanism -->

```text title="Multi-SWE-bench, corrected language-aware scorer"
slice (n)                  FILE   FUNCTION   LINE   fraction
python — Lite (300)       92.33      57.67   46.00     .537
python — Verified (407)   92.38      48.89   37.84     .494
javascript/typescript     46.38      31.55   14.14     .264
java (128)                49.22      39.84   14.84     .433
go (428)                  64.95      32.94   18.46     .423
rust (239)                60.25      20.92    7.53     .249
c (128)                   51.56      28.12   13.28     .225
c++ (129)                 65.89      20.93    8.53     .311
```

One capability note before the corrections: `.rb` and `.pony` sources are indexed
by default as of August 2026. The gate that adopted them measured something worth
stating plainly — the previous engine retrieved **zero** of the 148 gold files in
those extensions, not because it ranked them badly but because it never indexed the
file type at all. That is why C's FILE and LINE move here, and why Java's FUNCTION
does. `.svelte` was measured in the same round and rejected: 2,927 files admitted to
reach 5 gold ones, at a significant cost to JS/TS.

Two further corrections are baked into this table. The function-level scorer
originally extracted gold spans with a Python-only AST parser, so every
non-Python FUNCTION number it produced was vacuous; those are retired. And C
and C++ source extensions were missing from the indexer entirely — on the C
slice, 50 of 128 instances returned nothing at all.

Cross-language FILE differences are dominated by corpus shape (the JS/TS slice
has a ~76.7 extension ceiling; Go is 397/428 one repository), so compare within
a row, not down the column.

All eight rows were re-measured on a single engine commit in August 2026. Three
of them moved when we did: the Go, C, and C++ figures previously published had
been measured before adoptions that changed those very slices, and re-running
them on one commit moved Go FILE 63.79 → 64.95, C FUNCTION 26.56 → 28.12, and
C++ FILE 65.12 → 65.89. The other five reproduced to the digit, which is what
makes that attributable to engine drift rather than to noise. It is a reminder
that a per-language scoreboard decays unless every row is re-run together.

## Agent loop <!-- note: does better retrieval change outcomes -->

```text title="tokenbench v2 — live Sonnet 4.5, n=15"
tool                success   median $/successful run
roust                 93.3%                    $0.93
embedding-RAG         80.0%                        —
grep                  26.7%                        —
```

A partial run stopped at a spend cap, reported as indicative rather than as a
headline. The grep and roust arms get their method as the agent's only search
tool; the RAG arm additionally keeps grep.

## Latency <!-- note: cold index and warm query -->

Index build is a few hundred milliseconds to a few seconds depending on repo
size, cached under `<repo>/.roust/`. Warm queries run in tens to hundreds of
milliseconds; structural packing on large JS/TS repositories is the slow case
at roughly 2 seconds.

Artifact: `lab/latency/latency_v1.json`.

## Reproducing <!-- note: run any of these yourself -->

The harnesses evaluate against local clones of the twelve SWE-bench
repositories, checked out per instance, so they need those clones present
first — `lab/README.md` documents the layout. With them in place:

```bash title="shell — reproduce the Lite table"
cargo build --release --manifest-path roust-rs/Cargo.toml
python parity/region_eval2.py --report /tmp/lite.jsonl
python lab/agentless_metric_v4.py --predictions /tmp/lite.jsonl --out /tmp/lite.json
```

Two guards make a wrong answer hard to produce by accident. The harness
refuses to run against a binary whose embedded git SHA does not match the
tree under test, so a stale build cannot silently score. And because the
harness rewrites the clones as it walks instances, concurrent runs must use
private copies (`--repos-dir`) — a shared checkout races itself and quietly
corrupts both runs.
