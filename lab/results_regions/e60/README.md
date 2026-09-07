# E60 leading comments: mixed full-slice results, no adoption

Frozen candidate `09697e9`; baseline engine `645170a`. The declaration-owned
comment mode is default-off. Full discovery results use the original exact
scorer, requested budget 8192, padding 5, and length exponent .85.
All 368 flag-off payloads are identical; no engine or scoring errors occurred.

| Slice / arm | FILE | FUNCTION | LINE | Mean line fraction | Mean actual tokens |
|---|---:|---:|---:|---:|---:|
| Rust baseline, 239 | 60.25 | 20.92 | 7.53 | .248645 | 8464.05 |
| Rust leading comments | 60.25 | 21.76 | 7.11 | .236854 | 8454.85 |
| C++ baseline, 129 | 65.89 | 20.93 | 8.53 | .310977 | 8514.95 |
| C++ leading comments | 65.89 | 20.16 | 10.08 | .312148 | 8514.86 |

Rust gains six exact FUNCTION instances and loses four; C++ gains one and
loses two. Rust gains one exact LINE instance and loses two; C++ gains three
and loses one. Neither language meets the non-regression requirement, and no
binary endpoint is significant even before family correction. The boundary
ownership fix is mechanically valid but does not justify changing retrieval
defaults: changing boundaries also changes lexical scoring and packing.

The paired reports' local correction covers this candidate alone. Final
selection uses all seven discovery candidates through `lab/e61_family.py`.
No remaining-language replication or Verified gate is warranted for E60.

Reproduce with the E56 scoring environment:

```sh
python lab/e60_run.py --slice rust --baseline /path/to/baseline \
  --experiment /path/to/leading-comments --out /tmp/e60
python lab/e51_score.py /tmp/e60/rust_manifest.json
python lab/e51_compare.py /tmp/e60/rust_manifest.json
```

Repeat for `cpp`. `smoke/` contains execution checks, not an independent
discovery sample. Manifests record hashes, input membership, flags, and
completion; scoring metadata identifies the unchanged helper versions.
