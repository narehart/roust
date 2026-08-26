# E25 — does zero-config SHAPE-based block detection match the per-language node-kind allowlists?

Campaign #56 follow-on (language-agnostic directive), campaign #4 wave 6.
Engine: `roust 0.3.2 (abb96af, clean)`. **No default was flipped.**

## Question

`--structural-blocks` currently picks packing-unit headers with a hand-written
node-kind allowlist per language — `ts_header_start`, `java_header_start`,
`go_header_start`, `rust_header_start`, `c_header_start`/`cpp_header_start`
(~105 lines). `--shape-blocks` (E25, default OFF) replaces all of them with one
rule that reads tree-sitter's own field convention:

> a node is a header if it spans >1 line AND
> ((it has a `body` field AND a `name` or `declarator` field)
>  OR (it has a `value` field whose node has a `body` field)).

If that matches the allowlists, a newly linked grammar costs a grammar and
nothing else. This round measures whether it does, on all eight bench slices.

## Method

* **Same-commit pairing.** Every comparison is a `default` arm against a
  `--shape-blocks` arm, both at abb96af, both on the pinned binary, one private
  repo clone per arm (issue #41). 16 arms, 1632 non-Python + 707 Python = 2339 instances per arm-side.
* **Baselines NOT reused as the comparison arm.** The brief permitted reusing the
  committed baselines. I did not, because three of them predate adoptions that
  changed the very slices they cover (c/cpp at `0c0fc79`, before WS3c's
  language-agnostic symbol seating; go back at the WS2-era engine, before WS3b
  taught the tracer Go frame formats). Pairing an abb96af shape arm against those
  would have charged shape for three since-adopted changes. They are reported
  instead as a **drift audit** — see below, and it was the right call: three of
  them had in fact moved.
* **Provenance.** `--shape-blocks` was captured directly from the live process
  argv of all 16 runners (`lab/results_regions/e25/argv_raw.txt`): all 6 `_shape`
  arms carry the flag, all 6 `_def` arms do not. This is what makes a null result
  interpretable — without it, "no change" and "flag never passed" look identical.
* **Scoring.** `lab/agentless_metric_full.py --repos-dir --ts-functions
  --lang-functions` for the six non-Python slices (FUNCTION spans are parsed from
  the checkouts; without the wheels + `--repos-dir` FUNCTION silently scores 0.00
  — the WS3a lesson). Python uses `agentless_metric_v4.py` / `agentless_metric_verified.py`,
  the same two scorers the committed ws2c baselines were made with. Never
  `lab/agentless_metric.py`, which ignores CLI args.
* **Stats.** Exact McNemar (binomial, two-sided) on each all-or-nothing metric;
  Wilcoxon signed-rank on the per-instance line fraction.

Harness: `--shape-blocks` passthrough added to `parity/region_eval_full.py`,
`region_eval2.py`, `region_eval_verified.py`. Analysis: `lab/e25_paired.py`,
`lab/e25_drift_audit.py`, `lab/e25_shape_gap.py`, `lab/e25_table.py`,
`lab/e25_python_identity_gate.py`. Artifacts in `lab/results_regions/e25/`.

Go's 428-instance parquet was missing and was rebuilt
(`lab/mswe_adapter.py --langs go --out lab/mswe_go.parquet`): exactly **428**
rows, instance-id set **identical** to the ws2 baseline predictions file.

## Result — the complete per-language table

| slice | n | arm | FILE | FUNCTION (exact) | LINE (all-or-nothing) | line mean-fraction |
|---|---|---|---|---|---|---|
| **jsts** | 580 | default | 46.38 (269) | 31.21 (181) | 14.14 (82) | 0.26156 |
| | | shape | 46.38 (269) | 30.52 (177) | 13.79 (80) | 0.26343 |
| | | **delta** | +0.00 | -0.69 | -0.35 | +0.00187 |
| **java** | 128 | default | 49.22 (63) | 35.16 (45) | 14.84 (19) | 0.39691 |
| | | shape | 49.22 (63) | 37.50 (48) | 14.06 (18) | 0.40175 |
| | | **delta** | +0.00 | +2.34 | -0.78 | +0.00484 |
| **go** | 428 | default | 64.95 (278) | 28.97 (124) | 16.59 (71) | 0.41021 |
| | | shape | 64.95 (278) | 30.84 (132) | 15.89 (68) | 0.39457 |
| | | **delta** | +0.00 | +1.87 | -0.70 | -0.01563 |
| **rust** | 239 | default | 60.25 (144) | 19.67 (47) | 7.53 (18) | 0.24315 |
| | | shape | 60.25 (144) | 20.92 (50) | 7.11 (17) | 0.23001 |
| | | **delta** | +0.00 | +1.25 | -0.42 | -0.01314 |
| **c** | 128 | default | 46.88 (60) | 28.12 (36) | 10.94 (14) | 0.20217 |
| | | shape | 46.88 (60) | 28.91 (37) | 12.50 (16) | 0.21779 |
| | | **delta** | +0.00 | +0.79 | +1.56 | +0.01563 |
| **cpp** | 129 | default | 65.89 (85) | 17.83 (23) | 6.98 (9) | 0.29866 |
| | | shape | 65.89 (85) | 21.71 (28) | 6.98 (9) | 0.28142 |
| | | **delta** | +0.00 | +3.88 | +0.00 | -0.01724 |
| **python Lite** | 300 | default | 92.33 (277) | 54.67 (164) | 44.00 (132) | 0.52728 |
| | | shape | 92.33 (277) | 54.33 (163) | 44.00 (132) | 0.52728 |
| | | **delta** | +0.00 | -0.34 | +0.00 | +0.00000 |
| **python Verified** | 407 | default | 92.38 (376) | 47.17 (192) | 35.14 (143) | 0.47635 |
| | | shape | 92.38 (376) | 47.42 (193) | 35.14 (143) | 0.47639 |
| | | **delta** | +0.00 | +0.25 | +0.00 | +0.00005 |

| slice | McNemar FILE (def-only/shape-only, p) | FUNCTION | LINE | Wilcoxon fraction (up/down, p) | changed |
|---|---|---|---|---|---|
| **jsts** | 0/0, p=1.0000 | 5/1, p=0.2188 | 4/2, p=0.6875 | 40/43, p=0.9042 | 85/580 |
| **java** | 0/0, p=1.0000 | 1/4, p=0.3750 | 1/0, p=1.0000 | 11/10, p=0.5621 | 21/128 |
| **go** | 0/0, p=1.0000 | 10/18, p=0.1849 | 12/9, p=0.6636 | 69/90, p=0.0537 | 166/428 |
| **rust** | 0/0, p=1.0000 | 5/8, p=0.5811 | 2/1, p=1.0000 | 44/49, p=0.3548 | 101/239 |
| **c** | 0/0, p=1.0000 | 1/2, p=1.0000 | 0/2, p=0.5000 | 18/8, p=0.0525 | 26/128 |
| **cpp** | 0/0, p=1.0000 | 2/7, p=0.1797 | 3/3, p=1.0000 | 30/41, p=0.2256 | 74/129 |
| **python Lite** | 0/0, p=1.0000 | 1/0, p=1.0000 | 0/0, p=1.0000 | no change | 1/300 |
| **python Verified** | 0/0, p=1.0000 | 0/1, p=1.0000 | 0/0, p=1.0000 | 1/0, p=1.0000 | 1/407 |


**FILE is invariant in every one of the eight slices — zero discordant pairs,
2339 + 707 instances.** Shape never changed which files were retrieved anywhere;
all movement is *within* the file, in where block boundaries fall.

No metric reaches p<0.05 in any language. The two closest are line-fraction on
go (p=0.0537, 69 up / 90 down) and on c (p=0.0525, 18 up / 8 down) — and they
point in opposite directions, which is what noise looks like.

The one systematic signal: **FUNCTION-exact rises in 5 of 6 non-Python
languages** (cpp +3.88, java +2.34, go +1.87, rust +1.25, c +0.79; jsts −0.69),
while line mean-fraction drifts slightly *down* in the three languages with the
largest header populations (cpp −0.017, go −0.016, rust −0.013). Shape finds the
right function more often and packs its lines slightly less completely.

## Drift audit — committed baselines vs freshly-run abb96af defaults

| slice | committed baseline (engine) | FILE | FUNCTION | LINE | frac | abb96af default | drift |
|---|---|---|---|---|---|---|---|
| **jsts** | `ws3d/agentless_metric_ws3d_jsts_guard.json` (82c8d2f) | 46.38 | 31.21 | 14.14 | 0.26156 | 46.38/31.21/14.14/0.26156 | **none** |
| **java** | `ws3c/agentless_metric_ws3c_java_v2.json` (10967da) | 49.22 | 35.16 | 14.84 | 0.39691 | 49.22/35.16/14.84/0.39691 | **none** |
| **go** | `ws2/agentless_metric_mswe_go_exp.json` (aa9cb15) | 63.79 | 29.21 | 16.59 | 0.41140 | 64.95/28.97/16.59/0.41021 | FILE +1.16 / FUNC -0.24 / LINE +0.00 / frac -0.00120 |
| **rust** | `ws3c/agentless_metric_ws3c_rust_v2.json` (10967da) | 60.25 | 19.67 | 7.53 | 0.24315 | 60.25/19.67/7.53/0.24315 | **none** |
| **c** | `ws3b/agentless_metric_ws3b_c_base.json` (0c0fc79) | 46.88 | 26.56 | 10.94 | 0.19768 | 46.88/28.12/10.94/0.20217 | FILE +0.00 / FUNC +1.56 / LINE +0.00 / frac +0.00449 |
| **cpp** | `ws3b/agentless_metric_ws3b_cpp_base.json` (0c0fc79) | 65.12 | 17.83 | 6.98 | 0.29476 | 65.89/17.83/6.98/0.29866 | FILE +0.77 / FUNC +0.00 / LINE +0.00 / frac +0.00390 |

jsts, java, rust and python-Lite reproduce their committed baselines **to the
digit**, which independently validates this round's harness and scorer. go, c
and cpp had all moved since their artifacts were scored — the reason those
baselines were not used as comparison arms.

## Mechanism — what the allowlists actually buy

`lab/e25_shape_gap.py` replicates both predicates in Python tree-sitter and runs
them over every gold file of every slice, splitting the allowlist's exclusive
emissions into *true field-rule misses* (multi-line definitions the shape rule
structurally cannot see) and nodes dropped only by shape's own >1-line guard.

| slice | gold files | emitted by both | allowlist-only: TRUE field-rule misses | allowlist-only: one-line only | shape-only (false positives) |
|---|---|---|---|---|---|
| **jsts** | 2203 | 30879 | **0** — — | 2660 — `pair` 2041, `variable_declarator` 249 | 622 — `function_expression` 575, `export_statement` 44, `class` 3 |
| **java** | 200 | 7342 | **65** — `method_declaration` 46, `static_initializer` 19 | 561 — `method_declaration` 518, `constructor_declaration` 29 | 363 — `enhanced_for_statement` 349, `variable_declarator` 14 |
| **go** | 1434 | 11303 | **3526** — `type_declaration` 3526 | 346 — `type_declaration` 264, `method_declaration` 76 | 6 — `send_statement` 6 |
| **rust** | 881 | 31259 | **4803** — `impl_item` 4430, `macro_definition` 373 | 955 — `struct_item` 373, `impl_item` 304 | 5096 — `struct_expression` 2778, `let_declaration` 1602, `match_arm` 265 |
| **c** | 387 | 11340 | **1423** — `preproc_function_def` 521, `type_definition` 502, `struct_specifier` 206 | 674 — `type_definition` 310, `function_definition` 243 | 2 — `for_range_loop` 2 |
| **cpp** | 494 | 57314 | **33658** — `template_declaration` 21155, `preproc_function_def` 12245, `namespace_definition` 125 | 9290 — `function_definition` 6359, `struct_specifier` 1769 | 3794 — `for_range_loop` 1935, `lambda_expression` 1411, `init_declarator` 448 |

The concrete shapes the field convention misses fall into four families:

1. **Wrapper nodes whose `name`/`body` live on an inner spec** — Go
   `type_declaration` (3526), C++ `template_declaration` (21155), C
   `type_definition` (502). The wrapper carries neither field, so the rule
   cannot see it; in C++ the child `function_definition` is still caught, so
   the practical loss is the `template<...>` line falling outside the span.
2. **A body bound to a TYPE rather than a NAME** — Rust `impl_item` (4430).
   tree-sitter-rust names that field `type`, not `name`, so every `impl` block
   is invisible to the rule. This is the single largest true miss in Rust.
3. **Bodyless or macro-bodied definitions** — C/C++ `preproc_function_def`
   (521 / 12245; `#define f(x)` has `name` + `value`, but the value is not
   body-bearing), Rust `macro_definition` (373), Java abstract/interface
   `method_declaration` (46).
4. **Anonymous bodies** — Java `static_initializer` (19): a body with no name
   by construction.

Symmetrically, the field rule **admits control flow and expressions that merely
happen to bind a name to a body**: Rust `struct_expression` (2778) and
`let_declaration` (1602), C++ `for_range_loop` (1935) and `lambda_expression`
(1411), Java `enhanced_for_statement` (349). These are not definitions, and they
are the most likely source of the small line-fraction dilution.

**jsts is the clean case: 0 true field-rule misses.** Every jsts gap (2660
nodes, dominated by `pair` 2041 and `variable_declarator` 249) is a *single-line*
declaration — one-line arrow callbacks like `{ onClick: () => setOpen(true) }` —
dropped by shape's >1-line guard, not by the field convention. jsts is also the
only language where FUNCTION got worse, which is consistent: the allowlist's
earned coverage there is one-line bound functions.

## Python — measured, not assumed

The dispatch (`roust-rs/src/core.rs`) tests `.py` first, so a Python file never
reaches the shape branch:

```rust
let spans = if rel.ends_with(".py") {
    python_blocks(text)
} else if let Some(shape) = shape_blocks(text, rel).filter(|_| blocks == BlockMode::Shape) {
    shape
} else if ...
```

That settles Python *files* but not Python *benches*: matplotlib ships `.cpp`,
sphinx ships bundled `.js`, and those are indexed and do reach the shape branch.
The 60-instance identity gate (40 Lite + 20 Verified, flag ON vs OFF, two runs
each, cold cache) found **0 determinism failures and 6 payload differs** — all
six matplotlib or sphinx (`matplotlib-23987`, `sphinx-10325`, `sphinx-8801`,
`matplotlib-22865`, `sphinx-7454`, `sphinx-9230`); django (24 instances),
scikit-learn, astropy and seaborn were byte-identical.

So the Python rows were **not** asserted inert — the full 300 + 407 arms were run.
Per-instance inspection of the six differs shows every one is **metric-neutral**:
identical FILE, identical line recall to four decimals, identical region-file
sets. Only span boundaries *inside* the vendored `.js`/`.cpp` moved, shifting
token counts by single digits (e.g. 8518→8514). The Python gold was never
displaced.

The residue is the interesting part. Lite moved by exactly one FUNCTION flip
(`sphinx-8801`, 1→0) with FILE, LINE and fraction bit-identical; Verified moved
by exactly one the other way (`sphinx-8035`, 0→1, fraction +0.0182). Both are
sphinx, both net to noise (Lite FUNCTION −0.34, Verified +0.25), and FILE and
LINE are untouched on all 707 instances. The path is indirect — resizing a bundled `.js` span changed how much packing budget was
left, which re-truncated a Python region at a different boundary. **A
"structurally inert" flag can still perturb a bench through packer budget
competition from non-target-language files.** That is the transferable lesson,
and it is why the gate was worth running instead of quoting the dispatch.

## Verdict

**Shape MATCHES statistically — but it is not a free swap, and I do not
recommend deleting the allowlists outright.**

Against the brief's three options this lands between (1) and (2), so here is the
precise reading rather than a label:

* Option (1)'s first test is met: **every language is within noise.** No metric
  reaches p<0.05 in any of the eight slices, and FILE is perfectly invariant
  (0 discordant pairs across all 2339 paired instances).
* Option (1)'s second test is **not** met: several deltas are sign-negative —
  jsts FUNCTION −0.69, LINE negative on four slices, and line mean-fraction
  −0.016 (go), −0.013 (rust), −0.017 (cpp). Those fraction moves are *not*
  statistically significant at n=428/239/129, but they are **larger in magnitude
  than several deltas this campaign has previously adopted as wins** (WS3d shipped
  on jsts fraction +0.0018). "Not significant" and "not meaningful" are not the
  same claim, and at these sample sizes the round cannot separate them.

The mechanism section explains why the aggregate is a wash rather than a win:
shape gains FUNCTION-exact by admitting definition shapes the allowlists never
listed, and loses line-fraction by being blind to four real definition families
(`impl_item`, `type_declaration`, `template_declaration`, `preproc_function_def`)
while admitting control-flow nodes (`for_range_loop`, `let_declaration`,
`enhanced_for_statement`) that are not definitions at all. Those are structural
facts about the field convention, not sampling artifacts — they will not go away
with more instances.

**Recommendation: adopt shape as the zero-config FALLBACK, keep the allowlists as
per-language overrides.** This buys the property the experiment was actually for
— a newly linked grammar costs a grammar and nothing else, with no code from us —
at zero measured risk on the six languages already covered, and it spends none of
the earned coverage the mining just quantified. The 105 lines are not dead weight:
they encode, per language, exactly the shapes tree-sitter's field convention
cannot express.

Deleting them outright remains defensible if simplicity is weighted heavily —
the measured cost is bounded by the table above and no metric is significant —
but it should be a deliberate trade made with the gap table in hand, not a
conclusion drawn from "the numbers matched".

**No default was flipped in this round.** `--shape-blocks` stays default OFF.

### Follow-ups worth queueing

1. **Union rule** — emit a header if EITHER the allowlist or the shape rule
   fires. The gap table predicts this dominates both arms: it would keep
   `impl_item`/`template_declaration`/`type_declaration` and add the
   `function_expression` (575 in jsts) and lambda shapes the allowlists miss.
   Cheapest next arm and the only variant with a mechanism-backed reason to win.
2. **Drop shape's >1-line guard for the bound-value branch** — jsts's entire gap
   is 2660 one-line declarations and jsts is the only language where FUNCTION
   regressed. Directly targeted, one flag.
3. **Field-alias table** — a 6-line map (`impl_item`→`type`, `type_declaration`→
   inner `type_spec`) may recover most of the true misses without per-kind
   allowlists, i.e. a genuinely zero-config path that actually works.
4. **Python packer-budget coupling** — the sphinx-8801/8035 flips show non-target
   -language span sizes perturbing Python results through budget competition.
   Worth a dedicated look for any future flag claimed "structurally inert".

