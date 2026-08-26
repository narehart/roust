#!/usr/bin/env python3
"""WS1c step-0 mining (campaign #56): issue-mention-gated newcomer admission.

Questions (pre-registered in the WS1c spec):
  A. Across the 135 ceiling-blocked MSWE instances, how many of the 499
     out-of-allowlist gold files are MENTIONED in their issue text
     (basename exact match, case-insensitive, or path-suffix match against
     query tokens)?  -> the mechanism's ceiling.
  B. Across all 580 MSWE instances, how many mention ANY out-of-allowlist
     (newcomer-eligible) file?  -> where the reserve would fire (region cost
     is confined to these).
  C. Same gate-fire count for Lite-300.  -> the Python blast radius / risk
     bound.

The candidate-extraction + matching semantics here are CANONICAL: the Rust
`--newcomer-mention-gate` implementation must match them exactly.

Matching semantics:
  * candidates = whitespace tokens of the raw problem_statement, with
    wrapping punctuation ()[]{}<>,:;!?"'`* iteratively trimmed from both
    ends, then trailing '.' trimmed (sentence periods; leading dots survive
    for `.gitignore`-shaped names), lowercased. Tokens shorter than 3 chars
    are dropped.
  * "path-like" restriction (reported both ways, adopted variant marked in
    the writeup): candidate must contain '.' or '/'.
  * newcomer path P (lowercased, repo-relative) is MENTIONED when
      - basename(P) == some candidate, or
      - some candidate containing '/' (after stripping a leading './' or
        '/') equals P or is a '/'-aligned suffix of P.
  * newcomer-eligible files at base_commit = `git ls-tree -r` names that
    survive the corpus walk's exclusions (VENDOR_RE, .roust/) and do NOT
    carry a CODE_EXTENSIONS suffix (Path.suffix semantics). Mentioned hits
    are refined by the engine's sniff (first 8 KB: no NUL, UTF-8 head) and
    the 2 MB size cap via `git cat-file` so the reported gate-fire counts
    reflect actual corpus membership.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

LAB = Path(__file__).resolve().parent
CODE_EXTENSIONS = {".py", ".ts", ".js", ".go", ".rs", ".java", ".kt", ".cs",
                   ".swift", ".tsx", ".jsx"}
VENDOR_RE = re.compile(r"(?i)(vendor|vendored|third_party|node_modules|\.min\.(js|css)$|bundle\.js$)")
TRIM_CHARS = "()[]{}<>,:;!?\"'`*"


def suffix_of(rel: str) -> str:
    name = rel.rsplit("/", 1)[-1]
    i = name.rfind(".")
    return name[i:] if i > 0 else ""


def is_newcomer_eligible(rel: str) -> bool:
    if rel.startswith(".roust/") or VENDOR_RE.search(rel):
        return False
    return suffix_of(rel) not in CODE_EXTENSIONS


def extract_candidates(text: str) -> set[str]:
    out: set[str] = set()
    for tok in text.split():
        prev = None
        while prev != tok:
            prev = tok
            tok = tok.strip(TRIM_CHARS)
            tok = tok.rstrip(".")
        if len(tok) >= 3:
            out.add(tok.lower())
    return out


def path_like(c: str) -> bool:
    return "." in c or "/" in c


def match_mentions(path_lower: str, cands: set[str], slash_cands: list[str]) -> str | None:
    """Returns the matching candidate, or None."""
    base = path_lower.rsplit("/", 1)[-1]
    if base in cands:
        return base
    for c in slash_cands:
        c2 = c[2:] if c.startswith("./") else c.lstrip("/")
        if path_lower == c2 or path_lower.endswith("/" + c2):
            return c
    return None


def ls_tree(repo: Path, commit: str) -> list[str]:
    r = subprocess.run(["git", "ls-tree", "-r", "--name-only", commit],
                       cwd=repo, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"ls-tree {commit} in {repo}: {r.stderr.strip()[:200]}")
    return r.stdout.splitlines()


def sniff_ok(repo: Path, commit: str, rel: str) -> bool:
    """Engine corpus-membership refinement: size cap + text sniff."""
    r = subprocess.run(["git", "cat-file", "-s", f"{commit}:{rel}"],
                       cwd=repo, capture_output=True, text=True, timeout=60)
    if r.returncode != 0 or int(r.stdout.strip() or 0) > 2_000_000:
        return False
    r = subprocess.run(["git", "cat-file", "blob", f"{commit}:{rel}"],
                       cwd=repo, capture_output=True, timeout=60)
    head = r.stdout[:8192]
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError as e:
        return e.end == len(head) and e.start >= len(head) - 3


def mine_instance(repo: Path, commit: str, statement: str,
                  restrict_path_like: bool) -> tuple[list[tuple[str, str]], int]:
    """Returns ([(mentioned newcomer path, matching candidate)], n_eligible)."""
    cands = extract_candidates(statement)
    if restrict_path_like:
        cands = {c for c in cands if path_like(c)}
    slash_cands = sorted(c for c in cands if "/" in c)
    eligible = [f for f in ls_tree(repo, commit) if is_newcomer_eligible(f)]
    hits = []
    for f in eligible:
        m = match_mentions(f.lower(), cands, slash_cands)
        if m is not None and sniff_ok(repo, commit, f):
            hits.append((f, m))
    return hits, len(eligible)


def main() -> None:
    import pandas as pd

    out: dict = {}

    # ---- A: 135 ceiling-blocked MSWE instances, mentioned GOLD newcomers.
    ceiling = [json.loads(l) for l in
               (LAB / "results_regions/ws1_ceiling_records.jsonl").read_text().splitlines()]
    mswe = pd.read_parquet(LAB / "mswe_jsts.parquet")
    ps_by_id = dict(zip(mswe["instance_id"], mswe["problem_statement"]))
    repo_by_id = dict(zip(mswe["instance_id"], mswe["repo"]))

    for variant in ("pathlike", "anytoken"):
        restrict = variant == "pathlike"
        n_gold = n_gold_mentioned = 0
        inst_any, inst_all, detail = [], [], []
        for rec in ceiling:
            iid = rec["instance_id"]
            statement = ps_by_id[iid]
            cands = extract_candidates(statement)
            if restrict:
                cands = {c for c in cands if path_like(c)}
            slash_cands = sorted(c for c in cands if "/" in c)
            hits = []
            for g in rec["outside"]:
                n_gold += 1
                m = match_mentions(g.lower(), cands, slash_cands)
                if m is not None:
                    n_gold_mentioned += 1
                    hits.append((g, m))
            if hits:
                inst_any.append(iid)
                if len(hits) == len(rec["outside"]):
                    inst_all.append(iid)
                detail.append({"instance_id": iid, "mentioned_gold": hits})
        out[f"A_ceiling135_{variant}"] = {
            "n_gold_newcomers": n_gold,
            "n_gold_newcomers_mentioned": n_gold_mentioned,
            "n_instances_any_gold_mentioned": len(inst_any),
            "n_instances_all_gold_mentioned": len(inst_all),
            "instances_any": inst_any,
            "detail": detail,
        }

    # ---- B: MSWE-580 gate-fire (any newcomer-eligible file mentioned).
    # ---- C: Lite-300 gate-fire.
    lite = pd.read_parquet(LAB / "swebench_lite.parquet")
    benches = [
        ("B_mswe580", mswe, LAB / "mswe_repos_private",
         lambda repo: repo.replace("/", "__")),
        ("C_lite300", lite, LAB / "swebench_repos",
         lambda repo: repo.replace("/", "__")),
    ]
    for name, df, repos_root, slugify in benches:
        for variant in ("pathlike", "anytoken"):
            restrict = variant == "pathlike"
            fired, detail, basenames = [], [], Counter()
            for _, row in df.iterrows():
                repo = repos_root / slugify(row["repo"])
                try:
                    hits, n_elig = mine_instance(repo, row["base_commit"],
                                                 row["problem_statement"], restrict)
                except RuntimeError as e:
                    detail.append({"instance_id": row["instance_id"], "error": str(e)})
                    continue
                if hits:
                    fired.append(row["instance_id"])
                    detail.append({"instance_id": row["instance_id"],
                                   "n_eligible": n_elig,
                                   "mentioned": hits[:50]})
                    for f, _ in hits:
                        basenames[f.rsplit("/", 1)[-1]] += 1
            out[f"{name}_{variant}"] = {
                "n_instances": len(df),
                "n_instances_gate_fires": len(fired),
                "gate_fire_instances": fired,
                "top_mentioned_basenames": basenames.most_common(30),
                "detail": detail,
            }
            print(f"{name} {variant}: gate fires on {len(fired)}/{len(df)}",
                  file=sys.stderr, flush=True)

    out_path = LAB / "results_regions/ws1c_mention_mining.json"
    out_path.write_text(json.dumps(out, indent=1))
    print(f"wrote {out_path}", file=sys.stderr)

    # Summary to stdout
    for k in sorted(out):
        v = out[k]
        if k.startswith("A_"):
            print(f"{k}: gold mentioned {v['n_gold_newcomers_mentioned']}/{v['n_gold_newcomers']}"
                  f" | instances any={v['n_instances_any_gold_mentioned']}/135"
                  f" all={v['n_instances_all_gold_mentioned']}/135")
        else:
            print(f"{k}: gate fires {v['n_instances_gate_fires']}/{v['n_instances']}")


if __name__ == "__main__":
    main()
