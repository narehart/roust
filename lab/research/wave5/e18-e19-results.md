# E18 (similarity siblings) + E19 (nameable-family enumeration) — Lite-300 gate

*Campaign #4, wave 5. Branch `e18-sibling-sweep`, engine commit `07681c3`. Spec: the
wave5 sweep-localization survey (`multilang-and-sweeps.md` Part b, transplants #2/#3)
+ E17's failure-mode map (`wave4-mining` @ `e02cd5b`): post-adoption D-mass is
dominated by multi-function sweep patches (11/30 no-majority-owner); E16 proved
density re-ranking is the wrong signal, so both mechanisms add DEPTH keyed on
similarity-to-seed / name-family membership and never touch the existing ranking.*

## Mechanism (flag-gated, defaults byte-identical)

Given pass-1's pick in a file (the seed), `pack_regions` seats sibling spans
between pass 1 and pass 2 — budget-checked like pass-2 seats (skip, never
force-seat), marked pass-2 for the E12b guard (evictable; a file's pass-1 span is
never displaced), and excluded from pass 2's pool like any seated span. Spans the
zero-query-term filter drops from the ranked candidate list are kept as
sibling-only material — a sweep-family member need not contain a single query term.

- **E19 `--family-enum`**: def-name families derived from the seed's own name
  (seed must BE a member): exact method-name family across sibling classes
  (>= 2 members), or shared first/last name-segment family (raw
  underscore+camel split, segment >= 3 chars, >= 4 members). Python files only.
  Cap 8 members, nearest-to-seed first.
- **E18 `--sibling-sim <t>`**: SourcererCC-style identifier-token-bag overlap
  (multiset intersection / max bag size; `tokenize` bags minus stemmed
  Python-keyword exclusions; integer arithmetic until one final division) vs
  the seed span; threshold t, top `--max-siblings` (default 3) by overlap,
  ties by ascending span start.

Determinism: similarities precomputed once per file and sorted with `total_cmp`
(no comparator recomputation); family ordering pure-integer. Proofs: 53/53 Rust
tests (4 new fixtures: method family, suffix family, Type-2 clone cap,
budget-guard); defaults byte-identical to the main-built binary (92baeeb) on
12/12 sampled Lite instances (md5 over regions+bundle), two-run cross-process
determinism folded into the same check.

## Gate protocol

Four arms on Lite-300 (`parity/region_eval2.py`, private repos copy per issue
#41, engine `07681c3` clean, budget 8192): baseline (defaults) / E19-only /
E18-only (sim=0.7) / E18+E19. Scored with `lab/agentless_metric_v4.py`; paired
deltas vs baseline via `lab/stats/paired_tests.py` (paired bootstrap CI
n_boot=10000 + McNemar exact). Baseline must reproduce FUNCTION 53.33 / LINE
42.67 / fraction .5168 / FILE 277/300 exactly; FILE movement in any arm is a
contamination tripwire.

## Results (Lite-300, all arms 300/300 ok, engine `07681c3` clean)

| arm | FILE | FUNCTION | LINE (all-or-nothing) | mean fraction |
|---|---|---|---|---|
| baseline (defaults) | **277/300 (92.33)** | **53.33** | **42.67** | **.51683** |
| E19 `--family-enum` | 277/300 (92.33) | 27.67 | 18.00 | .25039 |
| E18 `--sibling-sim 0.7` | 277/300 (92.33) | 52.00 | 42.00 | .50360 |
| E18+E19 combo | 277/300 (92.33) | 26.67 | 17.33 | .24503 |

Baseline reproduces the adopted-engine reference EXACTLY (FUNCTION 53.33 /
LINE 42.67 / fraction .516831 / FILE 277) — no contamination. Paired deltas vs
baseline (`lab/stats/paired_tests.py`, n_boot=10000, McNemar exact):

| arm | FUNCTION Δ [CI95] | LINE Δ [CI95] | fraction Δ [CI95] | McNemar p (fn) | discordant (fn) |
|---|---|---|---|---|---|
| E19 | −25.67 [−31.33, −19.33] | −24.67 [−30.33, −19.00] | −.2664 [−.3208, −.2091] | 2.5e−15 | n01=13, n10=90 |
| E18 (0.7) | −1.33 [−3.33, +0.33] | −0.67 [−2.33, +1.00] | −.0132 [−.0261, −.0033] | 0.29 | n01=2, n10=6 |
| combo | −26.67 [−32.67, −20.33] | −25.33 [−31.00, −19.33] | −.2718 [−.3263, −.2142] | 4.5e−16 | n01=13, n10=93 |

FILE delta is exactly 0.0 with ZERO discordant pairs in every arm — the E12b
pass-1 exemption held structurally, and the contamination tripwire is clean.

## Verdict: REJECT (both mechanisms, and the combo)

Per the gate protocol (Lite negative → stop): no Verified run, no E18
threshold mini-sweep (0.7 showed no positive signal to sweep around).

### Autopsy: the packer economy inverts under gain-0 depth

The collapse is a *packing* failure, not a family-detection failure:

1. **Depth is not free at a fully-subscribed budget.** Sibling seats charge
   `spent` before pass 2, so every family span displaces pass-2 marginal
   coverage one-for-one; then the padded bundle exceeds budget and the E12b
   guard **de-escalates padding before evicting any whole span**. Adopted
   padding — the mechanism behind LINE 35.7→42.7 — is therefore sacrificed
   FIRST to keep gain-0 sibling spans seated. E19 arms carry FEWER spans than
   baseline (mean 57.0 vs 81.8 per instance) at the same ~8.5k token spend:
   fewer, larger, query-term-free family bodies replaced many small padded
   query-dense spans.
2. **E19's families fire far too broadly.** Every packed file has a seed, and
   shared first/last name-segment families (>= 4 members) are ubiquitous
   (`get_*`, `test_*`, `*_handler` shapes), so the cap-8 flood hits most
   files, not just sweep-shaped ones. The E17 pool motivated the mechanism on
   ~11/30 top-D cases; the mechanism as flagged applied itself to ~all 300.
3. **The upside exists but is swamped 7:1.** n01=13: thirteen instances DID
   flip correct at function level under E19 — the sweep-capture signal is
   real (consistent with E17's precondition analysis) — against n10=90
   destroyed. E18 at 0.7 is nearly inert (typically 0 additions per file;
   dose-response confirmed only at 0.3–0.6) and still pays a small but
   CI-significant fraction cost (−.013 [−.026, −.003]).

### What a future variant must change (before any re-gate)

- **Charge depth in tokens, not spans, and cap it**: a per-file sibling token
  budget (e.g. <= 10–15% of the file's cap) instead of span-count caps.
- **Fix the guard order for gain-0 seats**: evict gain-0 sibling spans BEFORE
  de-escalating any padding — added depth should never outrank the adopted
  padding it displaces.
- **Gate the trigger, not just the mechanism**: fire only on sweep-shaped
  evidence (e.g. >= K same-family members already carrying query hits, or
  anchored files only), not on every pass-1 seed.

The E16 lesson generalizes: it is not enough for the *signal* to be
similarity-to-seed rather than density — the *allocation* must also not trade
away the padded high-gain mass the engine already earns. Case-mining beat
literature priors again, in the uncomfortable direction: Blue-Pencil-style
within-file sweep expansion is near-perfect *given a human-confirmed seed and
no token budget*; under an 8k budget with an unconfirmed seed, it is a net
destroyer at Lite scale.

### Artifacts

- Predictions: `lab/results_regions/{e18e19_baseline,e19_family,e18_sim07,e18e19_combo}.jsonl`
- Scores: `lab/results_regions/agentless_metric_{e18e19_baseline,e19_family,e18_sim07,e18e19_combo}.json`
- Paired stats: `lab/stats/e18e19_{e19_family,e18_sim07,e18e19_combo}_vs_baseline.json`
- Byte-identity + determinism proof: 12/12 sampled instances, defaults md5-identical
  (regions+bundle) to the main-built 92baeeb binary, two runs each (scratchpad
  `byte_identity_check.py`; not committed)
- Private repos copy used throughout (issue #41); `lab/swebench_repos` untouched
  by the eval loop (scorer reads are `git show` object-DB only)
