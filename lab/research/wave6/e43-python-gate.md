# E43 — the Python dual gate on the non-source rules: FAIL

The configuration that puts Java over 63.64 depends on `--docs-data-files`,
which had never been gated. It is the most dilutive rule in the engine, and
Python repos carry plenty of `.md`/`.rst`/`.json`, so the gate was
load-bearing rather than a formality.

Config: `--symbol-graph --changelog-files --docs-data-files`, shipped
operating point. Baselines are E36's, equal to the published references.

| gate | n | FILE | line fraction | gained | lost | McNemar p |
|---|---|---|---|---|---|---|
| Lite | 300 | 92.33 -> 92.67 (+0.33) | +.00038 | 1 | 0 | 1.000 |
| **Verified** | 407 | 92.38 -> **90.91 (-1.47)** | +.00470 | **3** | **9** | 0.146 |

**Verified regresses.** Nine instances lost against three gained. The losses
cluster in documentation-heavy repos -- sphinx (3), django (2), xarray (2) --
which is exactly the predicted dilution: indexing `.md`/`.rst`/`.json` adds
corpus that outranks the code.

The regression is not statistically significant at p=0.146, but the dual gate
is a **guard, not a hypothesis test**: a 3:1 loss ratio and -1.47 points on
the held-out set is precisely the signal it exists to catch, and this
campaign has twice been saved by it before (two Lite-only mirages in wave 5).

## Consequence

`--docs-data-files` **cannot be adopted as a default**, and neither can the
Java configuration that depends on it. Java's clearance of 63.64 is real as a
measurement and unshippable as a default -- which is the same conclusion the
non-source analysis reached on principle, now confirmed on evidence.

## What remains adoptable

`--symbol-graph` alone is Python-neutral on both gates (Lite 92.33 -> 92.67,
Verified 92.38 -> 92.63, both McNemar p=1.00) and positive on every
non-Python slice. It is the one genuine adoption candidate from this whole
sequence -- though its per-slice gains were individually underpowered, so the
honest next step for it is more instances rather than a default flip.

## Standing summary

* All six slices can be made to clear 63.64, five of them on genuine
  retrieval mechanisms.
* **None of those configurations is currently shippable as a default**: the
  five genuine ones cost 1.5-2x tokens and lose line depth, and Java's
  depends on a rule that fails this gate.
* The mechanism worth keeping is the symbol-reference graph.
