"""Headroom diagnostic: SCORE-PROPAGATION RERANK (heat-kernel / RP3beta-style
degree exponents) on bgrep's residual SWE-bench Lite File@10 misses.

Hypothesis: propagating lexical (BM25) evidence 1-2 steps over the file
import/same-dir graph, with a TUNED destination-degree exponent (RP3beta-
style: divide incoming mass at node j by indegree(j)**beta) and/or a small-t
heat-kernel diffusion, discriminates the true fix file from its same-
directory siblings well enough to pull it into the top-3 of a local re-rank
against the top-10 files bgrep currently returns.

CORPUS RECONSTRUCTION (rev-based, no working-tree mutation -- see project
constraint: another agent owns checkouts of these shared clones, so this
script never runs `git checkout`/`git clean`, only `git archive <rev>`,
which reads the object database and touches no index/working file):

  For each instance: `git archive --format=tar <base_commit> -- <ext globs>`
  in the shared clone under swebench_repos/<owner>__<repo>, piped straight
  into an in-memory tarfile (no disk extraction). Members are filtered with
  the SAME predicates lanes3.Corpus.__init__ applies when walking a real
  checkout (extension in CODE_EXTENSIONS, not vendor/minified per _VENDOR_RE,
  <= MAX_FILE_BYTES, no line over _MAX_LINE_CHARS chars, non-empty token
  set) -- see build_corpus_at_rev() below. The resulting {rel: text} dict is
  then used to populate a lanes3.Corpus object's fields DIRECTLY (bypassing
  Corpus.__init__, which insists on `repo_path.rglob(...)`) -- i.e. this
  reuses lanes3.Corpus.bm25() and lanes3.build_import_graph() verbatim on an
  in-memory-populated Corpus, per the task's preferred branch ("compute with
  lanes2's Corpus if importable on in-memory texts"). lanes2.py and
  lanes3.py are byte-identical in the Corpus/bm25/build_import_graph regions
  (diffed before writing this script), so this is faithful to whichever
  lane module actually produced abl_bridges_v7.jsonl (lanes3, per
  swebench_driver3.py).

  Corpus.repo_path is set to a nonexistent dummy path so build_import_graph's
  tsconfig.json lookup (_load_tsconfig_paths) is a guaranteed no-op rather
  than reading tsconfig.json out of the CURRENT (HEAD) working tree of the
  shared clone, which would leak non-rev-based state. This is a no-op for
  every instance here anyway: SWE-bench Lite's 12 repos are all pure Python,
  so CODE_EXTENSIONS only ever matches *.py in this corpus and the JS/TS
  import-resolution branch (the only consumer of repo_path) never fires.
  [flagged, but inert for this dataset]

SEED VECTOR: terms = lanes3.query_terms(problem_statement, []) (no helper
keywords, matching swebench_driver3.run_instance's exact call), seed =
corpus.bm25(terms) sum-normalized to 1 (only BM25-nonzero files get mass).

GRAPH: combined adjacency = lanes3.build_import_graph(corpus) UNION
same-directory edges (same construction select_files() uses: files sharing
Path(rel).parent are pairwise linked), both unweighted/undirected.

PROPAGATION (config sweep):
  A_hat @ s, one step:
    raw[j] = sum_i s[i] / deg(i)        (sender/column-normalized: mass at i
                                          divided evenly among i's neighbors;
                                          dangling i with deg(i)==0 holds its
                                          own mass)
    raw[j] /= deg(j) ** beta            (RP3beta destination-degree penalty;
                                          beta=0 is a no-op)
  s_(t+1) = normalize_sum(raw + s_t)    (residual/restart-like connection,
                                          per the task's literal formula)
  Swept beta in {0, 0.3, 0.6, 1.0} x steps in {1, 2} = 8 configs.

  Heat kernel (3-term Taylor of expm(t*(A_norm - I))), A_norm = the beta=0
  (undamped, no destination penalty) column-stochastic operator above:
    expm(t(A-I)) ~= I + t(A-I) + (t^2/2)(A-I)^2
                  = (1 - t + t^2/2)*s + (t - t^2)*(A@s) + (t^2/2)*(A@A@s)
  t in {0.3, 0.7} = 2 more configs. [assumption: A_norm for the heat kernel
  is the undamped beta=0 operator, not a beta-penalized one -- the task
  introduces the heat kernel as a separate, single well-defined diffusion
  operator, not as another beta-swept arm; flagged]

DISCRIMINATIVE TEST: every one of the 52 File@10 failures in
results_swebench/abl_bridges_v7.jsonl has exactly one gold file, and it is
always the sole missing file (n_gold==1 for all 300 instances; verified).
mini-corpus = {gold} union top-10 returned_files (11 files, gold not already
in top-10 by definition of the failure). Rank the mini-corpus by the
propagated score s'; HEADROOM (per instance, per config) = gold's rank in
{1,2,3}. CONTROL: same test on the (up to) 10 lowest-instance_id PASSING
instances (gold already in top10; usually rank 1).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tarfile
import time
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import Path

LAB_DIR = Path("/Users/nicholasarehart/programming-projects/bgrep/lab")
sys.path.insert(0, str(LAB_DIR))
from lanes3 import (  # noqa: E402
    Corpus, CODE_EXTENSIONS, MAX_FILE_BYTES, _MAX_LINE_CHARS, _VENDOR_RE,
    tokenize, path_tokens, query_terms, build_import_graph,
)

RESULTS = LAB_DIR / "results_swebench" / "abl_bridges_v7.jsonl"
SCRATCH = Path(
    "/private/tmp/claude-501/-Users-nicholasarehart-programming-projects-bgrep/"
    "3ab12e71-fab2-4a81-bb2b-84700d211ef2/scratchpad/bgrep_lab"
)
PARQUET = SCRATCH / "swebench_lite.parquet"
REPOS_DIR = SCRATCH / "swebench_repos"
OUT_DIR = SCRATCH / "propdiag"

CONTROL_N = 10
BETAS = [0.0, 0.3, 0.6, 1.0]
STEP_COUNTS = [1, 2]
HEAT_TS = [0.3, 0.7]
_DUMMY_REPO_PATH = Path("/nonexistent-propdiag-dummy-path")


# ---------------------------------------------------------------- rev-based corpus build

def _archive_bytes(repo_dir: Path, rev: str) -> bytes | None:
    # No pathspec filtering: `git archive` treats a pathspec that matches
    # zero files in a given tree as a fatal error (varies per-repo/rev which
    # extensions are even present), so the safe approach is to archive the
    # whole tree and filter by extension in Python (see build_corpus_at_rev).
    r = subprocess.run(
        ["git", "archive", "--format=tar", rev],
        cwd=repo_dir, capture_output=True, timeout=180,
    )
    if r.returncode != 0:
        return None
    return r.stdout


def build_corpus_at_rev(repo_dir: Path, rev: str) -> Corpus | None:
    """Rev-based reconstruction of a lanes3.Corpus, via `git archive` (no
    checkout/working-tree touch) instead of Corpus.__init__'s rglob. Filters
    mirror Corpus.__init__ exactly (extension already narrowed by the
    archive pathspec; vendor/size/line-length/empty-token checks applied
    here). Bypasses __init__ via Corpus.__new__ + direct field assignment,
    then reuses Corpus.bm25()/build_import_graph() unmodified."""
    raw = _archive_bytes(repo_dir, rev)
    if raw is None:
        return None
    files: list[str] = []
    text: dict[str, str] = {}
    with tarfile.open(fileobj=BytesIO(raw)) as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            rel = member.name
            if Path(rel).suffix not in CODE_EXTENSIONS:
                continue
            if rel.startswith(".git/") or "/.git/" in rel:
                continue
            if _VENDOR_RE.search(rel):
                continue
            if member.size > MAX_FILE_BYTES:
                continue
            fh = tf.extractfile(member)
            if fh is None:
                continue
            raw_bytes = fh.read()
            try:
                txt = raw_bytes.decode("utf-8", errors="replace")
            except Exception:
                continue
            lines = txt.splitlines()
            if lines and max(len(ln) for ln in lines) > _MAX_LINE_CHARS:
                continue
            toks = tokenize(txt)
            if not toks:
                continue
            files.append(rel)
            text[rel] = txt

    c = Corpus.__new__(Corpus)
    c.repo_path = _DUMMY_REPO_PATH
    c.files = files
    c.text = text
    c.ptoks = {rel: path_tokens(rel) for rel in files}
    c.tf = {}
    c.doclen = {}
    c.df = Counter()
    for rel in files:
        counts = Counter(tokenize(text[rel]))
        c.tf[rel] = counts
        c.doclen[rel] = sum(counts.values())
        for term in counts:
            c.df[term] += 1
    c.use_comments = False
    c.com_tf = {}
    c.com_df = Counter()
    c.def_index = defaultdict(list)
    c.n_docs = len(files)
    c.avg_len = (sum(c.doclen.values()) / c.n_docs) if c.n_docs else 1.0
    c.n_com_docs = 0
    c.msg_tf = {}
    c.msg_df = Counter()
    c.msg_doclen = {}
    c.n_msg_docs = 0
    c.msg_avg_len = 1.0
    c.docs_files = []
    c.docs_text = {}
    c.docs_tf = {}
    c.docs_df = Counter()
    c.docs_len = {}
    c.n_docs_files = 0
    c.docs_avg_len = 1.0
    return c


def build_combined_graph(corpus: Corpus) -> dict[str, set[str]]:
    edges = build_import_graph(corpus)
    combined: dict[str, set[str]] = defaultdict(set)
    for a, nbrs in edges.items():
        combined[a] |= nbrs
    same_dir: dict[str, list[str]] = defaultdict(list)
    for rel in corpus.files:
        same_dir[str(Path(rel).parent)].append(rel)
    for members in same_dir.values():
        if len(members) < 2:
            continue
        for a in members:
            for b in members:
                if a != b:
                    combined[a].add(b)
    return dict(combined)


# ---------------------------------------------------------------- propagation

def normalize_sum(v: dict[str, float]) -> dict[str, float]:
    total = sum(v.values())
    if total <= 0:
        return dict(v)
    return {k: val / total for k, val in v.items()}


def propagate_step(
    s: dict[str, float], graph: dict[str, set[str]], degree: dict[str, int], beta: float,
) -> dict[str, float]:
    raw: dict[str, float] = defaultdict(float)
    for i, si in s.items():
        if si <= 0:
            continue
        nbrs = graph.get(i)
        if not nbrs:
            raw[i] += si  # dangling: hold mass at self
            continue
        share = si / len(nbrs)
        for j in nbrs:
            raw[j] += share
    if beta > 0:
        for j in list(raw.keys()):
            d = degree.get(j, 0)
            if d > 0:
                raw[j] = raw[j] / (d ** beta)
    return dict(raw)


def run_beta_steps(
    seed: dict[str, float], graph: dict[str, set[str]], degree: dict[str, int],
    beta: float, steps: int,
) -> dict[str, float]:
    s = dict(seed)
    for _ in range(steps):
        raw = propagate_step(s, graph, degree, beta)
        merged: dict[str, float] = defaultdict(float)
        for k, v in raw.items():
            merged[k] += v
        for k, v in s.items():
            merged[k] += v
        s = normalize_sum(dict(merged))
    return s


def run_heat(
    seed: dict[str, float], graph: dict[str, set[str]], degree: dict[str, int], t: float,
) -> dict[str, float]:
    v0 = dict(seed)
    v1 = propagate_step(v0, graph, degree, 0.0)
    v2 = propagate_step(v1, graph, degree, 0.0)
    c0 = 1 - t + (t ** 2) / 2
    c1 = t - t ** 2
    c2 = (t ** 2) / 2
    keys = set(v0) | set(v1) | set(v2)
    s = {k: c0 * v0.get(k, 0.0) + c1 * v1.get(k, 0.0) + c2 * v2.get(k, 0.0) for k in keys}
    return normalize_sum(s)


CONFIGS: list[tuple[str, dict]] = (
    [(f"beta={b}_steps={st}", {"kind": "beta_steps", "beta": b, "steps": st})
     for st in STEP_COUNTS for b in BETAS]
    + [(f"heat_t={t}", {"kind": "heat", "t": t}) for t in HEAT_TS]
)


def score_config(
    cfg: dict, seed: dict[str, float], graph: dict[str, set[str]], degree: dict[str, int],
) -> dict[str, float]:
    if cfg["kind"] == "beta_steps":
        return run_beta_steps(seed, graph, degree, cfg["beta"], cfg["steps"])
    return run_heat(seed, graph, degree, cfg["t"])


def rank_of(target: str, mini_files: list[str], scores: dict[str, float]) -> int:
    ordered = sorted(mini_files, key=lambda f: (-scores.get(f, 0.0), f))
    return ordered.index(target) + 1


# ---------------------------------------------------------------- data loading

def load_targets_and_controls():
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines()]
    rows = [r for r in rows if "error" not in r]
    fail10 = sorted(
        (r for r in rows if not (set(r["gold_files"]) <= set(r["returned_files"][:10]))),
        key=lambda r: r["instance_id"],
    )
    passing = sorted(
        (r for r in rows if set(r["gold_files"]) <= set(r["returned_files"][:10])),
        key=lambda r: r["instance_id"],
    )[:CONTROL_N]
    assert all(r["n_gold"] == 1 for r in rows), "assumption violated: not all instances have n_gold==1"
    return fail10, passing


def repo_dir_for(repo_slug: str) -> Path:
    return REPOS_DIR / repo_slug.replace("/", "__")


# ---------------------------------------------------------------- main

def process_instance(r: dict, meta_row, log: list[str]) -> dict | None:
    iid = r["instance_id"]
    repo_slug = r["repo"]
    rev = meta_row["base_commit"]
    repo_dir = repo_dir_for(repo_slug)
    if not (repo_dir / ".git").exists():
        log.append(f"[{iid}] SKIP: no local clone at {repo_dir}")
        return None
    corpus = build_corpus_at_rev(repo_dir, rev)
    if corpus is None or corpus.n_docs == 0:
        log.append(f"[{iid}] SKIP: corpus build failed / empty at rev {rev}")
        return None

    gold = r["gold_files"][0]
    top10 = r["returned_files"][:10]
    mini_files = list(dict.fromkeys([gold] + top10))
    if gold not in corpus.text:
        log.append(f"[{iid}] WARN: gold {gold} absent from reconstructed corpus (filtered out?)")
    missing_from_corpus = [f for f in mini_files if f not in corpus.text]
    if missing_from_corpus:
        log.append(f"[{iid}] WARN: {len(missing_from_corpus)}/{len(mini_files)} mini-corpus "
                    f"files absent from reconstructed corpus: {missing_from_corpus}")

    terms = query_terms(meta_row["problem_statement"], [])
    bm = corpus.bm25(terms)
    seed = normalize_sum(bm)

    graph = build_combined_graph(corpus)
    degree = {f: len(graph.get(f, ())) for f in corpus.files}

    # same-dir-sibling-of-a-top10-file check (target class for the wins-overlap report)
    gold_dir = str(Path(gold).parent)
    top10_dirs = {str(Path(f).parent) for f in top10}
    same_dir_sibling = gold_dir in top10_dirs

    rank0 = rank_of(gold, mini_files, seed)  # no-propagation baseline

    per_config: dict[str, dict] = {}
    for name, cfg in CONFIGS:
        s = score_config(cfg, seed, graph, degree)
        rk = rank_of(gold, mini_files, s)
        per_config[name] = {"rank": rk, "headroom": rk <= 3, "score": round(s.get(gold, 0.0), 6)}

    return {
        "instance_id": iid,
        "repo": repo_slug,
        "gold": gold,
        "n_mini": len(mini_files),
        "corpus_files": corpus.n_docs,
        "same_dir_sibling_of_top10": same_dir_sibling,
        "rank0_no_propagation": rank0,
        "per_config": per_config,
    }


def process_control_instance(r: dict, meta_row, log: list[str]) -> dict | None:
    """Same pipeline as process_instance, but gold is ALREADY in top-10 (this
    is a passing instance) -- tests whether propagation disturbs a working
    case, not whether it fixes a broken one."""
    return process_instance(r, meta_row, log)


def main() -> None:
    import pandas as pd

    t0 = time.time()
    fail10, control = load_targets_and_controls()
    meta = pd.read_parquet(PARQUET).set_index("instance_id")
    print(f"fail10 (target): {len(fail10)}  control (passing): {len(control)}", flush=True)

    log: list[str] = []
    target_results: list[dict] = []
    for k, r in enumerate(fail10, 1):
        m = meta.loc[r["instance_id"]]
        res = process_instance(r, m, log)
        if res:
            target_results.append(res)
        if k % 10 == 0 or k == len(fail10):
            print(f"  target progress {k}/{len(fail10)} ({time.time()-t0:.0f}s)", flush=True)

    control_results: list[dict] = []
    for k, r in enumerate(control, 1):
        m = meta.loc[r["instance_id"]]
        res = process_control_instance(r, m, log)
        if res:
            control_results.append(res)
        print(f"  control progress {k}/{len(control)} ({time.time()-t0:.0f}s)", flush=True)

    wall = time.time() - t0
    print(f"corpus/graph builds done in {wall:.0f}s "
          f"({len(target_results)}/{len(fail10)} target, {len(control_results)}/{len(control)} control)",
          flush=True)

    # -------------------------------------------------------------- aggregate

    config_names = [name for name, _ in CONFIGS]
    target_headroom = {name: sum(1 for t in target_results if t["per_config"][name]["headroom"])
                        for name in config_names}
    control_headroom = {name: sum(1 for t in control_results if t["per_config"][name]["headroom"])
                         for name in config_names}
    baseline_target_headroom = sum(1 for t in target_results if t["rank0_no_propagation"] <= 3)
    baseline_control_headroom = sum(1 for t in control_results if t["rank0_no_propagation"] <= 3)

    # best config: maximize target headroom; tie-break by control preservation
    best_name = max(
        config_names,
        key=lambda n: (target_headroom[n], control_headroom[n]),
    )

    n_target = len(target_results)
    n_control = len(control_results)
    n_sibling = sum(1 for t in target_results if t["same_dir_sibling_of_top10"])

    print("\n" + "=" * 90)
    print("CONFIG SWEEP -- target (52 File@10 failures) headroom (gold enters top-3 of "
          "{gold}+top10 local re-rank)")
    print("=" * 90)
    print(f"{'config':<20}{'target_headroom':>18}{'/'+str(n_target):<6}"
          f"{'control_headroom':>18}{'/'+str(n_control):<6}")
    print(f"{'(no propagation)':<20}{baseline_target_headroom:>18}{'/'+str(n_target):<6}"
          f"{baseline_control_headroom:>18}{'/'+str(n_control):<6}")
    for name in config_names:
        marker = "  <== BEST" if name == best_name else ""
        print(f"{name:<20}{target_headroom[name]:>18}{'/'+str(n_target):<6}"
              f"{control_headroom[name]:>18}{'/'+str(n_control):<6}{marker}")

    best_cfg_targets = [t for t in target_results if t["per_config"][best_name]["headroom"]]
    n_best_sibling_wins = sum(1 for t in best_cfg_targets if t["same_dir_sibling_of_top10"])

    print(f"\nBEST CONFIG: {best_name}")
    print(f"  target headroom: {target_headroom[best_name]}/{n_target} "
          f"({100*target_headroom[best_name]/n_target:.1f}%)  "
          f"[baseline no-propagation: {baseline_target_headroom}/{n_target}]")
    print(f"  control headroom (still top-3): {control_headroom[best_name]}/{n_control} "
          f"[baseline: {baseline_control_headroom}/{n_control}]")
    print(f"  of the {n_target} target instances, {n_sibling} have gold sharing a directory "
          f"with a top-10 file ('same-dir sibling' target class)")
    print(f"  of the {len(best_cfg_targets)} BEST-CONFIG WINS, {n_best_sibling_wins} are in "
          f"that same-dir-sibling class "
          f"({100*n_best_sibling_wins/len(best_cfg_targets):.1f}% of wins)" if best_cfg_targets
          else "  no wins under best config")

    print(f"\n-- per-instance table, BEST CONFIG ({best_name}) -- target set --")
    print(f"{'instance_id':<38}{'repo':<24}{'rank0':>6}{'rank_best':>10}{'headroom':>9}{'sibling':>9}")
    for t in target_results:
        pc = t["per_config"][best_name]
        print(f"{t['instance_id']:<38}{t['repo']:<24}{t['rank0_no_propagation']:>6}"
              f"{pc['rank']:>10}{str(pc['headroom']):>9}{str(t['same_dir_sibling_of_top10']):>9}")

    print(f"\n-- per-instance table, BEST CONFIG ({best_name}) -- control set --")
    print(f"{'instance_id':<38}{'repo':<24}{'rank0':>6}{'rank_best':>10}{'headroom':>9}")
    for t in control_results:
        pc = t["per_config"][best_name]
        print(f"{t['instance_id']:<38}{t['repo']:<24}{t['rank0_no_propagation']:>6}"
              f"{pc['rank']:>10}{str(pc['headroom']):>9}")

    print("\n-- FULL per-instance x per-config rank table -- target set --")
    header = "instance_id".ljust(38) + "".join(n[:16].rjust(17) for n in config_names)
    print(header)
    for t in target_results:
        row = t["instance_id"].ljust(38) + "".join(
            str(t["per_config"][n]["rank"]).rjust(17) for n in config_names
        )
        print(row)

    print("\n-- FULL per-instance x per-config rank table -- control set --")
    print(header)
    for t in control_results:
        row = t["instance_id"].ljust(38) + "".join(
            str(t["per_config"][n]["rank"]).rjust(17) for n in config_names
        )
        print(row)

    # -------------------------------------------------------------- write outputs
    OUT_DIR.mkdir(exist_ok=True)
    report = {
        "n_target": n_target,
        "n_control": n_control,
        "baseline_target_headroom": baseline_target_headroom,
        "baseline_control_headroom": baseline_control_headroom,
        "target_headroom_by_config": target_headroom,
        "control_headroom_by_config": control_headroom,
        "best_config": best_name,
        "n_same_dir_sibling_targets": n_sibling,
        "n_best_config_wins": len(best_cfg_targets),
        "n_best_config_wins_same_dir_sibling": n_best_sibling_wins,
        "target_results": target_results,
        "control_results": control_results,
        "wall_s": round(wall, 1),
    }
    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2, default=str))
    (OUT_DIR / "run_log.txt").write_text("\n".join(log))
    print(f"\nwrote {OUT_DIR / 'report.json'}")
    print(f"wall time: {wall:.0f}s")


if __name__ == "__main__":
    main()
