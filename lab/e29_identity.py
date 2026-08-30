"""E29 arm-identity gate: do this round's two REPLICATED arms reproduce the
stored E27 / E28 records they are supposed to be re-runs of?

E29 restricts every arm to the >=3-gold-file stratum via `--instances`. Two of
its four arms are, by construction, re-runs of arms that already exist:

  a1 (cap 16, budget 8192) -- the shipped default. Both harness sentinels mean
     "forward no flag at all", so a1's argv is byte-identical to E27's `_s0`
     default arms', and a1 must reproduce their records on the 618 stratum ids.
  a2 (cap 32, budget 8192) -- E28's `_m32` arm, same reasoning.

This gate therefore tests THREE things at once, and it is the reason the round
can be believed:

  1. the ported `--instances` allowlist selects instances without perturbing
     them (an instance's bundle must not depend on which other instances ran);
  2. the `--budget` passthrough is genuinely inert at its 0 sentinel (a1/a2
     pass no --budget, and rev.BUDGET stays 8192);
  3. the clone directories used this round hold the same corpus as the ones
     E27/E28 used -- E28's anomaly log records a dir that silently held 4 of 9
     jsts repos, which would otherwise score a partial corpus against a full one.

Unlike E28's gate, which sampled, this one compares the WHOLE stratum: every
one of the 618 ids, in both replicated arms.

What is compared is the PAYLOAD, never raw JSON. The engine's `stats` block
carries `index_ms`/`query_ms`, so a reference binary differs from *itself*
between runs; comparing raw JSON produces false failures. The comparison is on
the fields that ARE the payload: `regions` (the returned file -> spans map),
`tokens` (the packed size), and the derived metrics, which are pure functions
of regions + gold.

Usage:
  uv run --no-project python lab/e29_identity.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

R = Path("/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions")
E27, E28, E29 = R / "e27", R / "e28", R / "e29"

SLICES = ["jsts", "java", "go", "rust", "c", "cpp", "ver"]

# (this round's arm tag, the stored reference it replicates)
REPLICATED = (
    ("a1_c16b8192", lambda s: E27 / f"{s}_s0.jsonl"),
    ("a2_c32b8192", lambda s: E28 / "arms" / f"{s}_m32.jsonl"),
)

# The payload + everything derived from it. Deliberately EXCLUDES engine_sha,
# engine_dirty, shard, and the per-round flag-provenance keys (max_additions,
# budget), which are expected to differ in the RECORD even when the engine
# behaviour they describe is identical.
PAYLOAD_KEYS = ("regions", "tokens", "hunk_file_covered", "hunk_line_recall",
                "hunk_touched", "all_gold_files_retrieved", "n_gold_files",
                "n_gold_hunks", "error")


def load(path: Path) -> dict[str, dict]:
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["instance_id"]] = r
    return out


def main() -> int:
    total_cmp = 0
    total_diff = 0
    results = {}
    ok = True
    for arm_tag, ref_for in REPLICATED:
        print(f"\n=== {arm_tag} vs its stored reference ===")
        print(f"{'slice':6} {'expected':>9} {'compared':>9} {'identical':>10} "
              f"{'differ':>7}  verdict")
        for s in SLICES:
            new_p = E29 / "arms" / f"{s}_{arm_tag}.jsonl"
            old_p = ref_for(s)
            want = len((E29 / "instances" / f"{s}.txt").read_text().split())
            if not new_p.exists() or not old_p.exists():
                print(f"{s:6} {want:>9} {'-':>9} {'-':>10} {'-':>7}  MISSING")
                results[f"{arm_tag}/{s}"] = "MISSING"
                ok = False
                continue
            new, old = load(new_p), load(old_p)
            ids = sorted(set(new) & set(old))
            diffs = []
            for i in ids:
                for k in PAYLOAD_KEYS:
                    if new[i].get(k) != old[i].get(k):
                        diffs.append((i, k))
                        break
            # The arm must cover the whole stratum, and every stratum id must
            # be present in the reference: a short run is a failure, not a
            # smaller-but-clean comparison.
            complete = (len(new) == want and len(ids) == want)
            if complete and not diffs:
                verdict = "IDENTICAL"
            elif not complete:
                verdict = f"INCOMPLETE (arm={len(new)} common={len(ids)})"
                ok = False
            else:
                verdict = "DIFFER"
                ok = False
            total_cmp += len(ids)
            total_diff += len(diffs)
            results[f"{arm_tag}/{s}"] = verdict
            print(f"{s:6} {want:>9} {len(ids):>9} {len(ids) - len(diffs):>10} "
                  f"{len(diffs):>7}  {verdict}")
            for i, k in diffs[:5]:
                print(f"         first diff: {i} on {k!r}")

    print(f"\ncompared {total_cmp} records across {len(SLICES)} slices x "
          f"{len(REPLICATED)} replicated arms; {total_diff} payload differences")
    print(f"ARM IDENTITY: {'PASS' if ok else 'FAIL'} -- "
          + ("--instances is inert, --budget's sentinel is inert, and the clone "
             "dirs match E27/E28's" if ok
             else "the round's provenance is NOT established; do not report results"))
    (E29 / "identity_verdict.json").write_text(json.dumps(
        {"per_arm_slice": results, "records_compared": total_cmp,
         "payload_differences": total_diff, "pass": ok,
         "payload_keys": list(PAYLOAD_KEYS)}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
