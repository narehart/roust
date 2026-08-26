"""WS3d fixture-dir tree census (issue #56).

The --displacement-guard filter can only change engine output on an
instance whose checked-out tree contains a path with a `*.test/` or
`*.spec/` DIRECTORY component (otherwise `extract_symbol_anchors` is
structurally identical: the filter never skips anything). This census
checks that predicate EXACTLY, per instance, via `git ls-tree -r
--name-only <base_commit>` -- a pure object-store read (no checkout, no
mutation; safe alongside running arms).

Slices with zero matching instances need no guard arms: byte-identity is
structural. Matching instances are itemized for per-instance
byte-compare micro-checks.

Usage:
  uv run --no-project --with pandas --with pyarrow python \
      lab/ws3d_fixture_census.py SLICE:PARQUET:CLONES_DIR ...
"""

from __future__ import annotations

import re
import subprocess
import sys

FIXTURE_DIR_RE = re.compile(r"(?i)(^|/)[^/]+\.(test|spec)/")


def ls_tree(clones, slug, sha):
    p = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", sha],
        cwd=f"{clones}/{slug}", capture_output=True, text=True)
    if p.returncode != 0:
        return None
    return p.stdout.splitlines()


def main():
    import pandas as pd
    grand_total = 0
    for spec in sys.argv[1:]:
        name, pq, clones = spec.split(":", 2)
        df = pd.read_parquet(pq)
        n_match, n_err = 0, 0
        matches = []
        for _, r in df.iterrows():
            slug = r["repo"].replace("/", "__")
            files = ls_tree(clones, slug, r["base_commit"])
            if files is None:
                n_err += 1
                print(f"  !! {name} {r['instance_id']}: ls-tree failed")
                continue
            hit = sorted({f for f in files if FIXTURE_DIR_RE.search(f)})
            if hit:
                n_match += 1
                matches.append((r["instance_id"], len(hit), hit[:3]))
        print(f"== {name}: {n_match}/{len(df)} instances with fixture-dir paths "
              f"({n_err} ls-tree errors)")
        for iid, n, ex in matches:
            print(f"   {iid}: {n} files, e.g. {ex}")
        grand_total += n_match
    print(f"TOTAL matching instances (excl. jsts full arms): {grand_total}")


if __name__ == "__main__":
    main()
