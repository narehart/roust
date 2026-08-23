# Fresh SOTA Scan: SWE-bench-Class Localization & Code Retrieval, June–August 2026

*Companion to `lab/research/wave2/sota-localization-anatomy.md` (which covered Agentless, LocAgent, SweRank/+, CoSIL, OrcaLoca, SWE-Adept) — do not re-tread those. Scan window: arXiv submissions ~2026-06-01 through 2026-08-23, via date-bounded arXiv API sweeps on {SWE-bench × localization/retrieval} and {fault/bug localization, code retrieval}, plus targeted searches on the SweRank lineage, the full-split question, and the training-free niche. Scan date: 2026-08-23.*

## Headline answers

1. **The "first complete-split fine-grained table" claim still holds.** Nothing in the window reports file/function/line localization on the full 2,294-instance SWE-bench test split. Every new system and benchmark audited below stops at Lite (300), Verified (500), or pivots to *other* corpora (Pro, Live, Multilingual, or newly-built sets). Detailed audit in §Full-split claim.
2. **The strict training-free niche (no neural inference at all) remains unoccupied — and the field now treats it as a dead tier.** The window's "training-free" papers all mean *no fine-tuning but an LLM agent in the loop* (SHERLOC, IssueExec). The only no-LLM-no-training methods that appear anywhere are BM25/TF-IDF baselines, and SWE-Explore measures them at line-recall 0.021/0.049 — i.e., the field's picture of the deterministic tier is naive lexical retrieval, ~20x below roust's actual line-level performance. Nobody is publishing in roust's cell of the matrix.
3. **The field's center of gravity this quarter is evaluation infrastructure and retrieval-objective critique, not new localizer mechanisms.** Three new benchmarks (SWE-Explore, CORE-Bench, GREPO-adjacent), two "what does the downstream agent actually need" studies (The Recall Trap, minimal-context oracle studies), and no new SweRank-class trained retriever. The trained-retriever frontier has not moved since SweRank+ (2512.20482).
4. **Line-level coverage under a budget is being crowned the differentiating axis** — SWE-Explore's own conclusion is that "file-level localization is already strong for modern methods; line-level coverage and efficient ranking remain the key axes." This is exactly the FUNCTION/LINE gap campaign #4 is running; the field has converged on our problem statement.

---

## Per-system dissection (new systems, June 2026+)

