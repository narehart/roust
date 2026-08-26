"""WS2c Gate 2 pre-check (campaign #56): per-instance tree census of the new
VENDOR_RE alternates over Lite-300 + Verified-407 base commits.

For every instance, `git ls-tree -r --name-only <base_commit>` in a private
clone, then:
  default_hits : files with a DEFAULT CODE_EXTENSIONS suffix whose path
                 matches the new alternates. If 0 across all instances, the
                 default walk is provably unchanged by the VENDOR_RE
                 extension on every bench instance (justifies reusing the
                 WS2b Verified base arm).
  cfam_hits    : C-family-suffix files matching the new alternates (what the
                 guard newly excludes under --cfamily-ext).

Read-only over the clones (ls-tree; no checkout, no .roust touched).
"""
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

LAB = Path(__file__).resolve().parent
NEW_RE = re.compile(r"(?i)((^|/)(cextern|extern)(/|$)|(^|/)(libsvm|liblinear)(/|$))")
DEFAULT_EXT = (".py", ".ts", ".js", ".go", ".rs", ".java", ".kt", ".cs", ".swift", ".tsx", ".jsx")
CFAM_EXT = (".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh")

bench, clones = sys.argv[1], Path(sys.argv[2])
f = {"lite": "swebench_lite.parquet", "verified": "swebench_verified_heldout.parquet"}[bench]
df = pd.read_parquet(LAB / f)

tree_cache: dict[tuple[str, str], list[str]] = {}
default_hits: list[tuple[str, str]] = []
cfam_counter: Counter = Counter()
cfam_instances = 0
for _, row in df.iterrows():
    slug = row["repo"].replace("/", "__")
    key = (slug, row["base_commit"])
    if key not in tree_cache:
        p = subprocess.run(["git", "ls-tree", "-r", "--name-only", row["base_commit"]],
                           cwd=clones / slug, capture_output=True, text=True, check=True)
        tree_cache[key] = p.stdout.splitlines()
    dh = [x for x in tree_cache[key] if x.endswith(DEFAULT_EXT) and NEW_RE.search(x)]
    ch = [x for x in tree_cache[key] if x.endswith(CFAM_EXT) and NEW_RE.search(x)]
    for x in dh:
        default_hits.append((row["instance_id"], x))
    if ch:
        cfam_instances += 1
    cfam_counter[slug] += len(ch)

print(f"[{bench}] n={len(df)} unique trees={len(tree_cache)}")
print(f"default-suffix file hits under new-excluded dirs (instance,file pairs): {len(default_hits)}")
inst_by_repo: Counter = Counter()
paths: Counter = Counter()
for iid, x in default_hits:
    inst_by_repo[iid.rsplit("-", 1)[0]] += 1
    paths[x] += 1
print(f"  instances affected: {len({i for i, _ in default_hits})}, by repo-prefix: {dict(inst_by_repo)}")
print(f"  unique paths: {len(paths)}; sample: {sorted(paths)[:15]}")
print(f"instances with cfamily files under new-excluded dirs: {cfam_instances}")
print("cfamily excluded-file totals by repo (summed over instances):")
for slug, n in sorted(cfam_counter.items()):
    if n:
        print(f"    {slug}: {n}")
sys.exit(1 if default_hits else 0)
