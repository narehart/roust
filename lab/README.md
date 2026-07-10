# bgrep lab — retrieval experiments

Goal: LLM-agent code retrieval with **recall 1.00, missed-task 0.00, ≥70% fewer
tokens than grep**, tested on the [archex](https://github.com/Mathews-Tom/archex)
head-to-head benchmark (real repos at pinned versions, archex's own metric and
tiktoken accounting).

## Results (2026-07-10)

| lane | mean tokens/task | file recall | missed-task |
|---|---|---|---|
| raw grep + read matched files | 1,180,370 | 1.00 | 0.00 |
| disciplined grep (read ±25 lines around matches) | 764,759 | 1.00 | 0.00 |
| oracle (read exactly the expected files) | 26,395 | 1.00 | 0.00 |
| archex (embeddings, published artifacts) | 6,433 | 0.947 | 0.158 |
| **bgrep pipeline (packed regions)** | **8,317** | **1.00** | **0.00** |

- Dev set: 19/19 tasks at recall 1.00; savings vs raw grep mean 95.7%, min 76.0%.
- Held-out set (21 `loc_*` fault-localization tasks, frozen config): 21/21 at
  recall 1.00; savings mean 95.2%, min 74.9%.
- vs the *disciplined* grep control the pipeline still saves ≥72% on every task
  (mean 94.7%) — discipline removes only ~35% of grep's cost because keyword
  matches are everywhere in a large repo.

## The pipeline (lanes.py — pure Python, no models, no embeddings)

1. **BM25F** over identifier subtokens (camelCase/snake_case split, Porter-lite
   stemming), path tokens as a weighted field, implementation-file prior
   (tests/docs/examples 0.3×).
2. **1-hop structural expansion** of the whole retrieved set over the
   import/same-package graph, with **RM3 pseudo-relevance feedback** carrying
   evidence from hits to their lexically-quiet neighbors; guarantees for
   direct-import dependencies and discriminative path matches (path-df < 10%);
   evidence-threshold cutoff.
3. **Greedy weighted-coverage region packing** under an 8k token budget,
   evidence-proportional per-file allowances.

Every component was added to fix a concrete observed miss (see HYPOTHESES.md
and git history). Negative results: global personalized PageRank loses to
truncated 1-hop diffusion (hub sink); every fixed-count cutoff caused
whack-a-mole between tasks; per-seed quotas starve globally-strong candidates.

## Known limits (measured)

- **Vocabulary brittleness**: with helper keywords dropped, natural paraphrases
  keep 16/19 tasks at recall 1.00 (mean 0.939); adversarial paraphrases that
  avoid the key terms drop to 14/19 (mean 0.833). Consistent with CORE-Bench
  (2026): the fix is **anchor preservation** — callers should pass raw task
  text (error strings, API names, identifiers) rather than cleaned summaries;
  query *cleanup* hurts even dense retrievers. bgrep's caller is an LLM agent,
  which can supply anchor-rich multi-variant queries nearly for free.
- **Depth vs breadth is budget-bound**: bundles pack ~15-26 files into 8k
  tokens. Evidence-proportional allocation helps only marginally (+3%); depth
  is a caller-set budget knob, not a packing-cleverness problem. Literature
  (SWE-bench oracle-collapsed ablation; SWE-Explore degradation study) says
  recall-first / precision-second is the right trade for modern models.
- Recall 1.00 is empirical over 40 tasks / 17 repos / 5 languages, not a
  guarantee. archex comprehension tasks have 1–5 expected files; harder
  issue-to-edit benchmarks (SWE-bench) remain unmeasured for this pipeline.

## Literature context (deep-research pass, 2026-07-10, adversarially verified)

- One-shot indexed retrieval (BM25 *or* dense) fails at repo scale: BM25
  recovers all gold files in <46% of SWE-bench instances at realistic budgets;
  strong embedders collapse on issue-to-edit localization (CORE-Bench);
  non-agentic retrievers score near random on SWE-Explore while agentic
  explorers reach only ~0.65 file-recall.
- Graph expansion measurably lifts *file-level* localization (+4.4–6.7 pts,
  RepoGraph, ICLR 2025) — the exact mechanism and granularity this pipeline
  exploits. AST/region chunking beats whole files at any budget (cAST, EMNLP
  2025; SWE-bench Table 6).
- GrepRAG (2025): optimized grep-style pipelines beat indexed RAG under equal
  budgets with ~35× latency advantage — supporting the no-embedding design.

## SWE-bench Lite file localization (2026-07-11)

Frozen pipeline, query = raw issue text (no keywords, no LLM, no embeddings),
gold = files edited by the merged fix. All 300 instances, zero errors:

- **All-gold-files-present: 267/300 = 0.890** (mean file recall 0.890)
- Mean bundle 10,041 tokens, ~26 files; query 530ms on an index built in 2.1s
- Per repo: seaborn/flask/requests/xarray 1.00, matplotlib & scikit-learn 0.96,
  django 0.89 (102/114), pytest 0.88, sympy 0.84, astropy/pylint 0.83, sphinx 0.81

Published context (see research findings): BM25 achieves all-files retrieval on
~40% of instances at 27k tokens; GPT-4-based Agentless file localization ≈69%
(74% with RepoGraph); agentic explorers ≈0.65 HitFile on the harder SWE-Explore.
Caveat for comparisons: our bundle holds ~26 files — File@5/File@10 numbers from
the ranked list (results_swebench/lite_ranked.jsonl) are the k-matched figures.
Recurring miss pattern: fixes in lexically-distant infrastructure files (e.g.
django/db/migrations/serializer.py for issues describing migration *output*) —
the deep semantic gap that no lexical+structural method closes without an LLM.

## Run it

```bash
git clone https://github.com/Mathews-Tom/archex && cd archex && uv sync
uv run python <this dir>/driver.py                     # all 19 dev tasks, all lanes
uv run python <this dir>/driver.py --tasks httpx_pooling --lanes bm25_ppr_pack
uv run python <this dir>/driver.py --questions-json paraphrases.json --variant adversarial
```

Result JSONs: `results/` (dev), `results_holdout/` (frozen-config loc_*),
`results_grepdisc/` (disciplined-grep control), `results_para_*/` (paraphrase
robustness), `results_weighted_pack/` (allocation ablation).