### SHERLOC — arXiv:2606.24820 (June 2026)
**(a) Numbers:** File-level accuracy@1 **84.33%** on SWE-bench Lite (vs OrcaLoca 83.33), recall@1 **81.27%** on Verified (+13.2pp over RepoSearcher/ToolTrain 68.03). Chunk-level (line-span) coverage on Lite: **recall 39.14% / precision 44.54%**. Downstream: +5.95pp resolve on Verified; −36.7% localization tokens. No full-split numbers.
**(b) Mechanism:** An iterative loop (≤20 turns) pairing one reasoning LLM (Qwen3-235B-A22B-Thinking primary; also 30B variants, DeepSeek-V3/R1) with four deterministic tools: View File, literal Codebase Search, Repository Tree, and a Connected Tree of import dependencies. No fine-tuning, no multi-agent orchestration. Deterministic share: tool mechanics only; every navigation decision is LLM judgment. Structurally this is LocAgent minus the entity-BM25 index, plus a stronger reasoning backbone.
**(c) Transferability:** Low as a mechanism (it's frontier-reasoning-in-a-loop, same verdict as SWE-Adept in wave2). But its **chunk-level 39.14% recall on Lite is a directly useful calibration point**: an LLM-agentic SOTA system's line-span recall lands *below* roust's LINE 42.7 on the same split — supporting the wave2 thesis that agentic systems' advantage is file/function selection judgment, not span extraction. Metric definitions differ (their chunk recall vs our gold-line coverage), so treat as approximate until someone runs both harnesses on the same predictions.

### IssueExec — arXiv:2607.17286 (July 2026)
**(a) Numbers (SWE-bench Lite, GPT-4o):** Function-level **Recall@1 41.07%** (Agentless 21.78, MoatlessTools 29.01), Recall@5 55.67 (Agentless 47.26); file-level Recall@1 70.07 (Agentless 59.49, LocAgent 57.30, BM25 27.37). Downstream +17.72% resolved when slotted into Agentless. Note: these file/function numbers are noticeably *below* the Agentless numbers circulating from its own paper — different metric (top-1 of a ranked list vs superset-of-edit-locations); do not cross-compare with roust's FUNCTION 53.3 without a metric bridge.
**(b) Mechanism:** "Issue → tests → code": retrieve semantically relevant *test functions* (bge-large embeddings + LLM selection), **execute them** under `sys.settrace` to get dynamic caller/callee traces, then LLM-rerank the functions the tests actually exercise. Empirical anchors: existing test suites cover **96.98% of ground-truth files** across 18 repos, and issue→test→code two-hop pathways beat direct issue→code matching in 82.4% of cases. Training-free in the no-fine-tuning sense; LLM in three places; requires a runnable environment.
**(c) Transferability: the most interesting idea of the window for roust.** The load-bearing signal — *tests are a human-curated index from behavior vocabulary to code identifiers* — has a fully static approximation: test files' import statements and call expressions name the functions under test, no execution needed. A deterministic "two-hop via tests" feature (issue terms → matching test file/test name → functions that test imports/calls) is a lexical-bridge signal that could reach exactly the lexically-flat contests and Verified's low-visibility E-class pool (wave4: E lexical-visibility only ~60% on Verified) that pointwise signals can't. Candidate for a wave5 experiment; the dynamic-trace part is not transplantable (execution dependency), but IssueExec's own stats say most of the value is in the pathway, not the trace precision.

### The Recall Trap — arXiv:2608.14838 (August 2026)
**(a) Numbers (SWE-bench Verified, fixed-budget context packs):** the higher-recall retriever config (one-chunk-per-file dedup ON) puts the gold file in 87.8% of packs vs 80.6% OFF — yet OFF *raises* single-shot resolve: +7.6pp (GPT-5.6, 39.2→46.8, n=500, p=0.0003), +3.6pp (Qwen3.6-27B, p=0.013). A random-chunk control rules out a selection artifact; the gain tracks within-file depth.
**(b) Mechanism:** Pure configuration study on a deployed retrieval stack — no training, no new model. Finding: under a fixed token budget, **file breadth (recall) trades against within-file depth, and depth wins downstream.**
**(c) Transferability: direct doctrine-level relevance.** roust's charter is 1.00-recall at ≥70% token savings; this paper is the first execution-graded evidence that recall-maximizing configs can *hurt* the consumer under fixed budgets. It does not contradict the charter (roust budgets tokens explicitly rather than maximizing recall unconditionally) but it independently validates the padding adoption (PR #40: more within-file depth around selected regions) from the consumer side, and argues the E-class (missed-file) pool should *not* be attacked by widening file fan-out at the expense of depth. Worth citing in any future packing-policy decision.

### CodeGrep — arXiv:2608.05886 (August 2026)
**(a) Numbers (SWE-bench Verified):** resolve 27.0% vs 25.8% no-retrieval baseline (weak stack); −15% rounds, −19% tokens on resolved instances. The useful result is the **precision threshold**: BM25 at precision 0.375 *degrades* the downstream agent, Jina at 0.445 is neutral, CodeGrep at 0.677 helps. No file/function accuracy table.
**(b) Mechanism:** A 14B retrieval agent RL-trained (GRPO) to issue parallel grep/glob/read calls, supervision mined from 67K open-source agent trajectories; frozen downstream coder. Trained end-to-end — the opposite corner from roust.
**(c) Transferability:** The trained agent, none. The precision-threshold framing, yes: it gives a published, execution-graded argument that a retriever below ~0.45 precision is worse than nothing for an agent consumer — a good external yardstick when reporting roust's precision alongside recall.

### Retrieval-Oriented Code Representations in Agentic Bug Localization — arXiv:2607.11046 (July 2026)
**(a) Numbers:** On Long Code Arena + SWE-bench Verified, file-level: role-aware LLM-generated summaries beat file-path representations by up to +40% Hit@5; representation ensembling +31.9%; LLM post-ranking +42.0%; Agentless case study 94% Hit@6 file (+4.7 over baseline). File-level only.
**(b) Mechanism:** Representation study — lexical/semantic/LLM retrieval over five representations (paths, raw code, three LLM-generated summary types). Training-free in the no-fine-tuning sense, but the winning representations are themselves LLM-generated at index time.
**(c) Transferability:** Low-moderate. The offline-LLM-summarization-at-index-time pattern is technically compatible with a training-free *query-time* pipeline but breaks roust's no-LLM-anywhere property and its cold-start latency budget. The transferable nugget is directional: representation choice moves file-level Hit@k by tens of percent — consistent with wave2's "representation effect, not reasoning effect" reading of the Agentless skeleton.

### Code Isn't Memory — arXiv:2606.22417 (June 2026)
**(a) Numbers:** Within-harness ablation (Claude Opus 4.7 fixed) on SWE-PolyBench Verified + SWE-bench Pro: "large localization gain and statistically separated resolve gain, no cost penalty per cell." Abstract withholds absolute numbers; artifacts (localization extractor, results DB) are on GitHub.
**(b) Mechanism:** A structural codebase index queried by the agent instead of raw grep — construction method (AST vs learned) not stated in the abstract. Framing result: structural indexing pays off specifically on **multi-file changes**.
**(c) Transferability:** Watch item. If the index is deterministic (likely tree-sitter-class), this is another independent replication of the LocAgent-SearchEntity lesson, and its multi-file-change framing maps onto our fragmented multi-function-sweep miss pool. Needs a full-text read before it's load-bearing.

### Sweep-level mentions (not deep-fetched; abstract-sweep evidence only)
- **OwlPath** (2607.27249): OWL2 ontology as a structural retrieval layer for repair — 68.4% strict-apply on SWE-bench Pro, −28.8% tokens. Deterministic-representation flavored, repair-focused.
- **DUALVIEW** (2607.01929): four deterministic graph views (module/function call graphs, class hierarchy, PDG) rendered for *visual* LLM reasoning on Pro/Verified — graph scaffolding again, consumed multimodally.
- **Loc2Repair** (2606.30963): decoupled eval framework; explicit file-level localization "consistently improves resolved rate across all backbones" — more downstream evidence that localization quality is the binding input.
- **TraceProbe** (2607.06184): 2,500-trajectory diagnosis; "file choice is too coarse to separate success from failure" — a third independent voice (with SWE-Explore and Loc2Repair) pushing evaluation below file granularity.
- **Rethinking APR** (2608.14065): imprecise fault localization *enlarges* the spread between repair techniques — localization precision is a variance amplifier downstream.
- **EffiHolmes** (2608.03558): differential-profiling localization for *performance* bugs; new RepoEffi-Bench (140 Python issues) — adjacent task, new vertical.

---

## New benchmarks (the full-split question lives here)

### SWE-Explore — arXiv:2606.07297 (June 2026)
**848 issues, 10 languages, 203 repos**, sourced from SWE-bench Verified + Pro + Multilingual (64.5% Python). Task: return K=5 ranked regions under a **500-line budget** (also 100/300); primary metric nDCG@500; **line-level ground truth distilled from code regions that successful independent agent trajectories actually consulted** (not gold edit lines — a consultation-based target, broader than ours). Headline table (GPT-5.4 backbone where applicable): Oracle HitFile .923/line-recall .953; CoSIL .544/.788; Claude Code .667/.154; Mini-SWE-Agent .640/.151; AutoCodeRover .280/.233; TF-IDF .140/.049; **BM25 .079/.021**. Verdicts: agentic explorers a clear tier above classical retrieval; line-level coverage is the open axis.
**Relevance to roust:** this is the first external benchmark whose *shape* (ranked regions under a line budget) matches roust's contract. The deterministic tier they measure is BM25/TF-IDF at line-recall 0.02–0.05 — roust would be a category outlier if entered. Caveats before acting: consultation-derived ground truth rewards breadth of *useful* context, not edit-point precision; and CoSIL's .788 line recall vs Claude Code's .154 looks anomalous enough to re-verify against the primary tables before quoting.

### CORE-Bench — arXiv:2606.11864 (June 2026)
Code-retrieval benchmark, 180K+ queries, chunk-granularity labels (AST/LangChain splitters preserving file paths + line spans). Level-2/3 issue-localization queries are built from **Verified (432/302), Pro (632/585), Live (1,623), SWE-bench++ (442), SWE-bench+ (207), Multi-SWE-bench (1,449/1,445), Multilingual (276/248)** — the original 2,294 full split is conspicuously absent. Zero-shot rows (nDCG@10/Recall@100, L2): SweRankEmbed-Large 22.4/52.1, Qwen3-Embedding-8B 20.3/48.0, E5-Mistral 18.3/51.7; in-domain SFT lifts Qwen3-8B to 32.8/66.4. Two takeaways: (i) even the best trained code-retrieval embedders collapse to ~20 nDCG@10 on agentic-coding retrieval — the "sharp drop from traditional code search" is now quantified; (ii) "zero-shot" here means off-the-shelf *trained* embedders, not training-free methods — no deterministic system is evaluated at all.

### GREPO — arXiv:2602.13921 (Feb 2026; pre-window backfill, never covered in prior waves)
86 Python repos, **47,294 bug-fixing tasks**, graph-structured, built for GNN bug localization; GNNs beat IR baselines (keyword/text-similarity/BFS heuristics). Not SWE-bench-derived, granularity unstated in the abstract, no fine-grained table on any SWE-bench split — a scale-adjacent dataset, not a threat to the full-split claim, but the largest localization-supervision corpus we've seen and a potential *evaluation* pool if its labels turn out to be function-grained.

### SpIDER — arXiv:2512.16956 (Dec 2025; backfill)
Dense embedding retrieval + LLM reasoning + graph-based codebase exploration for issue localization; new SpIDER-Bench from SWE-PolyBench/Verified/Multi-SWE-bench; "≥13% improvement over dense retrieval" across languages. Trained-dense + LLM lineage — SweRank-adjacent, not training-free, no full-split numbers.

---

## Full-split claim audit

Systematic check of every candidate in the window that could plausibly have published fine-grained numbers on all 2,294:

| Candidate | Split(s) actually used | Fine-grained on full 2,294? |
|---|---|---|
| SHERLOC (2606.24820) | Lite 300 + Verified 500 | No |
| IssueExec (2607.17286) | Lite 300 | No |
| SWE-Explore (2606.07297) | New 848-issue set (Verified+Pro+Multilingual) | No |
| CORE-Bench (2606.11864) | Verified/Pro/Live/++/+/Multi/Multilingual — full split absent | No |
| CodeGrep (2608.05886) | Verified 500 | No |
| Recall Trap (2608.14838) | Verified 500 | No |
| 2607.11046 (representations) | Verified + Long Code Arena | No |
| GREPO (2602.13921) | Own 47K-task corpus, not SWE-bench | No |
| SpIDER (2512.16956) | SpIDER-Bench (PolyBench/Verified/Multi) | No |

Direct searches for "2,294 + localization + function/line" surface only the original SWE-bench paper and systems already in prior waves. **Verdict: roust's FULL-split table (85.7/38.9/28.1 on 2,294) remains, to the best of this scan, the only complete-split fine-grained localization table in the literature.** The trend actually runs the other way — new work is fragmenting onto Pro/Live/Multilingual/bespoke sets, so the original full split is becoming *less* contested, which strengthens the claim's shelf life but weakens its audience; SWE-Explore-style multi-source sets are where comparisons are heading.

## Training-free / zero-shot niche audit

Three distinct meanings of "training-free" are now circulating; keeping them straight is the whole story:

1. **No fine-tuning, LLM agent at inference** (SHERLOC, IssueExec, SWE-Adept lineage): crowded and advancing; gains track frontier-model quality.
2. **Zero-shot = off-the-shelf trained embedders** (CORE-Bench's "zero-shot" rows, SweRankEmbed used out-of-domain): stalled this quarter — no new SweRank-class retriever since SweRank+; CORE-Bench shows these collapse (~20 nDCG@10) outside their training distribution.
3. **No neural inference at all** (roust): represented in the entire window's literature *only* by BM25/TF-IDF baselines — SWE-Explore line-recall 0.021–0.049, CORE-Bench doesn't even include one, CodeGrep uses BM25 as its "actively harmful" calibration point (precision 0.375, degrades the agent). Nobody published a serious system in this tier; the field's belief that the tier tops out at BM25 is intact and increasingly load-bearing in how papers frame the "classical retrieval" strawman.

**Consequence:** roust's positioning is unchanged and, if anything, sharpened — every new benchmark in the window uses a deterministic baseline 5–20x below roust's measured level, so entering any of them (SWE-Explore first, given its region/line-budget shape) would land in an empty band between "classical retrieval" and the LLM-agent tier.

## What this scan changes for campaign #4

1. **New candidate signal — static test-bridge (from IssueExec):** issue → test-name/test-file lexical match → functions the test imports/calls, computed statically. Targets lexically-flat contests and the Verified E-class visibility floor via human-curated behavior-to-identifier vocabulary. The only genuinely new deterministic-approximable mechanism found this window.
2. **Depth-over-breadth is now externally validated (Recall Trap):** fixed-budget consumers prefer within-file depth to file fan-out; aligns with the PR #40 padding adoption and cautions against recall-widening fixes for E-class.
3. **External benchmark opportunity (SWE-Explore):** first public line-budget region benchmark; a roust entry is a positioning move, but its consultation-based ground truth differs from our gold-edit-line target — measure the gap before treating scores as comparable.
4. **No new pressure on the FUNCTION/LINE front from trained retrievers:** SweRank+ is still the trained frontier; the gap roust chases hasn't moved from above.

## Sources fetched
- arXiv API date-bounded sweeps (June 1 – Aug 24, 2026): `export.arxiv.org/api/query` over {SWE-bench × localization/retrieval} (38 entries) and {fault/bug localization ∪ code retrieval} (39 entries)
- SHERLOC: https://arxiv.org/abs/2606.24820 and https://arxiv.org/html/2606.24820v1
- IssueExec: https://arxiv.org/abs/2607.17286 and https://arxiv.org/html/2607.17286v1
- SWE-Explore: https://arxiv.org/abs/2606.07297 and https://arxiv.org/html/2606.07297v1
- CORE-Bench: https://arxiv.org/abs/2606.11864 and https://arxiv.org/html/2606.11864v2
- The Recall Trap: https://arxiv.org/abs/2608.14838
- CodeGrep: https://arxiv.org/abs/2608.05886
- Representations study: https://arxiv.org/abs/2607.11046
- Code Isn't Memory: https://arxiv.org/abs/2606.22417
- Rethinking APR: https://arxiv.org/abs/2608.14065
- GREPO: https://arxiv.org/abs/2602.13921 (backfill)
- SpIDER: https://arxiv.org/abs/2512.16956 (backfill)
- SweRank lineage check via WebSearch: no successor to SweRank+ (2512.20482) as of scan date

## Caveats
Same WebFetch-summarization caveat as wave2: all numbers passed through an intermediate summarizing model, not raw PDF table parsing. Specific items to re-verify before any number becomes load-bearing: (i) SWE-Explore's CoSIL line-recall 0.788 vs Claude Code 0.154 looks anomalous — possibly a metric-definition artifact (regions returned vs regions consulted); (ii) SHERLOC's chunk-level 39.14% recall metric definition vs roust's gold-line coverage; (iii) IssueExec's Agentless baselines are much lower than Agentless's own published numbers — confirmed to be a different metric (ranked Recall@k), so never mix its table with the wave2 numbers; (iv) Code Isn't Memory's index construction (deterministic vs learned) is unverified — abstract only. Sweep-level mentions (OwlPath, DUALVIEW, Loc2Repair, TraceProbe, EffiHolmes) were not individually fetched; treat their one-liners as leads, not citations. The full-split audit is a no-evidence-found result over keyword-reachable arXiv — a paper burying full-split fine-grained numbers in an appendix without SWE-bench-adjacent keywords would evade this net.
