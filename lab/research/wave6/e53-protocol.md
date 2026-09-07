# E53 — engine correctness, emitted coverage, and file discovery

Baseline: clean main `ff0c995`. First isolate output-preserving optimization
and cache correctness (`3f2f3a9`): lazy shape-block computation, linear header
ends, separate count/lexical cache presence, invalidate ambiguous legacy
entries, and uniquely owned cache-write temporaries. Targeted tests compare
count-only, legacy, concurrent, warm/cold, and uncached behavior. Fourteen
fixed non-Verified tasks (first two of each of seven slices) measure isolated
block-cold and warm timing; retain all observations and require payload
identity. This small timing sample is not a recall gate or a universal speedup.

Mining uses archived predictions, gold solely as labels, and base-commit tree
listings without modifying source checkouts. A same-directory implementation /
declaration companion probe (first two absent companions in retrieved-file
order) finds only 4/338 gold proposals on JS/TS and 0/254 on C, with no complete
FILE rescues. Exact missing-source basenames occur in only 8/1218 JS/TS and
2/266 C cases counted as file occurrences. Do not implement blind companion
expansion or assume explicit path mentions cover the deficit.

## Frozen recall arms

Code inspection finds pass 1 credits every query term in its original
candidate, even when its output cap discards the term. Test:

1. `emitted`: `--emitted-coverage`, computing pass-1 coverage from emitted
   text (the unpadded source span when padding reconstructs the text).
2. `emitted-shape`: arm 1 plus `--shape-union-blocks` from E51.

No span cap, candidate ranking formula, file-selection rule, final padding
guard, or budget is changed. Research flags default off. Opt-in packing traces
record candidate/emitted spans and terms for diagnosis; the engine never reads
gold. Hold parameters fixed after this protocol is committed.

Discovery is full Rust239 / C++129 through the existing exact harness. Run
baseline, repaired flag-off control, and both arms. Require complete IDs,
zero unexplained flag-off payload drift, clean binary hashes, and error-as-wrong
scoring. Isolate structural caches by arm so cache history cannot contaminate
comparisons; archived E51/E52 observations retain their original provenance.

A candidate qualifies only with positive exact FUNCTION or LINE and positive
mean fraction on both slices, unchanged FILE, and <=2% mean-token growth.
Select at most one, by mean FUNCTION gain then fraction. Apply paired tests
with two-arm and eight-depth-comparison corrections; report paired fraction
and cost intervals. If neither qualifies, record the null without Verified.
If one qualifies, replicate unchanged on Java/Go/JS-TS/C/Lite, then only if all
FILE/FUNCTION/LINE/fraction values are nonnegative and token growth <=2%, run
the existing 407-case Python Verified final gate. Default adoption additionally
requires corrected statistical support and all validation/CI checks.

Cache correctness fixes are justified by executable invariants, independently
of whether a recall flag wins. Timing claims require measured identity and
raw timings. No result here establishes best-in-class quality or Python parity
without the corresponding evidence.
