#!/usr/bin/env python3
"""WS1c step-0 variant grid (campaign #56): the mention-matching trade-off
curve that decided the NO-GO.

For each candidate mention-matching rule, measures the two numbers that
bound the mechanism:
  * ceiling   -- of the 135 ceiling-blocked MSWE instances, how many are
                 RECOVERABLE: every out-of-allowlist gold file is mentioned
                 under the rule AND the instance's in-allowlist gold is
                 already fully present in the WS1b baseline bundle (FILE is
                 all-gold-superset, so both are necessary; admission
                 ranking/fit success is still assumed, so this is an upper
                 bound).
  * gate-fire -- on how many MSWE-580 / Lite-300 instances at least one
                 newcomer-eligible file is mentioned, i.e. where
                 --newcomer-mention-gate would carve the reserve and the
                 region cost lands.

Variants:
  exact_token      spec semantics (canonical, ws1c_mention_mining.py):
                   whitespace tokens, punctuation-trimmed, case-insensitive
                   basename equality or '/'-aligned path-suffix match.
  exact_regexrun   stronger extraction: maximal [A-Za-z0-9_.@/-]+ runs
                   (catches markdown links, URLs, parenthesized paths);
                   unidirectional (candidate is suffix of path) and
                   bidirectional (path is also allowed to be a suffix of
                   the candidate, e.g. blob URLs).
  stem_K{k}        exact_token OR basename-stem token match (stem len>=4)
                   where at most k newcomer-eligible files in the repo
                   share that stem (distinctiveness cap).
  titlestem_K{k}L{l}  exact_token OR stem token restricted to the issue's
                   FIRST LINE, stem len>=l, distinctiveness cap k.

Reads repos with `git ls-tree` only (no checkouts; safe next to running
evals). Writes lab/results_regions/ws1c_variant_grid.json.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ws1c_mention_mining import (extract_candidates, is_newcomer_eligible,
                                 ls_tree, match_mentions)

LAB = Path(__file__).resolve().parent
PATH_RUN = re.compile(r"[A-Za-z0-9_.@/-]+")


def stem(base: str) -> str:
    i = base.rfind(".")
    return base[:i] if i > 0 else base


def extract_runs(text: str) -> set[str]:
    out = set()
    for m in PATH_RUN.finditer(text):
        raw = m.group(0)
        t = raw.strip(".-/")
        if raw.startswith(".") and len(raw) > 1 and raw[1].isalnum():
            t = "." + t
        if len(t) >= 3 and ("." in t or "/" in t):
            out.add(t.lower())
    return out


def match_runs(path: str, cands: set[str], slash_cands: list[str], bidir: bool) -> bool:
    base = path.rsplit("/", 1)[-1]
    if base in cands or path in cands:
        return True
    for c in slash_cands:
        c2 = c[2:] if c.startswith("./") else c.lstrip("/")
        if path == c2 or path.endswith("/" + c2):
            return True
        if bidir and c2.endswith("/" + path):
            return True
    return False


class Variant:
    def __init__(self, name: str):
        self.name = name

    def prepare(self, text: str) -> dict:
        cands = extract_candidates(text)
        return {"cands": cands, "slash": sorted(c for c in cands if "/" in c),
                "text": text}

    def matches(self, path_lower: str, ctx: dict, stem_counts: Counter) -> bool:
        raise NotImplementedError


class ExactToken(Variant):
    def matches(self, path_lower, ctx, stem_counts):
        return match_mentions(path_lower, ctx["cands"], ctx["slash"]) is not None


class ExactRegexRun(Variant):
    def __init__(self, name, bidir):
        super().__init__(name)
        self.bidir = bidir

    def prepare(self, text):
        cands = extract_runs(text)
        return {"cands": cands, "slash": sorted(c for c in cands if "/" in c)}

    def matches(self, path_lower, ctx, stem_counts):
        return match_runs(path_lower, ctx["cands"], ctx["slash"], self.bidir)


class StemK(Variant):
    def __init__(self, name, k, minlen=4):
        super().__init__(name)
        self.k = k
        self.minlen = minlen

    def matches(self, path_lower, ctx, stem_counts):
        if match_mentions(path_lower, ctx["cands"], ctx["slash"]) is not None:
            return True
        st = stem(path_lower.rsplit("/", 1)[-1])
        return (len(st) >= self.minlen and st in ctx["cands"]
                and stem_counts[st] <= self.k)


class TitleStemK(Variant):
    def __init__(self, name, k, minlen):
        super().__init__(name)
        self.k = k
        self.minlen = minlen

    def prepare(self, text):
        ctx = super().prepare(text)
        first = text.strip().splitlines()[0] if text.strip() else ""
        ctx["title"] = {c for c in extract_candidates(first) if len(c) >= self.minlen}
        return ctx

    def matches(self, path_lower, ctx, stem_counts):
        if match_mentions(path_lower, ctx["cands"], ctx["slash"]) is not None:
            return True
        st = stem(path_lower.rsplit("/", 1)[-1])
        return (len(st) >= self.minlen and st in ctx["title"]
                and stem_counts[st] <= self.k)


VARIANTS: list[Variant] = [
    ExactToken("exact_token"),
    ExactRegexRun("exact_regexrun_unidir", bidir=False),
    ExactRegexRun("exact_regexrun_bidir", bidir=True),
    StemK("stem_K1", 1), StemK("stem_K2", 2), StemK("stem_K4", 4),
    StemK("stem_K8", 8), StemK("stem_K16", 16),
    TitleStemK("titlestem_K4_L5", 4, 5),
    TitleStemK("titlestem_K8_L5", 8, 5),
    TitleStemK("titlestem_K8_L6", 8, 6),
]


def gold_files(patch_text: str) -> set[str]:
    return set(m.group(1) for m in
               re.finditer(r"^diff --git a/(\S+) b/", patch_text, re.M))


def main() -> None:
    import pandas as pd

    mswe = pd.read_parquet(LAB / "mswe_jsts.parquet")
    lite = pd.read_parquet(LAB / "swebench_lite.parquet")
    ps = dict(zip(mswe.instance_id, mswe.problem_statement))
    patch = dict(zip(mswe.instance_id, mswe.patch))
    ceiling = [json.loads(l) for l in
               (LAB / "results_regions/ws1_ceiling_records.jsonl").read_text().splitlines()]
    base_rows = {json.loads(l)["instance_id"]: json.loads(l) for l in
                 (LAB / "results_regions/mswe_jsts_ws1b_baseline.jsonl").read_text().splitlines()}

    tree_cache: dict = {}

    def elig_stems(repo: Path, commit: str):
        key = (str(repo), commit)
        if key not in tree_cache:
            e = [f for f in ls_tree(repo, commit) if is_newcomer_eligible(f)]
            tree_cache[key] = (e, Counter(stem(f.lower().rsplit("/", 1)[-1]) for f in e))
        return tree_cache[key]

    out: dict = {}
    for v in VARIANTS:
        row: dict = {}
        # ceiling on the 135
        n_gold_mentioned = 0
        recoverable = []
        for rec in ceiling:
            iid = rec["instance_id"]
            outside = set(rec["outside"])
            inside = gold_files(patch[iid]) - outside
            base = base_rows.get(iid)
            returned = set(base["regions"].keys()) if base and base.get("regions") else set()
            repo = LAB / "mswe_repos_private" / rec["slug"]
            _, sc = elig_stems(repo, rec["base_commit"])
            ctx = v.prepare(ps[iid])
            mentioned = [g for g in outside if v.matches(g.lower(), ctx, sc)]
            n_gold_mentioned += len(mentioned)
            if inside <= returned and len(mentioned) == len(outside):
                recoverable.append(iid)
        row["gold_newcomers_mentioned_of_499"] = n_gold_mentioned
        row["ceiling135_recoverable"] = len(recoverable)
        row["ceiling135_recoverable_instances"] = recoverable

        # gate-fire on both benches
        for bench, df, root in [
            ("mswe580", mswe, LAB / "mswe_repos_private"),
            ("lite300", lite, LAB / "swebench_repos"),
        ]:
            fired = 0
            for _, r in df.iterrows():
                repo = root / r["repo"].replace("/", "__")
                try:
                    e, sc = elig_stems(repo, r["base_commit"])
                except RuntimeError:
                    continue
                ctx = v.prepare(r["problem_statement"])
                if any(v.matches(f.lower(), ctx, sc) for f in e):
                    fired += 1
            row[f"gate_fire_{bench}"] = fired
        out[v.name] = row
        print(f"{v.name}: ceiling={row['ceiling135_recoverable']}/135 "
              f"gold={row['gold_newcomers_mentioned_of_499']}/499 "
              f"fire mswe={row['gate_fire_mswe580']}/580 "
              f"lite={row['gate_fire_lite300']}/300", flush=True)

    out_path = LAB / "results_regions/ws1c_variant_grid.json"
    out_path.write_text(json.dumps(out, indent=1))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
