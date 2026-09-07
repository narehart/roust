# E62 ancillary history signals

Full path/history diagnostic from `f704fe2`, using 200 non-merge commits
reachable from each task's base commit. Ranking sees the issue, baseline
returned files, and Git history; the E55 absent gold set is consulted afterward.
There is no bundle, token-budget result, text-validity guarantee, or adoption
claim. Source ranking and its IDF are unchanged.

| Slice | Tasks with excluded gold paths | Excluded path occurrences | Outside candidate suffix/name set |
|---|---:|---:|---:|
| Rust | 66 | 228 | 24 |
| C++ | 38 | 139 | 13 |

Number of affected tasks whose **entire excluded gold set** appears within
the ancillary ranking cutoff:

| Slice / channel | Top 4 | Top 10 | Top 26 |
|---|---:|---:|---:|
| Rust history | 19 | 33 | 37 |
| Rust path/history RRF | 5 | 19 | 33 |
| C++ history | 4 | 12 | 13 |
| C++ path/history RRF | 4 | 8 | 13 |

At top 10, history reaches some excluded gold in 55/66 Rust and 24/38 C++
tasks (88 and 61 path occurrences). Path fusion does not improve complete
excluded-set coverage at these cutoffs. The separate historical signal is
therefore worth a real retrieval test, but these counts cannot be added to
the baseline FILE score: other source files may remain missing, and candidate
names alone do not supply source context. Changelog co-change may describe
release bookkeeping rather than useful issue-localization evidence.

The current history engine filters through corpus membership and its code
suffix list. A separate channel could retain ancillary edges without changing
source lexical statistics. A future treatment must render relevant text,
account for its budget, and pass the original full-context metrics; the
top-k results here do not select a deployment threshold or expand the current
seven-candidate adoption family by themselves.

```sh
python lab/e62_mine.py --slice rust --out /tmp/rust_signals.json
python lab/e62_mine.py --slice cpp --out /tmp/cpp_signals.json
```

JSON files include source/input hashes, base commits, per-task history hashes,
ranked top-26 paths, missing-path ranks, and unsupported missing paths.
