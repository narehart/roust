#!/usr/bin/env python3
"""E26 census: where can --ext-v2 possibly act, and how much gold does it unlock?

Two questions, both answered from the bench parquets + the clones, never from
a list of languages that exist:

  1. INERTNESS. For every instance's base_commit, does the tree contain ANY
     file with an EXT_V2 suffix? If no commit in a slice does, the flag cannot
     change a byte there and the slice needs no arm (this is the go proof).
  2. CEILING. Of each slice's gold files (parsed from the gold patch), how many
     carry an EXT_V2 suffix? Those are files roust cannot retrieve at ANY rank
     with the flag off, because they are never indexed. That count is the
     ceiling --ext-v2 is trying to recover.

Usage: e26_census.py --slice NAME --parquet P --repos-dir D [--no-tree-scan]
"""
from __future__ import annotations
import argparse, collections, json, pathlib, re, subprocess, sys

EXT_V2 = (".rb", ".pony", ".svelte", ".mjs", ".cjs", ".cts", ".mts", ".vue", ".scala", ".php")
GOLD_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.M)


def gold_files(patch: str) -> list[str]:
    return sorted({m.group(2) for m in GOLD_RE.finditer(patch or "")})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", required=True)
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--repos-dir", required=True)
    ap.add_argument("--no-tree-scan", action="store_true",
                    help="skip the per-base_commit ls-tree pass (question 1)")
    ap.add_argument("--out", type=pathlib.Path)
    a = ap.parse_args()

    import pandas as pd
    d = pd.read_parquet(a.parquet)
    repos_dir = pathlib.Path(a.repos_dir)

    gold_total = 0
    gold_ext = collections.Counter()
    inst_with_ext_gold: list[dict] = []
    for _, row in d.iterrows():
        gfs = gold_files(row["patch"])
        gold_total += len(gfs)
        hit = [f for f in gfs if f.endswith(EXT_V2)]
        for f in hit:
            gold_ext["." + f.rsplit(".", 1)[-1]] += 1
        if hit:
            inst_with_ext_gold.append({"instance_id": row["instance_id"],
                                        "n_gold": len(gfs), "ext_gold": hit})

    tree = {}
    if not a.no_tree_scan:
        for repo, grp in d.groupby(d["instance_id"].str.rsplit("-", n=1).str[0]):
            p = repos_dir / repo
            if not p.exists():
                tree[repo] = "REPO_DIR_MISSING"
                continue
            n_commits_with, n_commits = 0, 0
            for c in sorted(set(grp["base_commit"])):
                r = subprocess.run(["git", "-C", str(p), "ls-tree", "-r", "--name-only", c],
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    continue
                n_commits += 1
                if any(l.endswith(EXT_V2) for l in r.stdout.splitlines()):
                    n_commits_with += 1
            tree[repo] = {"base_commits": n_commits, "with_ext_v2_files": n_commits_with}

    res = {"slice": a.slice, "instances": int(len(d)),
           "gold_files_total": gold_total,
           "gold_files_ext_v2": int(sum(gold_ext.values())),
           "gold_ext_v2_by_suffix": dict(gold_ext),
           "instances_with_ext_v2_gold": len(inst_with_ext_gold),
           "per_repo_tree_scan": tree,
           "detail": inst_with_ext_gold}
    txt = json.dumps(res, indent=2)
    if a.out:
        a.out.write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
