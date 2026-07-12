"""CAPS-OFF diagnostic fork of lanes2.py.

Purpose: measure the "caps-off ceiling" -- if select_files() evaluated
candidates with NO capacity limits (the limit an instance-optimal TA/NRA
evaluator would approach: full pool, unlimited additions), how many of the
measured File@10 / File@all recall failures have gold ANYWHERE in the
returned candidate list, and at what rank?

This module reuses everything from lanes2.py UNCHANGED (Corpus, bm25,
tokenize, query_terms, extract_symbol_anchors, build_import_graph,
personalized_pagerank, pack_regions, the neighborhood-first helpers, ...) --
scoring formulas (bm25, add_score, fb_n, specificity, docsbridge ranking
key) are byte-identical to lanes2. Only select_files() is reimplemented,
with every CAPACITY cap removed/raised:

  - additions cap (16) and the msg-top-up cap (3): removed -- ALL eligible
    candidates (add_score > 0) and ALL positive-scoring msg-top-up
    candidates are included, not just the top N.
  - pool eligibility threshold: relaxed from `add_score(c) >= 0.15 * pmax`
    (dynamic, evidence-relative) to `add_score(c) > 0` (keep anything with
    ANY positive evidence).
  - anchor promotion caps (2 head + 2 tail): removed -- every anchor file
    extract_symbol_anchors() returns is a candidate (that function's own
    output is already rarity-gated and strength-sorted; nothing here adds a
    NEW eligibility filter, only removes the head-2/tail-2 slice caps).
  - testbridge caps (top-3 linking test files, tail cap of 3): removed --
    every testlike file with positive BM25 score is a linking candidate,
    and every specificity-ranked bridge candidate is included.
  - docsbridge caps (top-3 doc pages, tail cap of 2): removed -- every doc
    page with positive BM25 score contributes references, and every
    ranked bridge candidate is included.
  - k_lex stays 10 (the lexical head is NOT under test here -- floor_ratio/
    k_lex are the "always-on" first stage, not a capacity cap being probed).

No position-based insertion (position 7/12/14/16 in lanes2's tail-tier
logic) is meaningful once there's no cap -- the point of THIS module is
just "is the file anywhere in the full ranked union, and at what rank",
not "does it land in the top 10". So instead of lanes2's insert-at-position
promotion logic, select_files() here builds ONE flat ranked, deduplicated
list in this order (each stage skips files already added by an earlier
stage -- first-seen rank wins, matching "earliest/strongest evidence
determines rank"):

  1. lex_picks (k_lex=10, floor_ratio-filtered BM25F head -- unchanged)
  2. pool-eligible additions, sorted by add_score descending (uncapped)
  3. commit-message top-up, sorted by msg_bm25 score descending (uncapped,
     s>0 only -- the 0.35*msg_max relative threshold is also a capacity-
     style relative cutoff, so it is relaxed to >0 for consistency with
     the pool eligibility relaxation)
  4. definition-symbol anchor candidates, in extract_symbol_anchors()'s own
     (strength, -def_count) order (uncapped)
  5. testbridge candidates, ranked by the SAME specificity score lanes2
     uses (uncapped: all positive-scoring testlike linking files, all
     resulting candidates)
  6. docsbridge candidates, ranked by the SAME (n_pages_referencing,
     best_page_rank) key lanes2 uses (uncapped: all positive-scoring doc
     pages, all resulting candidates)

Do NOT change scoring: bm25/add_score/fb_n/specificity/docsbridge-ranking
formulas below are copy-identical to lanes2.py. The `scores` dict returned
is populated identically to lanes2 too (pool-eligible + msg-top-up files
get `max(existing, 0.3 + 0.5*fb_n)`; anchor/testbridge/docsbridge-only
files get no explicit score, same as lanes2, so pack_regions falls back to
0.0 for them via `scores.get(rel, 0.0)`).
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

# Reuse everything else from lanes2 unchanged.
from lanes2 import (  # noqa: F401
    CODE_EXTENSIONS,
    EXTENDED_EXTENSIONS,
    MAX_FILE_BYTES,
    Corpus,
    _apply_anchor_promotions,  # unused here, kept importable for parity/debugging
    _expand_region,
    _neighborhood_seeds,
    _normalize,
    _NEIGHBORHOOD_MIN_REGION,
    _NEIGHBORHOOD_THRESHOLD,
    _TESTBRIDGE_EXTS,
    _TESTLIKE_RE,
    _resolve_py_dotted,
    _DOTTED_PATH_RE,
    _SPHINX_DIRECTIVE_RE,
    build_import_graph,
    extract_symbol_anchors,
    impl_prior,
    pack_regions,
    personalized_pagerank,
    query_terms,
    tokenize,
    _py_module_index,
)

LAST_EXPLAIN: dict = {}


def _anchor_candidates(anchors: list[tuple[str, float]] | None) -> list[str]:
    """All anchor files, in extract_symbol_anchors()'s own sorted order.
    No head/tail split, no cap -- lanes2's caps (2 head + 2 tail) are the
    thing being removed; the rarity gate (<=3 defining files) inside
    extract_symbol_anchors() itself is unchanged (it's an evidence filter,
    not a capacity cap)."""
    if not anchors:
        return []
    return [f for f, _strength in anchors]


def _testbridge_candidates(
    corpus: Corpus, bm: dict[str, float], edges: dict[str, set[str]]
) -> tuple[list[str], list[tuple[str, str]]]:
    """Uncapped version of lanes2._apply_testbridge_promotions: ALL testlike
    files with positive raw BM25 score are linking candidates (not just the
    top 3), and ALL resulting bridge candidates are returned (not just the
    top-3 by specificity). Ranking/specificity formula is copy-identical to
    lanes2."""
    testlike = [
        f for f in corpus.files
        if _TESTLIKE_RE.search(f) and Path(f).suffix in _TESTBRIDGE_EXTS
    ]
    testlike_set = set(testlike)
    ranked_tests = sorted(
        ((f, bm.get(f, 0.0)) for f in testlike), key=lambda kv: (-kv[1], kv[0])
    )
    top_tests = [(f, s) for f, s in ranked_tests if s > 0]  # CAP REMOVED (was [:3])
    if not top_tests:
        return [], []
    top_score = top_tests[0][1]
    if top_score <= 0:
        return [], []

    candidates: dict[str, tuple[float, str]] = {}
    for test, tscore in top_tests:
        for nbr in edges.get(test, ()):
            if impl_prior(nbr) != 1.0:
                continue
            strength = tscore / top_score
            cur = candidates.get(nbr)
            if cur is None or strength > cur[0]:
                candidates[nbr] = (strength, test)

    def specificity(f: str) -> float:
        strength = candidates[f][0]
        n_test_importers = len(edges.get(f, set()) & testlike_set)
        return strength / math.log(2 + n_test_importers)

    ranked_candidates = sorted(candidates, key=lambda f: (-specificity(f), f))  # CAP REMOVED (was tail cap 3)
    records = [(f, candidates[f][1]) for f in ranked_candidates]
    return ranked_candidates, records


def _docsbridge_candidates(
    corpus: Corpus, terms: list[str]
) -> tuple[list[str], list[tuple[str, int]]]:
    """Uncapped version of lanes2._apply_docsbridge_promotions: ALL doc pages
    with positive BM25 score contribute references (not just the top 3),
    and ALL resulting bridge candidates are returned (not just the top-2).
    Ranking key is copy-identical to lanes2."""
    if not corpus.docs_tf:
        return [], []
    doc_scores = corpus.docs_bm25(terms)
    if not doc_scores:
        return [], []
    ranked_pages = sorted(doc_scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top_pages = [(f, s) for f, s in ranked_pages if s > 0]  # CAP REMOVED (was [:3])
    if not top_pages:
        return [], []

    pyidx = _py_module_index(corpus.files)

    candidates: dict[str, tuple[int, int]] = {}
    for rank, (page, _score) in enumerate(top_pages):
        text = corpus.docs_text[page]
        refs: set[str] = {m.group(0) for m in _DOTTED_PATH_RE.finditer(text)}
        refs.update(m.group(1) for m in _SPHINX_DIRECTIVE_RE.finditer(text))
        resolved: set[str] = set()
        for ref in refs:
            hit = _resolve_py_dotted(ref, pyidx)
            if hit and impl_prior(hit) == 1.0:
                resolved.add(hit)
        for f in resolved:
            n, best_rank = candidates.get(f, (0, rank))
            candidates[f] = (n + 1, min(best_rank, rank))

    ranked_candidates = sorted(  # CAP REMOVED (was tail cap 2)
        candidates, key=lambda f: (-candidates[f][0], candidates[f][1], f)
    )
    records = [(f, candidates[f][0]) for f in ranked_candidates]
    return ranked_candidates, records


def select_files(
    corpus: Corpus,
    terms: list[str],
    use_ppr: bool,
    k_lex: int = 10,
    k_graph: int = 8,
    seed_count: int = 8,
    floor_ratio: float = 0.05,
    cochange: dict[str, dict[str, int]] | None = None,
    cochange_strong: int = 5,
    anchors: list[tuple[str, float]] | None = None,
    use_testbridge: bool = False,
    use_docsbridge: bool = False,
    use_neighborhood: bool = False,
) -> tuple[list[str], dict[str, float]]:
    """CAPS-OFF select_files: same signature/scoring as lanes2.select_files,
    every capacity cap removed (see module docstring). Returns the FULL
    ranked, deduplicated candidate list."""
    global LAST_EXPLAIN
    bm = corpus.bm25(terms)
    if not bm:
        return [], {}

    edges: dict[str, set[str]] | None = None
    neighborhood_explain: dict = {}
    region: set[str] | None = None
    if use_neighborhood and corpus.n_docs > _NEIGHBORHOOD_THRESHOLD:
        # Neighborhood masking itself is not one of the caps under test here
        # (it's a pre-filter to fight lexical dilution in huge monorepos,
        # not a capacity limit on the selection stage) -- reused unchanged.
        same_dir_all: dict[str, list[str]] = defaultdict(list)
        for rel in corpus.files:
            same_dir_all[str(Path(rel).parent)].append(rel)
        edges = build_import_graph(corpus)
        seeds, seed_score = _neighborhood_seeds(corpus, terms, anchors)
        region = _expand_region(seeds, seed_score, edges, same_dir_all)
        region_size = len(region)
        fallback = region_size < _NEIGHBORHOOD_MIN_REGION
        masked_bm = {f: s for f, s in bm.items() if f in region} if not fallback else {}
        if fallback or not masked_bm:
            fallback = True
            region = None
        else:
            bm = masked_bm
        neighborhood_explain = {
            "active": True, "seed_count": len(seeds),
            "region_size": region_size, "fallback": fallback,
        }

    bm_n = _normalize(bm)
    ranked = sorted(bm_n.items(), key=lambda kv: -kv[1])
    best = ranked[0][1]
    # k_lex/floor_ratio: UNCHANGED (the head is not under test).
    lex_picks = [f for i, (f, s) in enumerate(ranked[:k_lex]) if i < 3 or s >= floor_ratio * best]
    scores = dict(bm_n)

    out: list[str] = list(lex_picks)
    seen: set[str] = set(out)

    def _extend(cands: list[str]) -> list[str]:
        added: list[str] = []
        for c in cands:
            if c not in seen:
                seen.add(c)
                out.append(c)
                added.append(c)
        return added

    if not use_ppr:
        anchor_cands = _anchor_candidates(anchors)
        added_anchor = _extend(anchor_cands)
        tb_records: list[tuple[str, str]] = []
        if use_testbridge:
            edges = edges if edges is not None else build_import_graph(corpus)
            tb_cands, tb_records = _testbridge_candidates(corpus, bm, edges)
            _extend(tb_cands)
        db_records: list[tuple[str, int]] = []
        if use_docsbridge:
            db_cands, db_records = _docsbridge_candidates(corpus, terms)
            _extend(db_cands)
        LAST_EXPLAIN = {
            "lex_picks": lex_picks, "anchor_candidates": added_anchor,
            "testbridge": tb_records, "docsbridge": db_records,
        }
        if neighborhood_explain:
            LAST_EXPLAIN["neighborhood"] = neighborhood_explain
        return out, scores

    # --- structural expansion (copy-identical scoring to lanes2) ---
    edges = edges if edges is not None else build_import_graph(corpus)
    same_dir: dict[str, list[str]] = defaultdict(list)
    for rel in corpus.files:
        same_dir[str(Path(rel).parent)].append(rel)

    sources = lex_picks[:6]

    qset = set(terms)
    fb_terms: set[str] = set()
    for s in [f for f in sources if impl_prior(f) == 1.0][:3]:
        weighted = [
            (t, tf * math.log(1 + corpus.n_docs / (1 + corpus.df.get(t, 1))))
            for t, tf in corpus.tf[s].items() if t not in qset
        ]
        weighted.sort(key=lambda kv: -kv[1])
        fb_terms.update(t for t, _ in weighted[:20])

    bm_fb = corpus.bm25(sorted(fb_terms)) if fb_terms else {}
    fb_n = _normalize(bm_fb)

    pool: dict[str, float] = {}
    owner: dict[str, str] = {}
    import_nbrs: dict[str, list[str]] = {}
    cochange_origin: set[str] = set()
    fileset = set(corpus.files)
    for s in sources:
        w = bm_n.get(s, 0.0)
        imp: list[str] = []
        co_partners = cochange.get(s, {}) if cochange else {}
        neighbors = list(edges.get(s, ())) + same_dir.get(str(Path(s).parent), [])
        neighbors += [c for c in co_partners if c in fileset and c not in neighbors]
        if region is not None:
            neighbors = [c for c in neighbors if c in region]
        for c in neighbors:
            if c in lex_picks or c == s or impl_prior(c) < 1.0:
                continue
            if c in edges.get(s, ()):
                imp.append(c)
            elif co_partners.get(c, 0) >= cochange_strong:
                imp.append(c)
            if c in co_partners:
                cochange_origin.add(c)
            if w > pool.get(c, 0.0):
                pool[c] = w
                owner[c] = s
        import_nbrs[s] = imp

    def add_score(c: str) -> float:
        return (0.15 + bm_n.get(c, 0.0) + 0.8 * fb_n.get(c, 0.0)) * (0.5 + 0.5 * pool[c])

    ranked_pool = sorted(pool, key=add_score, reverse=True)
    # CAP REMOVED: was `add_score(c) >= 0.15 * pmax` (evidence-relative
    # dynamic threshold) -- relaxed to "any positive evidence at all".
    eligible = [c for c in ranked_pool if add_score(c) > 0]

    additions: list[str] = list(eligible)  # CAP REMOVED (was capped to 16 via
    # guarantee-tiers + global fill; with no cap every eligible candidate is
    # already included, in add_score-descending order, so the guarantee
    # tiers -- whose only job was ensuring per-source representation UNDER
    # a cap -- are moot and are not reproduced here.)

    # History top-up: CAP REMOVED (was capped to 3, with a 0.35*msg_max
    # relative threshold -- relaxed to >0 for the same reason as pool
    # eligibility above).
    msg_additions: list[str] = []
    if corpus.msg_tf:
        msg_scores = corpus.msg_bm25(terms)
        if msg_scores:
            already = set(lex_picks) | set(additions)
            msg_ranked = sorted(msg_scores.items(), key=lambda kv: -kv[1])
            for f, s in msg_ranked:
                if f in already or s <= 0 or impl_prior(f) != 1.0:
                    continue
                msg_additions.append(f)
        additions.extend(msg_additions)

    _extend(additions)
    # scores: identical formula to lanes2, applied to the same set of files
    # (pool-eligible + msg top-up) -- do NOT change scoring.
    for f in additions:
        scores[f] = max(scores.get(f, 0.0), 0.3 + 0.5 * fb_n.get(f, 0.0))

    anchor_cands = _anchor_candidates(anchors)
    added_anchor = _extend(anchor_cands)

    tb_records: list[tuple[str, str]] = []
    added_tb: list[str] = []
    if use_testbridge:
        tb_cands, tb_records = _testbridge_candidates(corpus, bm, edges)
        added_tb = _extend(tb_cands)

    db_records: list[tuple[str, int]] = []
    added_db: list[str] = []
    if use_docsbridge:
        db_cands, db_records = _docsbridge_candidates(corpus, terms)
        added_db = _extend(db_cands)

    LAST_EXPLAIN = {
        "seeds": sources,
        "lex_picks": lex_picks,
        "pool": [(c, round(add_score(c), 4), round(pool[c], 2)) for c in ranked_pool],
        "eligible": eligible,
        "additions": additions,
        "cochange_additions": [c for c in additions if c in cochange_origin],
        "msg_additions": msg_additions,
        "anchor_candidates": added_anchor,
        "testbridge": tb_records,
        "testbridge_added": added_tb,
        "docsbridge": db_records,
        "docsbridge_added": added_db,
    }
    if neighborhood_explain:
        LAST_EXPLAIN["neighborhood"] = neighborhood_explain
    return out, scores
