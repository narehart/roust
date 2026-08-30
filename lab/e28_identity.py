"""E28 default-arm identity gate: is main's engine payload-identical to the
engine that produced E27's stored `_s0` default arms?

E28 wants to reuse E27's `_s0` arms as its default side rather than spend a
wave re-running them. That is only legitimate if the two engines agree on the
DEFAULT path. E27's binary was `d5263f6` = the E27 implementation `6e28c76`
plus two measurement-only commits; `6e28c76`'s parent is `ca15227`, E26's
.rb/.pony adoption, whose engine source is identical to main's `3eb8f78`
landing of the same work (`git diff ca15227 3eb8f78 -- roust-rs/src/` is
empty). So structurally the default path should not have moved. This script
does not take that on faith -- it MEASURES it.

What is compared is the PAYLOAD, never raw JSON. The engine's `stats` block
carries `index_ms`/`query_ms`, so a reference binary differs from *itself*
between runs; an earlier campaign round produced a false "DIFFER" that way.
The comparison here is on the per-record fields that ARE the payload:

  * `regions`      -- the returned file -> spans map, i.e. the bundle content
  * `tokens`       -- stats.bundle_tokens, the packed size
  * the derived metrics (hunk_file_covered / hunk_line_recall / hunk_touched /
    all_gold_files_retrieved), which are pure functions of regions + gold

A pass means E27's `_s0` records are a valid default side for E28's arms; a
fail means fresh default arms must be run.

Usage:
  uv run --no-project python lab/e28_identity.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

E27 = Path("/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e27")
E28 = Path("/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e28/idcheck")

SLICES = ["jsts", "java", "go", "rust", "c", "cpp", "lite", "ver"]

# The payload + everything derived from it. Deliberately EXCLUDES engine_sha,
# engine_dirty, shard, and the per-round flag-provenance keys, which are
# expected to differ and are not part of what the engine returns.
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
    print(f"{'slice':6} {'compared':>9} {'identical':>10} {'differ':>7}  verdict")
    per_slice = {}
    for s in SLICES:
        new_p = E28 / f"{s}_def.jsonl"
        old_p = E27 / f"{s}_s0.jsonl"
        if not new_p.exists() or not old_p.exists():
            print(f"{s:6} {'-':>9} {'-':>10} {'-':>7}  MISSING ({new_p.name} / {old_p.name})")
            per_slice[s] = "MISSING"
            continue
        new, old = load(new_p), load(old_p)
        ids = sorted(set(new) & set(old))
        diffs = []
        for i in ids:
            for k in PAYLOAD_KEYS:
                if new[i].get(k) != old[i].get(k):
                    diffs.append((i, k))
                    break
        total_cmp += len(ids)
        total_diff += len(diffs)
        verdict = "IDENTICAL" if not diffs else "DIFFER"
        per_slice[s] = verdict
        print(f"{s:6} {len(ids):>9} {len(ids) - len(diffs):>10} {len(diffs):>7}  {verdict}")
        for i, k in diffs[:5]:
            print(f"         first diff: {i} on {k!r}")

    ok = total_diff == 0 and all(v == "IDENTICAL" for v in per_slice.values())
    print(f"\ncompared {total_cmp} records across {len(SLICES)} slices; "
          f"{total_diff} payload differences")
    print(f"DEFAULT-ARM IDENTITY: {'PASS' if ok else 'FAIL'} -- "
          f"{'E27 _s0 arms are a valid default side for E28' if ok else 'fresh default arms REQUIRED'}")
    Path(E28 / "identity_verdict.json").write_text(json.dumps(
        {"per_slice": per_slice, "records_compared": total_cmp,
         "payload_differences": total_diff, "pass": ok,
         "payload_keys": list(PAYLOAD_KEYS)}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
