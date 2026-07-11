"""Headroom diagnostic for three UNUSED signals on SWE-bench Lite File@10
failures under the current config (results_swebench/abl_anchor_v5.jsonl):

  SIGNAL A -- error-string literals: 5-word shingles of traceback exception
              messages / long quoted spans in problem_statement, matched
              verbatim (whitespace-collapsed) against stray gold file text.
  SIGNAL B -- test-file lexical bridge: mini BM25 over testlike .py files,
              query = problem_statement; top-5 test files' resolved imports.
  SIGNAL C -- docs bridge: mini BM25 over doc files (.rst/.txt/.md, non-test);
              top-5 pages' dotted-path / sphinx-directive references resolved
              against the repo's python module index.

Read-only measurement script: does NOT modify lanes2.py or swebench_driver2.py,
and does not write new results/config. Checks out repo@base_commit in the
SHARED clones under swebench_repos/, so it refuses to run concurrently with
swebench_driver (waits until `pgrep -f swebench_driver` is empty).

Usage (run from the archex dir, per lab convention -- picks up the archex
uv-managed venv's pandas/pyarrow):
    uv run python ../bgrep_lab/diag_channels.py
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))

from lanes2 import tokenize, _TESTLIKE_RE, CODE_EXTENSIONS  # noqa: E402

import pandas as pd  # noqa: E402

RESULTS = LAB / "results_swebench" / "abl_anchor_v5.jsonl"
PARQUET = LAB / "swebench_lite.parquet"
REPOS = LAB / "swebench_repos"
TOTAL_INSTANCES = 300

# ---------------------------------------------------------------- regexes

# Signal A
_TRACE_RE = re.compile(r"^\s*\w+(?:Error|Exception|Warning)\s*:\s*(.+)$", re.M)
_DQUOTE_RE = re.compile(r'"([^"\n]{1,400})"')
_SQUOTE_RE = re.compile(r"'([^'\n]{1,400})'")

# Signal B (import resolution -- same regex approach as lanes2.build_import_graph)
_PY_FROM_RE = re.compile(r"^\s*from\s+([\w\.]+)\s+import\s+(\([^)]*\)|[^\n]+)", re.M)
_PY_PLAIN_IMPORT_RE = re.compile(r"^\s*import\s+([\w\., ]+)", re.M)

# Signal C
_DOTTED_RE = re.compile(r"\b[a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*){2,}\b")
_SPHINX_RE = re.compile(r"(?:automodule|currentmodule|module|autoclass|autofunction)::\s*([\w\.]+)")


def collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def read_text(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def checkout(repo_dir: Path, sha: str) -> None:
    r = subprocess.run(["git", "checkout", "-f", "-q", sha], cwd=repo_dir,
                        capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"checkout {sha} failed: {r.stderr.strip()[:300]}")
    subprocess.run(["git", "clean", "-fdq"], cwd=repo_dir, capture_output=True,
                    text=True, timeout=300)


def wait_for_driver_idle() -> None:
    while True:
        r = subprocess.run(["pgrep", "-f", "swebench_driver"], capture_output=True, text=True)
        if not r.stdout.strip():
            return
        print("swebench_driver is running (shared clones); waiting 30s...", flush=True)
        time.sleep(30)


# ---------------------------------------------------------------- mini BM25

def bm25_rank(doc_toks: dict[str, list[str]], query_terms: list[str],
              k1: float = 1.2, b: float = 0.75) -> list[tuple[str, float]]:
    """Standalone Okapi BM25 (no path field, no prior) over an arbitrary
    document set. doc_toks: rel -> already-tokenized text."""
    n = len(doc_toks)
    if n == 0:
        return []
    doclen = {r: len(t) for r, t in doc_toks.items()}
    avg = (sum(doclen.values()) / n) if n else 1.0
    df: Counter[str] = Counter()
    tf: dict[str, Counter[str]] = {}
    for r, toks in doc_toks.items():
        c = Counter(toks)
        tf[r] = c
        for term in c:
            df[term] += 1
    scores: dict[str, float] = defaultdict(float)
    for term in query_terms:
        d = df.get(term)
        if not d:
            continue
        idf = math.log(1.0 + (n - d + 0.5) / (d + 0.5))
        for r, c in tf.items():
            f = c.get(term)
            if not f:
                continue
            denom = f + k1 * (1 - b + b * doclen[r] / avg)
            scores[r] += idf * (f * (k1 + 1) / denom)
    return sorted(scores.items(), key=lambda kv: -kv[1])


# ---------------------------------------------------------------- signal A

def extract_shingles(problem_statement: str) -> list[str]:
    candidates: list[str] = []
    for m in _TRACE_RE.finditer(problem_statement):
        msg = collapse(m.group(1))
        if len(msg) >= 20:
            candidates.append(msg)
    for rx in (_DQUOTE_RE, _SQUOTE_RE):
        for m in rx.finditer(problem_statement):
            span = collapse(m.group(1))
            if len(span.split()) >= 4:
                candidates.append(span)
    shingles: set[str] = set()
    for c in candidates:
        words = c.split()
        # "split into 5-word shingles" -- candidates shorter than 5 words
        # (e.g. an exactly-4-word quoted span) yield no shingle at all,
        # per spec; they are effectively too short to be a discriminative
        # error-string literal. [flagged assumption]
        for i in range(len(words) - 4):
            shingles.add(" ".join(words[i:i + 5]))
    return sorted(shingles)


# ---------------------------------------------------------------- python module index (signals B, C)

def build_pyidx(repo_dir: Path) -> dict[str, str]:
    files: list[str] = []
    for p in repo_dir.rglob("*.py"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(repo_dir))
        if rel.startswith(".git/") or "/.git/" in rel:
            continue
        files.append(rel)
    idx: dict[str, str] = {}
    for rel in files:
        mod = rel[:-3].replace("/", ".")
        idx[mod] = rel
        if mod.endswith(".__init__"):
            idx[mod[: -len(".__init__")]] = rel
    return idx


def resolve_py_module(mod: str, rel: str) -> str:
    """Resolve a possibly-relative module spec to an absolute dotted path
    (mirrors lanes2.build_import_graph.resolve_py_module)."""
    if not mod.startswith("."):
        return mod
    level = len(mod) - len(mod.lstrip("."))
    rest = mod.lstrip(".")
    pkg_parts = list(Path(rel).parent.parts)
    pkg_parts = pkg_parts[: len(pkg_parts) - (level - 1)] if level > 1 else pkg_parts
    return ".".join([*pkg_parts, *(rest.split(".") if rest else [])])


def resolve_module_file(mod: str, pyidx: dict[str, str]) -> str | None:
    parts = [p for p in mod.split(".") if p]
    for i in range(len(parts), 0, -1):
        hit = pyidx.get(".".join(parts[:i]))
        if hit:
            return hit
    return None


def parse_py_imports(rel: str, text: str, pyidx: dict[str, str]) -> set[str]:
    out: set[str] = set()
    for m in _PY_FROM_RE.finditer(text):
        mod = resolve_py_module(m.group(1), rel)
        hit = resolve_module_file(mod, pyidx)
        if hit:
            out.add(hit)
        for name in m.group(2).strip("()").replace("\n", " ").split(","):
            name = name.strip().split(" as ")[0].strip("*# \t")
            if name and "." not in name:
                sub = pyidx.get(f"{mod}.{name}")
                if sub:
                    out.add(sub)
    for m in _PY_PLAIN_IMPORT_RE.finditer(text):
        for spec in m.group(1).split(","):
            mod = spec.strip().split(" as ")[0].strip()
            if mod:
                hit = resolve_module_file(mod, pyidx)
                if hit:
                    out.add(hit)
    return out


# ---------------------------------------------------------------- signal B

def collect_testlike_py(repo_dir: Path) -> list[str]:
    out: list[str] = []
    for p in repo_dir.rglob("*.py"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(repo_dir))
        if rel.startswith(".git/") or "/.git/" in rel:
            continue
        if _TESTLIKE_RE.search(rel):
            out.append(rel)
    return sorted(out)


def signal_b(problem_statement: str, repo_dir: Path, pyidx: dict[str, str]
             ) -> tuple[set[str], list[tuple[str, set[str]]]]:
    testlike = collect_testlike_py(repo_dir)
    doc_toks: dict[str, list[str]] = {}
    texts: dict[str, str] = {}
    for rel in testlike:
        text = read_text(repo_dir / rel)
        if text is None:
            continue
        texts[rel] = text
        toks = tokenize(text)
        if toks:
            doc_toks[rel] = toks
    if not doc_toks:
        return set(), []
    q = tokenize(problem_statement)
    ranked = bm25_rank(doc_toks, q)
    top5 = [r for r, _ in ranked[:5]]
    resolved: set[str] = set()
    evidence: list[tuple[str, set[str]]] = []
    for rel in top5:
        imports = parse_py_imports(rel, texts[rel], pyidx)
        resolved |= imports
        evidence.append((rel, imports))
    return resolved, evidence


# ---------------------------------------------------------------- signal C

_DOC_EXTS = (".rst", ".txt", ".md")
_DOC_CAP = 4000


_DOC_TESTDIR_RE = re.compile(r"(^|/)(tests?|testing|__tests__)(/|$)", re.I)


def collect_doc_files(repo_dir: Path) -> list[str]:
    out: list[str] = []
    for pattern in ("*.rst", "*.txt", "*.md"):
        found = []
        for p in repo_dir.rglob(pattern):
            if not p.is_file():
                continue
            rel = str(p.relative_to(repo_dir))
            if rel.startswith(".git/") or "/.git/" in rel:
                continue
            if _DOC_TESTDIR_RE.search(rel):
                continue
            found.append(rel)
        out.extend(sorted(found))
        if len(out) >= _DOC_CAP:
            break
    return out[:_DOC_CAP]


def signal_c(problem_statement: str, repo_dir: Path, pyidx: dict[str, str]
             ) -> tuple[set[str], list[tuple[str, set[str]]]]:
    docs = collect_doc_files(repo_dir)
    doc_toks: dict[str, list[str]] = {}
    texts: dict[str, str] = {}
    for rel in docs:
        text = read_text(repo_dir / rel)
        if text is None:
            continue
        texts[rel] = text
        toks = tokenize(text)
        if toks:
            doc_toks[rel] = toks
    if not doc_toks:
        return set(), []
    q = tokenize(problem_statement)
    ranked = bm25_rank(doc_toks, q)
    top5 = [r for r, _ in ranked[:5]]
    resolved: set[str] = set()
    evidence: list[tuple[str, set[str]]] = []
    for rel in top5:
        text = texts[rel]
        refs: set[str] = set(_DOTTED_RE.findall(text))
        refs.update(_SPHINX_RE.findall(text))
        files_here: set[str] = set()
        for ref in refs:
            hit = resolve_module_file(ref, pyidx)
            if hit:
                files_here.add(hit)
        resolved |= files_here
        evidence.append((rel, files_here))
    return resolved, evidence


# ---------------------------------------------------------------- data loading

def load_results() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for line in RESULTS.read_text().splitlines():
        r = json.loads(line)
        if "error" in r:
            continue
        rows[r["instance_id"]] = r
    return rows


def load_meta() -> dict[str, dict]:
    df = pd.read_parquet(PARQUET)
    return {row["instance_id"]: row for _, row in df.iterrows()}


# ---------------------------------------------------------------- main

def snip(s: str, n: int = 80) -> str:
    s = collapse(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> None:
    wait_for_driver_idle()
    t_start = time.perf_counter()

    rows = load_results()
    meta = load_meta()

    fail10 = sorted(
        iid for iid, r in rows.items()
        if not (set(r["gold_files"]) <= set(r["returned_files"][:10]))
    )
    n_pass10 = len(rows) - len(fail10)
    print(f"Failing @10 instances: {len(fail10)} (passing: {n_pass10} of {len(rows)})", flush=True)

    # per-instance per-stray-gold-file hit records
    #   iid -> {"stray10": set, "stray_all": set, "per_file": {gold: {...}}}
    inst_data: dict[str, dict] = {}

    for k, iid in enumerate(fail10, 1):
        r = rows[iid]
        m = meta[iid]
        repo_slug = m["repo"]
        repo_dir = REPOS / repo_slug.replace("/", "__")
        if not (repo_dir / ".git").exists():
            print(f"  [skip, no clone] {iid}", flush=True)
            continue
        try:
            checkout(repo_dir, m["base_commit"])
        except RuntimeError as exc:
            print(f"  [skip, checkout failed] {iid}: {exc}", flush=True)
            continue

        problem_statement = m["problem_statement"]
        gold = set(r["gold_files"])
        top10 = r["returned_files"][:10]
        stray10 = gold - set(top10)
        stray_all = gold - set(r["returned_files"])

        # ---- signal A prep: candidate shingles + collapsed top-10 texts
        shingles = extract_shingles(problem_statement)
        top10_collapsed: dict[str, str] = {}
        for t in top10:
            txt = read_text(repo_dir / t)
            if txt is not None:
                top10_collapsed[t] = collapse(txt)

        # ---- signals B, C (per instance, shared module index)
        pyidx = build_pyidx(repo_dir)
        b_resolved, b_evidence = signal_b(problem_statement, repo_dir, pyidx)
        c_resolved, c_evidence = signal_c(problem_statement, repo_dir, pyidx)

        per_file: dict[str, dict] = {}
        for g in sorted(stray10):
            gtext = read_text(repo_dir / g)
            gcollapsed = collapse(gtext) if gtext is not None else None

            a_hit_shingle = None
            a_discriminative = None
            if gcollapsed:
                for sh in shingles:
                    if sh and sh in gcollapsed:
                        a_hit_shingle = sh
                        break
                if a_hit_shingle is not None:
                    a_discriminative = not any(
                        a_hit_shingle in tc for tc in top10_collapsed.values()
                    )

            b_hit = g in b_resolved
            b_src = None
            if b_hit:
                for rel, imports in b_evidence:
                    if g in imports:
                        b_src = rel
                        break

            c_hit = g in c_resolved
            c_src = None
            if c_hit:
                for rel, files_here in c_evidence:
                    if g in files_here:
                        c_src = rel
                        break

            per_file[g] = {
                "a_hit": a_hit_shingle, "a_discriminative": a_discriminative,
                "b_hit": b_hit, "b_src": b_src,
                "c_hit": c_hit, "c_src": c_src,
            }

        inst_data[iid] = {"stray10": stray10, "stray_all": stray_all, "per_file": per_file}

        if k % 10 == 0:
            print(f"  progress {k}/{len(fail10)}", flush=True)

    wall = time.perf_counter() - t_start

    # ---------------------------------------------------------------- report

    def aggregate(target_key: str, iids: list[str]) -> dict:
        a_insts, b_insts, c_insts, a_disc_insts = set(), set(), set(), set()
        a_cases, b_cases, c_cases, a_disc_cases = [], [], [], []
        for iid in iids:
            d = inst_data.get(iid)
            if not d:
                continue
            targets = d[target_key]
            for g, hit in d["per_file"].items():
                if g not in targets:
                    continue
                if hit["a_hit"] is not None:
                    a_insts.add(iid)
                    a_cases.append((iid, g, snip(hit["a_hit"])))
                    if hit["a_discriminative"]:
                        a_disc_insts.add(iid)
                        a_disc_cases.append((iid, g, snip(hit["a_hit"])))
                if hit["b_hit"]:
                    b_insts.add(iid)
                    b_cases.append((iid, g, snip(f"imported by {hit['b_src']}")))
                if hit["c_hit"]:
                    c_insts.add(iid)
                    c_cases.append((iid, g, snip(f"referenced in {hit['c_src']}")))
        union = a_insts | b_insts | c_insts
        return {
            "a_insts": a_insts, "b_insts": b_insts, "c_insts": c_insts,
            "a_disc_insts": a_disc_insts, "union": union,
            "a_cases": a_cases, "b_cases": b_cases, "c_cases": c_cases,
            "a_disc_cases": a_disc_cases,
        }

    processed10 = [iid for iid in fail10 if iid in inst_data]
    agg10 = aggregate("stray10", processed10)

    print()
    print("=" * 78)
    print("REPORT 1: File@10 failures (gold file missing from top-10)")
    print("=" * 78)
    print(f"Failing @10 instances processed: {len(processed10)} / {len(fail10)} "
          f"(current File@10 = {n_pass10}/{len(rows)} = {n_pass10/len(rows):.3f})")
    print(f"  Signal A (error-string literal) hits >=1 stray gold file: {len(agg10['a_insts'])} instances")
    print(f"    of which discriminative (shingle absent from all current top-10 files): "
          f"{len(agg10['a_disc_insts'])} instances")
    print(f"  Signal B (test-file lexical bridge) hits >=1 stray gold file: {len(agg10['b_insts'])} instances")
    print(f"  Signal C (docs bridge) hits >=1 stray gold file: {len(agg10['c_insts'])} instances")
    print(f"  UNION (A or B or C): {len(agg10['union'])} instances")
    ceiling10 = (n_pass10 + len(agg10["union"])) / len(rows)
    print(f"  File@10 ceiling if union-signal instances were fixed: "
          f"({n_pass10} + {len(agg10['union'])}) / {len(rows)} = {ceiling10:.3f}")

    print("\n-- Signal A case list (instance_id, gold file, shingle) --")
    for c in agg10["a_cases"]:
        print("  ", c)
    print("\n-- Signal A DISCRIMINATIVE case list (shingle not in any current top-10 file) --")
    for c in agg10["a_disc_cases"]:
        print("  ", c)
    print("\n-- Signal B case list (instance_id, gold file, evidence) --")
    for c in agg10["b_cases"]:
        print("  ", c)
    print("\n-- Signal C case list (instance_id, gold file, evidence) --")
    for c in agg10["c_cases"]:
        print("  ", c)

    # ---- @all report (subset with non-empty stray_all)
    failall = [iid for iid in processed10 if inst_data[iid]["stray_all"]]
    agg_all = aggregate("stray_all", failall)
    n_pass_all = len(rows) - len([iid for iid, r in rows.items()
                                   if not (set(r["gold_files"]) <= set(r["returned_files"]))])

    print()
    print("=" * 78)
    print("REPORT 2: File@all failures (gold file missing from the ENTIRE returned list)")
    print("=" * 78)
    print(f"@all-failing instances processed: {len(failall)} "
          f"(current File@all = {n_pass_all}/{len(rows)} = {n_pass_all/len(rows):.3f})")
    print(f"  Signal A hits >=1 stray gold file: {len(agg_all['a_insts'])} instances")
    print(f"  Signal B hits >=1 stray gold file: {len(agg_all['b_insts'])} instances")
    print(f"  Signal C hits >=1 stray gold file: {len(agg_all['c_insts'])} instances")
    print(f"  UNION (A or B or C): {len(agg_all['union'])} instances")
    ceiling_all = (n_pass_all + len(agg_all["union"])) / len(rows)
    print(f"  File@all ceiling if union-signal instances were fixed: "
          f"({n_pass_all} + {len(agg_all['union'])}) / {len(rows)} = {ceiling_all:.3f}")

    print("\n-- Signal A case list (@all subset) --")
    for c in agg_all["a_cases"]:
        print("  ", c)
    print("\n-- Signal B case list (@all subset) --")
    for c in agg_all["b_cases"]:
        print("  ", c)
    print("\n-- Signal C case list (@all subset) --")
    for c in agg_all["c_cases"]:
        print("  ", c)

    print()
    print(f"wall time: {wall:.1f}s")


if __name__ == "__main__":
    main()
