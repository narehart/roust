# Research

<!-- site:sub How roust is developed: flag-gated hypotheses, a two-set gate, and a public ledger of what failed. -->

roust is developed as a measurement loop rather than a feature list. Every
mechanism starts as a flag with its default off, is gated on a fixed protocol,
and is either adopted as a default or written up as a null. The nulls are kept
in the repository with their artifacts — they are the more useful half of the
record.

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

## What was adopted <!-- note: the six changes that survived -->

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
