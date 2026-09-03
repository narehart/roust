# E48 — can breadth become a default now that the stub refunds its tax?

E28 rejected cap 32 on Python for region regressions. E47's tiered seat
refunded most of the depth tax that admission width incurs. This round asks
the direct question under the NEW shipped defaults (floor 0.15, stub 40/16):
does `--symbol-graph --max-additions 32` clear the Python dual gate, and
does a smaller stub close JS/TS's residual cap-32 tax?

Baselines are the post-E47 Python arms (= the published references).

## Lite (n=300)

| arm | FILE | FUNCTION | LINE | fraction | frac G/L | Wilcoxon | tokens |
|---|---|---|---|---|---|---|---|
| shipped (E47 defaults) | 92.33 | 57.67 | 46.00 | .5372 | -- | -- | 8560 |
| + symbol-graph + cap 32 | **94.00** (5 gained / 0 lost) | **54.33** | 43.67 | .5267 | 6/11 | p=.080 | 8707 (+1.7%) |

FILE +1.67 on Lite -- five more instances fully located, none lost -- for
+147 tokens. But FUNCTION **57.67 -> 54.33, 2 gained / 12 lost, McNemar
p=.013**, and LINE 46.00 -> 43.67. The stub refunded most of the cap-32
depth tax on the non-Python slices; on Lite it does not: the E28 sign is
back, now on the exact metric and significant.

## Verified (n=407)

| arm | FILE | fraction | frac G/L | Wilcoxon | tokens |
|---|---|---|---|---|---|
| shipped (E47 defaults) | 92.38 | .4937 | -- | -- | 8559 |
| + symbol-graph + cap 32 | **94.59** (9 flips) | .4818 | 10/20 | **p=.030** | 8704 (+1.7%) |

Same shape on the held-out set: FILE up, fraction significantly down
(10 gains / 20 losses). Exact FUNCTION/LINE pending.

## Verdict: breadth stays an opt-in operating point, not a default

Both Python gates say the same thing, now with the stub in place: cap 32 +
symbol graph buys FILE (+1.7 Lite, +2.2 Verified) and pays for it in depth
(Lite FUNCTION -3.3, p=.013; Verified fraction p=.030). The campaign's
adoption rule is "wins or draws everywhere"; this loses on the held-out
depth columns, so it is **not adopted**. It remains the documented operating
point for callers who want breadth: `--symbol-graph --max-additions 32`,
ideally with `--budget ~9216` (E46) to restore depth.

This also closes the question E28 left open: the depth cost of cap 32 on
Python was never only a budget artifact (E29) nor only a seat-count
artifact (E47) -- after both fixes, a residual, significant depth loss
remains on Python at cap 32. Python's bundles have the highest lexical
precision in the set, so widening admission there dilutes pass 2 more than
it does elsewhere.
