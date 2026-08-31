# E36 — `--import-edges-v2` at the shipped operating point

The first adoption-grade measurement of the import-graph fix: **full slices**
(not the >= 3-gold-file strata the exploratory rounds used) at the **shipped
operating point** (cap 16, budget 8192), with baseline and treatment run on
the same pinned binary so no cross-commit drift enters the comparison.

## Python dual gate — PASS, by identity

| gate | n | FILE | line fraction | records changed |
|---|---|---|---|---|
| SWE-bench Lite | 300/300 | 92.33 -> 92.33 | .52728 -> .52728 | **0** |
| SWE-bench Verified | 407/407 | 92.38 -> 92.38 | .47635 -> .47635 | **0** |

Both match the published references exactly. This gate was **load-bearing,
not a formality**: the new resolution fires on `.c`/`.cpp`/`.h`, and Python
repos do contain those under the adopted `--cfamily-ext` default (numpy,
pandas), so the flag could have moved Python numbers without any `.py` branch
changing. It did not, on any of 707 instances.

## The languages it targets

| slice | n | baseline | ie2 alone | ie2 + 2hop + cap32 |
|---|---|---|---|---|
| Java | 128 | 49.22 | 50.00 (+0.78) | **50.78** (+1.56) |
| C | 128 | 51.56 | **50.00 (-1.56)** | **55.47** (+3.91) |
| C++ | 129 | 65.89 | 65.89 (+0.00) | not run |

**The edges alone are not an adoption.** On the full C slice they *cost*
1.56. The mechanism is the same displacement seen in E30: new edges create
new Guarantee-1 seats, and inside a cap of 16 those seats push other
candidates out. The exploratory 3+ figure (C 4.35 -> 28.26) was measured at
cap 128 with two hops and does not transfer to the shipped settings.

Combined with the breadth the new edges need in order to pay -- two hops and
cap 32 -- both slices gain: C **+3.91** on the full slice for ~150 extra
tokens. Line fraction drops on both (java .4152 -> .3832, c .2251 -> .2117),
the familiar breadth/depth trade that E29 showed is budget-recoverable.

## Status

Not adopted. The combination that wins bundles three changes (edges, hops,
cap), each of which needs its own dual gate before any default moves; only
the edges have been Python-gated so far. Recorded here so the next round
starts from measured ground rather than from the exploratory numbers.
