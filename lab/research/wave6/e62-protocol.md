# E62: separate ancillary-file signals

E55 proves that source-corpus membership cannot reach the raw Python FILE
reference. Engine inspection also finds that history mining filters through
the current corpus and then `is_code_file_with`, whose suffix list excludes
documentation/configuration even when broad corpus flags admit those paths.
Test whether a separate path/history channel can rank ancillary candidates
without changing source IDF or source selection.

This is a candidate-list diagnostic, not a token-budget retrieval treatment.
Use full Rust/C++ discovery inputs, their original baseline returned file sets,
and only the 200 non-merge commits reachable from each base commit. Consider
regular tracked blobs <=2 MB with the documented ancillary suffixes/names.
Skip commits changing more than 50 paths. Score each ancillary path by summed
normalized co-change with baseline returned paths: pair_count / sqrt(source
commit_count * ancillary_commit_count). Independently score query/path token
overlap with path-corpus inverse document frequency. Report historical ranking
and equal reciprocal-rank fusion (k=60), with deterministic path tie breaks.
Zero-score paths do not enter a channel.

Ranking receives issue text, baseline output paths, and base-commit history;
gold paths are consulted only afterward. Report missing-path rank positions,
top-4/10/26 coverage of the E55 absent set, and residual missing paths. These
cutoffs are diagnostic and cannot select a deployment threshold. Candidate
blobs are identified by Git metadata; text validity and rendered source
coverage remain requirements for a future actual retrieval arm. No production
defaults, extra source regions, or Verified examples are involved.

The historical signal is motivated by the repository-history retrieval work
already cited in E55. Co-change with release notes may explain benchmark
coverage without improving a user's code context; retain that distinction.
