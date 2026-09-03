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
| + symbol-graph + cap 32 | **94.00** (5 gained / 0 lost) | pending | pending | .5267 | 6/11 | p=.080 | 8707 (+1.7%) |

FILE +1.67 on Lite -- five more instances fully located, none lost -- for
+147 tokens. Fraction -.0105 (6 gains / 11 losses, p=.08): the depth cost
is small but the sign is the E28 sign. Exact FUNCTION/LINE decide.

## Verified (n=407) and JS/TS stub 25 (n=580): running
