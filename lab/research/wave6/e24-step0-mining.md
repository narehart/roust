# E24 step-0 mining — consequence-side displacement, reachable mass

Campaign #4 (region quality) / #56 follow-on. This is the **mining step only**:
the WS3d round closed the *fire-shape* line of attack NO-GO and named two
consequence-side candidates — floor-protection and seat-budget caps. Before
building either, this note asks the pre-registered question: **how much mass
is actually reachable, and on which benches?**

Source: `lab/results_regions/ws3d/mine_fires.json` (306 anchor/trace fires
across 121 instances, produced by `lab/ws3d_firelevel.py` during WS3d), plus
the seed anatomies in `lab/research/langagnostic/ws3d-displacement-guard.md`.

## Population

| channel | gain | loss | neutral |
|---|---|---|---|
| anchor | 89 | 113 | — |
| trace | 4 | 3 | 97 |

Slice coverage of the mined fires: java 122, jsts 111, rust 52, go 21 fires.
**Python is absent from this population** — the WS3d mining ran on the
Multi-SWE slices only, because that is where WS3b/WS3c's losses lived.

## Reachable mass, by candidate

Grouping the 113+3 loss fires by instance (56 instances with at least one
loss fire) and asking what happened to the gold file:

| class | instances | mechanism | candidate |
|---|---|---|---|
| **A. gold ejected from the ranked list entirely** | **3** | score inflation tightens the relative floor cut; a file that survived pre-boost falls out | floor-protection |
| **B. gold retained, rank same-or-worse, region budget lost** | **51** | inserted anchor seats consume pass-1 budget; pass-2 (where gold coverage lived) is starved | seat-budget cap |

Class A is `mui-34548`, `svelte-9973`, `svelte-11104`. Class B splits jsts 31 /
rust 13 / java 7.

Loss-fire shapes: 63 tail-inserts, 42 head-inserts, 8 head-moves, 3 trace-frame
boosts. Strength distribution of loss fires spans the same 0.5–2.5 range as the
gain fires — confirming WS3d's core finding at the population level, not just
the seed level: **strength does not separate culprits from wins**.

## Verdict on scope

1. **Floor-protection: NO-GO as a standalone round.** Three instances, all
   JS/TS, is below the noise floor of a 580-instance slice (±1 instance is
   0.17pp) and the mechanism touches the Python trace/anchor channels — so it
   would require full Lite-300 + Verified-407 revalidation (~1,400 eval
   instances) to buy at most 3 MSWE instances. The cost/benefit is
   unfavourable by roughly two orders of magnitude.

2. **Seat-budget cap: GO, but not on this evidence.** 51 instances is real
   mass, and the mechanism (pass-1 seating starving pass-2) is the same one
   that E18/E19 and E21 hit from other directions — it is the campaign's
   recurring packer-economy failure, now with a third independent sighting.
   But two things must be measured before implementing:
   - **Python-side mass is unmeasured.** The anchor channel is a Python
     default; the 51 instances are MSWE-only because that is where the mining
     ran. A Python `--explain` mining pass over Lite-300 + Verified-407 is the
     required step-0 for the Python half, and it is cheap relative to the arms
     (explain reruns, no scoring).
   - **The cap must be checked against the wins.** WS3c's adoption gains came
     from *exactly* this seating mechanism (18/18 changed Java instances went
     zero-anchors→fired; jackson-4013 fraction .036→.893). A cap that reclaims
     class-B budget by suppressing seats will suppress those. The
     discriminator question is whether a cap on *total* seat budget (rather
     than on individual seats) preserves the wins, which the fire data cannot
     answer — it needs per-instance budget accounting that only an explain
     rerun records.

## Recommended next round (E24a, scoped)

Explain-mining only, no engine change, both Python benches plus jsts:
1. Per instance, record pass-1 seat count, total seat tokens, budget share, and
   whether gold coverage lived in pass-1 or pass-2 spans.
2. Report the joint distribution for (a) the 51 class-B losses, (b) the WS3c/
   WS3b adoption wins, (c) the untouched majority.
3. GO only if a cap threshold exists that leaves every win's seat allocation
   intact while returning budget in class B — the WS1c/WS3d discipline: find
   the separator in the data, or record the NO-GO for the price of a script.

Until that runs, the rust FUNCTION −2 caveat and the svelte/jackson-class
losses remain live and documented, exactly as WS3d left them.
