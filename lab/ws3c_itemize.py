"""WS3c per-instance itemization between a base and a v2 arm (issue #56).

For every instance where ANYTHING changed (FILE flag, LINE all-or-nothing,
fraction, FUNCTION verdict, or the packed regions differ), print: metric
deltas, gold files, gold rank in the packed-file order before/after, and a
region-diff summary (files entering/leaving the pack; span changes on
shared files).

With --repos-dir and --bin, additionally re-runs the engine per changed
instance (defaults AND --symbols-v2, --explain) and prints the
anchor_promotions of each -- the promotions present only under the flag
are exactly "which anchors fired" for WS3c (the def/anchor channel is the
only ranking-side mechanism the flag adds; seating is pack-side and shows
up as the span changes on promoted files).

Usage:
  uv run --no-project --with pandas --with pyarrow python lab/ws3c_itemize.py \
      gold.parquet base.jsonl v2.jsonl \
      [--metrics metric_base.json metric_v2.json] \
      [--repos-dir CLONES --bin ROUST] [--only INSTANCE_ID ...]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def load(p):
    recs = {}
    with open(p) as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                recs[r["instance_id"]] = r
    return recs


def gold_files(patch):
    return sorted({m.group(2) for m in
                   re.finditer(r"^diff --git a/(\S+) b/(\S+)", patch or "", re.M)})


def func_detail(metric_path):
    with open(metric_path) as fh:
        d = json.load(fh)
    det = d["all_instances"]["function"].get("detail") or \
        d.get("file_correct_subset", {}).get("function", {}).get("detail", [])
    return {r["instance_id"]: r["correct"] for r in det}


def gold_rank(rec, gold):
    files = list((rec.get("regions") or {}).keys())
    for i, f in enumerate(files):
        if f in gold:
            return i + 1
    return None


def region_diff(a, b):
    ra, rb = a.get("regions") or {}, b.get("regions") or {}
    added = sorted(set(rb) - set(ra))
    removed = sorted(set(ra) - set(rb))
    respanned = sorted(f for f in set(ra) & set(rb) if ra[f] != rb[f])
    return added, removed, respanned


def explain_anchors(binary, clones, slug, sha, query, extra=()):
    rp = Path(clones) / slug
    subprocess.run(["git", "checkout", "-f", sha], cwd=rp, check=True, capture_output=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=rp, check=True, capture_output=True)
    shutil.rmtree(rp / ".roust", ignore_errors=True)
    p = subprocess.run([str(binary), "--json", "--budget", "8192", "--explain",
                        query, str(rp), *extra],
                       capture_output=True, text=True, timeout=1800)
    err = p.stderr
    a, b = err.find("{"), err.rfind("}")
    if a < 0 or p.returncode not in (0, 1):
        return f"__ERROR__ exit {p.returncode}"
    try:
        return json.loads(err[a:b + 1]).get("anchor_promotions", [])
    except json.JSONDecodeError:
        return "__ERROR__ bad explain json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gold_parquet")
    ap.add_argument("base_jsonl")
    ap.add_argument("v2_jsonl")
    ap.add_argument("--metrics", nargs=2, default=None,
                    help="metric_base.json metric_v2.json (FUNCTION verdicts)")
    ap.add_argument("--repos-dir", default=None,
                    help="clones dir for --explain anchor reruns (PRIVATE copy)")
    ap.add_argument("--bin", default=None, help="branch roust binary for reruns")
    ap.add_argument("--only", nargs="*", default=None,
                    help="restrict to these instance ids (still requires presence in both arms)")
    ap.add_argument("--metric-only", action="store_true",
                    help="itemize only instances whose METRICS changed (skip the "
                         "pack-only churn; keeps --explain reruns affordable)")
    args = ap.parse_args()

    import pandas as pd
    gold_df = pd.read_parquet(args.gold_parquet)
    gold_map, meta = {}, {}
    for _, r in gold_df.iterrows():
        gold_map[r["instance_id"]] = gold_files(r["patch"])
        meta[r["instance_id"]] = (r["repo"].replace("/", "__"), r["base_commit"],
                                  r["problem_statement"])
    a, b = load(args.base_jsonl), load(args.v2_jsonl)
    fa = fb = {}
    if args.metrics:
        fa, fb = func_detail(args.metrics[0]), func_detail(args.metrics[1])

    ids = sorted(set(a) & set(b))
    if args.only:
        ids = [i for i in ids if i in set(args.only)]
    n_changed = 0
    for iid in ids:
        ra, rb = a[iid], b[iid]
        d_file = (ra.get("hunk_file_covered"), rb.get("hunk_file_covered"))
        d_line = (ra.get("hunk_touched"), rb.get("hunk_touched"))
        d_frac = (ra.get("hunk_line_recall") or 0.0, rb.get("hunk_line_recall") or 0.0)
        d_func = (fa.get(iid), fb.get(iid)) if args.metrics else (None, None)
        added, removed, respanned = region_diff(ra, rb)
        metric_changed = (d_file[0] != d_file[1] or d_line[0] != d_line[1]
                          or abs(d_frac[0] - d_frac[1]) > 1e-9 or d_func[0] != d_func[1])
        changed = metric_changed or added or removed or respanned
        if not changed or (args.metric_only and not metric_changed):
            continue
        n_changed += 1
        gold = gold_map.get(iid, [])
        print(f"== {iid}")
        print(f"   FILE {d_file[0]}->{d_file[1]}  LINE {d_line[0]}->{d_line[1]}  "
              f"frac {d_frac[0]:.4f}->{d_frac[1]:.4f}  FUNC {d_func[0]}->{d_func[1]}")
        print(f"   gold={gold}  gold_rank {gold_rank(ra, set(gold))}->{gold_rank(rb, set(gold))}")
        if added or removed:
            print(f"   pack +{added} -{removed}")
        if respanned:
            print(f"   respanned {respanned[:6]}{'...' if len(respanned) > 6 else ''}")
        if args.repos_dir and args.bin and iid in meta:
            slug, sha, q = meta[iid]
            base_anch = explain_anchors(args.bin, args.repos_dir, slug, sha, q)
            v2_anch = explain_anchors(args.bin, args.repos_dir, slug, sha, q,
                                      extra=("--symbols-v2",))
            print(f"   anchors base={base_anch}")
            print(f"   anchors v2  ={v2_anch}")
    print(f"TOTAL changed: {n_changed} / {len(ids)} paired")


if __name__ == "__main__":
    main()
