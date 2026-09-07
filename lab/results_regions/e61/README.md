# E61 shared source: modest C++ coverage gains, no function gain

Candidate `7adc6d6`, baseline `645170a`, original exact language-aware scorer,
requested budget 8192, padding 5, length exponent .85. All 368 flag-off
payloads match and no errors occurred. The full integrity audit verifies that
every original file and source region remains represented, with no token
increase on any instance. Engine tests separately check exact source equality
and explicit location rendering; the audit alone does not inspect aliases.

| Slice / arm | FILE | FUNCTION | LINE | Mean line fraction | Mean actual tokens |
|---|---:|---:|---:|---:|---:|
| Rust baseline, 239 | 60.25 | 20.92 | 7.53 | .248645 | 8464.05 |
| Rust shared source | 60.25 | 20.92 | 7.53 | .248645 | 8462.54 |
| C++ baseline, 129 | 65.89 | 20.93 | 8.53 | .310977 | 8514.95 |
| C++ shared source | 65.89 | 20.93 | 9.30 | .320338 | 8351.71 |

C++ expands represented source in 71 tasks, improves fractional line coverage
in 16, and adds one all-gold LINE success. No task loses coverage. Mean
fraction rises .009362 (descriptive paired bootstrap 95% interval
[.003036, .018138]); mean tokens fall 163.24, or 1.92%. Rust changes three
bundles, saves 362 tokens in total, and changes no recall metric.

There are no exact FUNCTION gains and the single exact LINE gain is not
statistically significant. This is useful evidence for exact-content sharing,
but it does not meet the primary discovery gate or establish language parity.
The mode remains default-off; no Verified test or default adoption follows.
The family-wide report includes all six candidates, not just this experiment.

Reproduce in the E56 scoring environment with the frozen binaries:

```sh
python lab/e61_run.py --slice cpp --baseline /path/to/baseline \
  --experiment /path/to/shared-source --out /tmp/e61
python lab/e61_audit.py /tmp/e61/cpp_manifest.json
python lab/e51_score.py /tmp/e61/cpp_manifest.json
python lab/e51_compare.py /tmp/e61/cpp_manifest.json
```

Repeat for Rust. `discovery/` contains manifests, raw records, integrity
reports, scorer provenance, and paired comparisons. Cost is bounded against
the original actual bundle, not a claim of strict 8192-token rendering.
