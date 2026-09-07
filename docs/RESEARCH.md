# Research

<!-- site:sub How roust is developed: flag-gated hypotheses, a two-set gate, and a public ledger of what failed. -->

roust is developed as a measurement loop rather than a feature list. Every
mechanism starts as a flag with its default off, is gated on a fixed protocol,
and is either adopted as a default or written up as a null. The nulls are kept
in the repository with their artifacts — they are the more useful half of the
record. This page is the method and the ledger; the numbers themselves are on
[Benchmarks](BENCHMARKS.md) and, in full, on the [Evaluation record](EVALUATION.md).

## The loop <!-- note: hypothesis, gate, ledger -->

```text title="one experiment round"
1. mine        find the failure in existing artifacts before writing code
2. implement   behind a flag, defaults byte-identical to main (proven, md5)
3. gate        tuning set AND held-out set, same protocol, paired statistics
4. decide      adopt as default, or write the null up with its anatomy
5. record      artifacts committed, ledger comment on the campaign issue
```

Step 1 is load-bearing. Two rounds were killed by mining alone, for the price
of a script: issue-mention gating (1 of 499 gold files was actually named by
filename in its issue) and the general displacement guard (culprit fires were
shape-identical to the fires behind the adopted wins).

## The dual gate <!-- note: why one benchmark is not enough -->

Adoption requires a win on SWE-bench Lite *and* on the 407 held-out Verified
instances, which no tuning decision is ever made on. This has caught two
mechanisms that looked good on the tuning set and were negative held-out —
query-type routing and one sibling-expansion variant. Both would have shipped
under single-set evaluation.

## What was adopted <!-- note: the changes that survived -->

- **Region packing economy** — guarded span padding and sub-linear length
  normalization. The largest single gain: FUNCTION 41.0 → 53.3, LINE
  35.7 → 42.7 on Lite, replicated held-out.
- **Trace-frame file boost** — files named in a stack trace in the query get a
  rank-decayed boost, raise-site first, query text untouched.
- **Structural blocks** — tree-sitter packing units for eight languages, one
  CST-walking mechanism plus a small node-type allowlist per grammar.
- **C-family indexing** — those extensions were never indexed; a vendored-code
  guard keeps bundled C in scientific-Python repositories from competing.
- **Multi-format trace parsing** — Java, Node, Go, and Rust frames feed the
  same boost channel as CPython tracebacks.
- **Structural symbols** — the definition index and anchor seating source from
  the same tree-sitter walks, for every grammar-covered language.
- **Extension coverage** — `.rb` and `.pony` sources indexed by default behind
  a fixture guard, after the gate found the engine had retrieved 0 of 148 gold
  files in those types. `.svelte` was measured in the same round and rejected.
- **Packer budget floor 0.15** (was 0.3) — lets the lexical score steer pass-2
  depth more steeply. FILE pinned on all 2,339 instances, zero token cost,
  FUNCTION +17/−9 pooled across eight gates.
- **Tiered pass-1 seats** — files ranked 16+ get a 40-token first seat instead
  of 120 and the freed budget goes to depth. FILE pinned, FUNCTION +54/−8
  pooled with no cell below the prior release.
- **Two speedups with byte-identical output** — a memoized padding guard and a
  per-file block/token cache. 8-23x faster warm queries than 0.3.2, proven
  identical on 128/128 full-slice instances.

## What failed <!-- note: nine mechanisms and one shared cause -->

```text title="rejected, with artifacts"
neighbor score smoothing      FILE +1 is churn (p=1.0); hub guard taxes gold
chunk-max file scoring        FILE +0.3, FUNCTION -2.7 (budget shrinkage)
chunk ranking, decoupled      tax halved; residual from list composition
query-type routing            Lite +1.7 LINE, Verified -2.2 FUNCTION
static test bridge            no bridged file was ever a missing gold file
sibling-sweep expansion       FUNCTION 53.3 -> 27.7 (depth charged too early)
universal indexing            FILE 46.4 -> 31.2 (boilerplate displaces code)
newcomer reserve budget       buys template admissions at region cost
issue-mention gating          1 of 499 gold files named in its issue
co-change seats               seat gold precision 0.08-3.65%; a centrality proxy
per-source seating            0 gold rescued of 143 at fixed admission count
PPR as packing budget         falsified twice (additive and replacement forms)
breadth cap as a default      FILE +1.7 on Lite but FUNCTION 57.7 -> 54.3 (p=.013)
changelog/docs indexing       an artifact of the corpus; fails held-out Verified
complementary block candidates FUNCTION rises on Rust/C++; mean line coverage fails the gate
overlap-only budget accounting frees duplicate charges but loses mean line coverage
```

