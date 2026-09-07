# E54 — query-local relevance feedback

The E53 absent-source audit finds 1,213/1,218 JS/TS missing source files and
266/266 C-slice files pass the audited suffix/vendor/size/line-length guards.
Companion expansion has poor measured precision. C-slice misses concentrate
in Pony's compiler (252/266 occurrences), JS/TS in MUI (846/1,218). These are
repository-specific failure populations, not universal language properties.

Inspection of `select_files` finds feedback terms selected by whole-file
TF×IDF from up to three top implementation files. In a large source module,
frequent identifiers remote from query hits can dominate those twenty terms.
This motivates one frozen arm, `--local-feedback`: derive the same counts
from merged +/-3-line contexts around query hits instead. A source with no
text hits falls back to its original counts (path-only lexical matches).
Keep the twenty-term cap, IDF formula, candidate pool, seat cap, budget, and
packing defaults unchanged. Do not enable any E51/E52/E53 retrieval flags.
The new flag defaults off. No new file extensions or language parser is added.

Full discovery: JS/TS580 and C128. Compare clean main `ff0c995`, experimental
flag-off, and local-feedback with per-arm block caches. Preserve complete IDs,
raw outputs, errors-as-wrong, provenance hashes, and full flag-off payload
identity. Use the original exact scorer and paired McNemar/bootstrap statistics.
This mechanism changes FILE; the packing-only FILE identity assertion does
not apply to the enabled arm.

Qualify only if FILE improves on both discovery slices, FUNCTION/LINE/fraction
are each nonnegative on both, and mean tokens grow <=2%. Report raw paired
p-values and correction across two discovery slices × three exact endpoints;
no arm selection multiplicity is needed because only one arm is tested. Do
not tune radius or term count after observing results.

Only a qualifier replicates unchanged on Rust/C++/Java/Go/Lite. Only if every
metric remains nonnegative there (and costs <=2%) does it reach the existing
407-case Python Verified final gate. A default change additionally requires
corrected statistical support, relevant tests, and passing CI. Otherwise
record the failure/tradeoff and retain the flag solely for reproducibility.
No local diagnostic or discovery slice is claimed to be an untouched holdout.
