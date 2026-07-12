"""ANCHOR-DISTANCE WEIGHTING diagnostic (SBEST transfer).

Hypothesis: among same-directory siblings that tie lexically, the true fix
file is closer (in import/call-graph hops) to symbols/files the issue
explicitly NAMES -- weight candidates by 1/(1+hops) to nearest anchor.

Method note (per task spec, "OR simpler" branch): rather than
re-implementing lanes2's import-graph / def-index resolution logic inline,
each instance's base_commit tree is materialized read-only into a private
scratch directory via `git archive <base_commit> | tar -x` (pure rev-based
access -- no `git checkout` is ever run against the shared repo_cache
clones, so this is safe to run concurrently with other agents). lanes2 is
then imported directly and its REAL Corpus / build_import_graph /
extract_symbol_anchors are run unmodified against that materialized tree.
This reuses lanes2's exact import-graph + def-index resolution rather than
reimplementing it, at the cost of a `git archive` + tar-extract per
instance (cheap: <1s each for these repo sizes).
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

DIAG_DIR = Path(__file__).resolve().parent
LAB_DIR = Path("/Users/nicholasarehart/programming-projects/bgrep/lab")
RESULTS_PATH = LAB_DIR / "results_swebench" / "abl_bridges_v7.jsonl"
PARQUET_PATH = DIAG_DIR / "swebench_lite.parquet"
REPO_CACHE = DIAG_DIR / "repo_cache"

sys.path.insert(0, str(LAB_DIR))
import lanes2 as L  # noqa: E402


def load_results():
    recs = [json.loads(l) for l in open(RESULTS_PATH) if "error" not in json.loads(l)]
    return {r["instance_id"]: r for r in recs}


def at10_fail(rec):
    gold = set(rec["gold_files"])
    top10 = set(rec["returned_files"][:10])
    return not gold.issubset(top10)


def select_instances():
    import pandas as pd

    recs = load_results()
    fail, passing = [], []
    for iid, r in recs.items():
        (fail if at10_fail(r) else passing).append(iid)
    passing_sorted = sorted(passing)
    step = len(passing_sorted) // 10
    control = [passing_sorted[i] for i in range(0, len(passing_sorted), step)][:10]

    df = pd.read_parquet(PARQUET_PATH)
    df = df.set_index("instance_id")
    return recs, sorted(fail), control, df


def materialize(repo_slug: str, sha: str, dest: Path) -> None:
    """Populate `dest` with the file tree at `sha`, via `git archive` (a pure
    rev-based read -- reads objects, never touches the shared clone's
    working tree / HEAD / index)."""
    clone = REPO_CACHE / repo_slug.replace("/", "__")
    dest.mkdir(parents=True, exist_ok=True)
    p1 = subprocess.Popen(
        ["git", "-C", str(clone), "archive", sha],
        stdout=subprocess.PIPE,
    )
    p2 = subprocess.run(["tar", "-x", "-C", str(dest)], stdin=p1.stdout)
    p1.stdout.close()
    p1.wait()
    if p1.returncode != 0 or p2.returncode != 0:
        raise RuntimeError(f"materialize failed for {repo_slug}@{sha}")


# ---------------------------------------------------------------- anchors

_WORDCHAR = re.compile(r"[A-Za-z0-9_]")


def _literal_hit(problem_statement: str, needle: str) -> bool:
    start = 0
    while True:
        idx = problem_statement.find(needle, start)
        if idx == -1:
            return False
        before = problem_statement[idx - 1] if idx > 0 else " "
        after_pos = idx + len(needle)
        after = problem_statement[after_pos] if after_pos < len(problem_statement) else " "
        if not _WORDCHAR.match(before) and not _WORDCHAR.match(after):
            return True
        start = idx + 1
    return False


def literal_path_mentions(problem_statement: str, files: list[str]) -> set[str]:
    """(b) literal path/basename mentions: a file is an anchor if its full
    relative path appears verbatim in the issue text (checked via
    non-word-char boundaries on both sides -- inherently rare, so no rarity
    gate needed), OR its basename appears verbatim AND that basename is
    itself repo-rare (<=3 files share it, mirroring extract_symbol_anchors'
    <=3-defining-files gate) -- otherwise generic names like 'core.py' /
    'connect.py' / 'utils.py' (14, 8, ... files in a repo like astropy) turn
    every mention of a common filename into a repo-wide anchor blast, which
    is pure noise rather than file-identity evidence."""
    basename_owners: dict[str, list[str]] = {}
    for rel in files:
        basename_owners.setdefault(Path(rel).name, []).append(rel)

    hits: set[str] = set()
    for rel in files:
        if len(rel) >= 5 and _literal_hit(problem_statement, rel):
            hits.add(rel)
            continue
        base = Path(rel).name
        if len(base) >= 5 and len(basename_owners[base]) <= 3 and _literal_hit(problem_statement, base):
            hits.add(rel)
    return hits


def build_anchor_set(problem_statement: str, corpus: "L.Corpus") -> tuple[set[str], dict]:
    sym_anchors = L.extract_symbol_anchors(problem_statement, corpus)
    sym_files = {f for f, _ in sym_anchors}
    path_files = literal_path_mentions(problem_statement, corpus.files)
    anchors = sym_files | path_files
    detail = {
        "symbol_anchor_files": sorted(sym_files),
        "path_mention_files": sorted(path_files),
    }
    return anchors, detail


# ---------------------------------------------------------------- graph distance

def build_combined_graph(corpus: "L.Corpus") -> dict[str, set[str]]:
    """import edges (lanes2.build_import_graph, reused verbatim) unioned with
    same-directory edges, replicating the exact same_dir grouping pattern
    lanes2.select_files / _expand_region use internally (same_dir[str(Path(rel).parent)])."""
    edges = L.build_import_graph(corpus)
    same_dir: dict[str, list[str]] = {}
    for rel in corpus.files:
        same_dir.setdefault(str(Path(rel).parent), []).append(rel)
    combined: dict[str, set[str]] = {f: set(edges.get(f, ())) for f in corpus.files}
    for rel in corpus.files:
        for nbr in same_dir.get(str(Path(rel).parent), []):
            if nbr != rel:
                combined[rel].add(nbr)
                combined.setdefault(nbr, set()).add(rel)
    return combined


def bfs_multi_source(graph: dict[str, set[str]], sources: set[str]) -> dict[str, int]:
    dist: dict[str, int] = {}
    q = deque()
    for s in sources:
        if s in graph:
            dist[s] = 0
            q.append(s)
    while q:
        u = dist_key = q.popleft()
        for v in graph.get(u, ()):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def distance_scores(graph: dict[str, set[str]], anchors: set[str], files: list[str]) -> dict[str, float]:
    dist = bfs_multi_source(graph, anchors)
    return {f: (1.0 / (1.0 + dist[f]) if f in dist else 0.0) for f in files}


# ---------------------------------------------------------------- ranking

def rank_a(mini: list[str], dscore: dict[str, float]) -> list[str]:
    """distance score alone, ties broken by original mini-corpus input order
    (stable sort) for determinism."""
    return sorted(mini, key=lambda f: -dscore[f])


def rank_b(mini: list[str], dscore: dict[str, float], order_score: dict[str, float]) -> list[str]:
    blended = {f: 0.5 * order_score[f] + 0.5 * dscore[f] for f in mini}
    return sorted(mini, key=lambda f: -blended[f])


def current_order_scores(mini: list[str], returned_files: list[str]) -> dict[str, float]:
    """normalized-current-order score: 1 - rank/N for files present in the
    full (pre-@10-truncation) returned_files ranking, 0.0 for files that
    were dropped entirely (never made the packed selection at all)."""
    n = len(returned_files)
    pos = {f: i for i, f in enumerate(returned_files)}
    out = {}
    for f in mini:
        if f in pos and n > 0:
            out[f] = 1.0 - pos[f] / n
        else:
            out[f] = 0.0
    return out


# ---------------------------------------------------------------- per-instance

def process_instance(iid: str, rec: dict, row, work_root: Path) -> dict:
    repo_slug = rec["repo"]
    base_commit = row["base_commit"]
    problem_statement = row["problem_statement"]
    gold = rec["gold_files"]
    returned = rec["returned_files"]
    top10 = returned[:10]
    missing10 = [g for g in gold if g not in set(top10)]

    dest = work_root / iid
    if dest.exists():
        shutil.rmtree(dest)
    materialize(repo_slug, base_commit, dest)

    corpus = L.Corpus(dest)
    anchors, anchor_detail = build_anchor_set(problem_statement, corpus)
    anchors &= set(corpus.files)  # def_index/path hits are already corpus files, but be safe

    graph = build_combined_graph(corpus)

    mini = sorted(set(missing10) | set(top10))
    dscore = distance_scores(graph, anchors, mini)
    oscore = current_order_scores(mini, returned)

    ra = rank_a(mini, dscore)
    rb = rank_b(mini, dscore, oscore)

    def rank_of(f, ordered):
        return ordered.index(f) + 1 if f in ordered else None

    missing_ranks = {
        g: {
            "rank_a": rank_of(g, ra),
            "rank_b": rank_of(g, rb),
            "dist_score": dscore.get(g, 0.0),
            "order_score": oscore.get(g, 0.0),
        }
        for g in missing10
    }

    return {
        "instance_id": iid,
        "repo": repo_slug,
        "n_gold": len(gold),
        "missing10": missing10,
        "n_missing10": len(missing10),
        "mini_corpus_size": len(mini),
        "n_anchors": len(anchors),
        "anchors": sorted(anchors),
        "anchor_detail": anchor_detail,
        "missing_ranks": missing_ranks,
        "any_missing_top3_b": any(v["rank_b"] is not None and v["rank_b"] <= 3 for v in missing_ranks.values()),
        "all_missing_top3_b": bool(missing_ranks) and all(
            v["rank_b"] is not None and v["rank_b"] <= 3 for v in missing_ranks.values()
        ),
        "corpus_files": corpus.n_docs,
    }


def process_control(iid: str, rec: dict, row, work_root: Path) -> dict:
    repo_slug = rec["repo"]
    base_commit = row["base_commit"]
    problem_statement = row["problem_statement"]
    gold = rec["gold_files"]
    returned = rec["returned_files"]
    top10 = returned[:10]
    assert set(gold).issubset(set(top10))

    dest = work_root / iid
    if dest.exists():
        shutil.rmtree(dest)
    materialize(repo_slug, base_commit, dest)

    corpus = L.Corpus(dest)
    anchors, anchor_detail = build_anchor_set(problem_statement, corpus)
    anchors &= set(corpus.files)

    graph = build_combined_graph(corpus)
    mini = list(top10)
    dscore = distance_scores(graph, anchors, mini)
    ra = rank_a(mini, dscore)

    def rank_of(f, ordered):
        return ordered.index(f) + 1 if f in ordered else None

    gold_ranks = {g: rank_of(g, ra) for g in gold}

    return {
        "instance_id": iid,
        "repo": repo_slug,
        "gold_files": gold,
        "n_anchors": len(anchors),
        "gold_ranks_distance_alone": gold_ranks,
        "all_gold_top3_distance": bool(gold_ranks) and all(v is not None and v <= 3 for v in gold_ranks.values()),
    }


def main():
    recs, fail_ids, control_ids, df = select_instances()
    print(f"fail={len(fail_ids)} control={len(control_ids)}", flush=True)

    work_root = DIAG_DIR / "materialized"
    work_root.mkdir(exist_ok=True)

    fail_results = []
    for iid in fail_ids:
        row = df.loc[iid]
        print(f"[fail] {iid} ...", flush=True)
        try:
            fail_results.append(process_instance(iid, recs[iid], row, work_root))
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            fail_results.append({"instance_id": iid, "error": str(e)})

    control_results = []
    for iid in control_ids:
        row = df.loc[iid]
        print(f"[control] {iid} ...", flush=True)
        try:
            control_results.append(process_control(iid, recs[iid], row, work_root))
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            control_results.append({"instance_id": iid, "error": str(e)})

    with open(DIAG_DIR / "fail_results.json", "w") as f:
        json.dump(fail_results, f, indent=1)
    with open(DIAG_DIR / "control_results.json", "w") as f:
        json.dump(control_results, f, indent=1)

    shutil.rmtree(work_root, ignore_errors=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