Three of these share one cause, which is the most useful thing the campaign
found: **in this corpus, gold files are disproportionately large and central.**
Any mechanism that redistributes weight away from large central files taxes the
files it was built to rescue — whether it does so through graph-hub exclusion,
score damping, or selection-list composition. The interventions that worked
instead changed the budget economy directly, or added evidence-gated boosts
that fire rarely on strong signals.

## Where the record lives <!-- note: issues, writeups, artifacts -->

- `lab/research/` — one report per round, with its gate tables and anatomy.
- `lab/results_regions/` — per-instance evaluation records and scored metrics.
- `lab/stats/` — paired bootstrap and McNemar outputs.
- Campaign issues carry the running ledger: region quality (#4) and the
  language-agnostic campaign (#56).

## Open problems <!-- note: what is still unsolved -->

Line-level mean fraction is .537 against a measured lexical ceiling of .93 for
this corpus. The residual is dominated by patches that touch many sibling
functions, where no single-site mechanism suffices. File ranking trails trained
retrievers by roughly seven points on the depth-aligned metric. Both are
documented rather than papered over.

The E51/E52 non-Python follow-up separates three problems: file discovery,
packing within retrieved files, and benchmark composition. In the archived
baseline, 86% of Rust's missing source lines and 91% of C++'s are in files
already retrieved. All 300 Lite cases have one old-side gold file, while the
other language slices include large multi-file patches and non-source files.
The investigation therefore retains the published metrics and adds explicit
source-only, file-count, and gold-context-size diagnostics.

Two rounds tested complementary block candidates and overlap-aware budget
accounting at the shipped budget. The strongest exact-FUNCTION tradeoff was
structural/shape union: Rust 20.92→25.94 and C++ 20.93→25.58, but C++ mean
line fraction fell, so it did not pass the preset gate. No default changed,
and Python Verified was not used to tune or rescue a failed candidate.
Protocols, per-instance records, paired statistics, and compact evaluation
input snapshots are in `lab/research/wave6/e51-complementary-packing.md`,
`lab/research/wave6/e52-overlap-budget.md`, and `lab/results_regions/e51/` /
`e52/`. These are bounded negative adoption results, not a proof that parity
is impossible.

The following engine audit (E53/E54) found independent correctness and
performance improvements: distinguish incomplete lexical cache entries, isolate
concurrent cache writers, avoid discarded shape parses, find structural header
ends in linear time, and stream line splitting. The accompanying retrieval
experiments remain disabled: emitted-term coverage loses mean fraction on
Rust/C++, and query-local feedback fails the C FILE-improvement gate. No
Python Verified run was used to rescue these failures. Full results, timing
conditions, trace autopsies, and reproduction instructions are in
`lab/research/wave6/e53-engine-audit.md`, `e54-local-feedback.md`, and
`lab/results_regions/e53/README.md`.

E55 supplies gold file names as an explicit diagnostic intervention. Even
with that help, exact FUNCTION/LINE recall remains below the Python reference.
The current corpus excludes at least one gold path in 66/239 Rust and 38/129
C++ tasks, imposing raw FILE ceilings of 72.38% and 70.54% for that corpus.
These findings motivate separate work on file relevance, ancillary text
coverage, and within-file packing; oracle gains are not retrieval gains.
See `lab/research/wave6/e55-oracle-diagnosis.md` and the frozen artifacts in
`lab/results_regions/e55/`.

E56–E58 investigate pinned local semantic retrieval and AST-unit caching.
E59 diagnoses exact duplicate function bodies; E61 tests shared source with
explicit locations and a per-instance non-increasing token cost. E60 fixes
leading-comment ownership experimentally, but full Rust/C++ results have
opposing FUNCTION/LINE effects and fail the non-regression gate. These modes
remain experimental. Protocols and artifacts distinguish completed smoke,
workload diagnostics, and full discovery measurements. Final selection uses
the complete seven-candidate family correction in `lab/e61_family.py`, followed
by the established replication and held-out gates for any qualifying change.
