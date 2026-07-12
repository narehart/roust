# Rank Aggregation & Top-k Theory: Applicability Scan

## 1. Fagin's Threshold Algorithm (TA) — instance optimality

Fagin, Lotem & Naor, "Optimal Aggregation Algorithms for Middleware" (PODS 2001 / journal version [arXiv:cs/0204046](https://arxiv.org/abs/cs/0204046)). Given m sorted lists (one per scoring channel) and a monotone combining function f, TA does round-robin sorted access across all lists, computes exact scores via random access for every object seen, and stops once the running k-th best exact score ≥ f(current last-seen values in each list) — the **threshold**. TA is **instance-optimal**: its cost is within a constant factor (depending only on m and the random-access/sorted-access cost ratio, not on the data) of *any* correct algorithm on *that specific input*. Fagin's original FA needs O(N^{(m-1)/m} k^{1/m}) sorted accesses; TA typically stops far earlier and needs no assumption about data distribution.

**Leap**: the guarantee is not "close to optimal on average" — it's optimal on every single query, which is exactly the property hand-tuned caps can never offer (a cap is tuned for the average query and is instance-*pessimal* on the tail).

## 2. NRA — no random access

Same paper introduces NRA for when random access isn't supported by some lists — it tracks a [worst-case, best-case] score interval per candidate from sorted access alone and prunes once k candidates' worst bound exceeds all others' best bound. Follow-ups: Güntzer et al.'s "Speeding Up NRA," and Selective-NRA (Gursky, [Springer 2009](https://link.springer.com/chapter/10.1007/978-3-642-00672-2_4); journal version [JIIS 2012](https://link.springer.com/article/10.1007/s10844-012-0208-5)) add heuristics for which list to probe next. NRA is proven instance-optimal *within the class of no-random-access algorithms* (not against random-access algorithms — that gap is real and provably unclosable in general).

**Leap**: this is a near-exact match to the stated problem — channels like history/tests/docs that can't be probed for an arbitrary file. NRA gives exact interval bounds instead of an arbitrary "read top-N and hope," and its termination condition is a formal certificate, not a tuned constant.

## 3. Kemeny rank aggregation / cheap approximations

Kemeny-optimal aggregation (minimize total pairwise disagreement across input rankings) is NP-hard, NP-hard even for 4 lists (Dwork, Kumar, Naor, Sivakumar, WWW 2001). Cheap approximations with guarantees: Borda/Pick-a-Perm (expected 2-approx), footrule optimal aggregation (2-approx via min-cost bipartite matching, solvable in polynomial time), KwikSort (3-approx, QuickSort-style pivoting). Partial-list and tie-aware variants are surveyed for the "how to aggregate top-lists" line of work ([ResearchGate summary](https://www.researchgate.net/publication/338326462_How_to_aggregate_Top-lists_Approximation_algorithms_via_scores_and_average_ranks); recent differentially-private variants at [arXiv:2511.11319](https://arxiv.org/pdf/2511.11319), efficient dynamic updates at [arXiv:2509.02885](https://arxiv.org/pdf/2509.02885)).

**Leap**: these guarantees are about *rank* aggregation (ordinal), not score fusion — useful only if channels genuinely disagree on ordering rather than magnitude, and only if we care about the aggregate ranking's distance to consensus, not top-k recall. Lower priority for this project than TA/NRA.

## 4. Top-k joins with expensive predicates

Hwang & Chang, "Probe Minimization by Schedule Optimization: Supporting Top-k Queries with Expensive Predicates" (IEEE TKDE 2007; MPro algorithm). Finding the optimal probe *schedule* (which expensive predicate to evaluate on which candidate, in what order) is NP-hard, so MPro uses a greedy benefit/cost ratio per predicate to decide probe order, provably approximating the optimal schedule's cost.

**Leap**: symbol-anchor resolution or docs lookups that require an actual (possibly expensive) parse/read are "expensive predicates" — MPro's benefit/cost scheduling directly generalizes "which channel do we bother probing for this candidate" beyond a fixed per-channel cap.

## 5. Skyline / Pareto retrieval

Instead of scalarizing 7 channels into one score, keep the Pareto frontier — candidates not dominated on all channels simultaneously. Survey: "Comparing Flexible Skylines and Top-k Queries" ([arXiv:2202.06351](https://arxiv.org/pdf/2202.06351)), "Understanding the Compromise Between Skyline and Ranking" ([arXiv:2204.06078](https://arxiv.org/pdf/2204.06078)), multi-objective DB survey ([arXiv:2202.02619](https://arxiv.org/pdf/2202.02619)). Key result: skyline avoids committing to channel weights at all (only monotone preference per axis is assumed), but skyline size can blow up combinatorially with more channels/anti-correlation — flexible-skyline / k-dominance hybrids exist precisely to bound output size while keeping the no-weights guarantee.

**Leap**: skyline eliminates the "hand-tuned cap/threshold" failure mode structurally, at the cost of no single ranked order — best used as a *pre-filter* (discard dominated candidates before scalarizing) rather than a replacement for top-k, since a single "best hit" is still needed.

## 6. Weighted-fusion optimality (when linear fusion is dominated)

Cormack, Clarke & Buettcher, "Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods" (SIGIR 2009, [PDF](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf)) — rank-only RRF beats several score-combination and even some learned methods in a zero-tuning, cross-domain setting, but is provably dominated by *tuned* convex score combinations once even modest labeled data exists, and RRF is non-smooth/underperforms when constituent score distributions carry real information (i.e., ranks discard magnitude, which is a strict information loss whenever magnitude is meaningful — a channel like a lexical BM25 score has meaningful magnitude, path-distance may not).

**Leap**: no linear fusion (weighted or RRF) has a *worst-case* guarantee; TA/NRA's guarantee holds precisely because they never scalarize until random-access confirmation — this is the theoretical argument for replacing linear fusion with a threshold algorithm rather than re-tuning weights again.

## 7. Selectivity / how-deep-to-read

Bast & Weber, "IO-Top-k: Index-access Optimized Top-k Query Processing" (VLDB 2006, [PDF](https://www.vldb.org/conf/2006/p475-bast.pdf)) models the two-phase problem of estimating list-read depth from precomputed synopses. Newer: "Beyond Quantile Methods: Improved Top-K Threshold Estimation for Traditional and Learned Sparse Indexes" ([arXiv:2412.10701](https://arxiv.org/pdf/2412.10701), Dec 2024) — improves on quantile-based score-threshold prediction for stopping posting-list traversal in sparse (BM25/SPLADE-style) indexes, directly relevant since lexical channel is presumably an inverted-index-style list.

**Leap**: replaces a fixed cap-per-channel with a *predicted* threshold score, calibrated per query rather than per corpus — a middle ground between full TA (exact, needs random access) and blind fixed-depth caps.

## 8. Recent learned-free top-k systems (2023–2026)

Nothing surfaced is a clean drop-in "TA for hybrid search" system; closest are engineering writeups on RRF/round-robin fusion for BM25+dense hybrid search (2026 practitioner guides) and cascade retrieval substrates like AgentIR ([arXiv:2605.25092](https://arxiv.org/pdf/2605.25092)) which adapts retrieval depth to workload but without a formal instance-optimality argument. This confirms the gap: production hybrid/code retrieval systems still default to weighted/RRF fusion with hand caps — nobody has published a TA-grounded fusion layer for this exact setting, which is an opportunity rather than a solved problem to copy.

---

## Top-3 transferable ideas

**1. Replace the per-channel read cap with a Threshold Algorithm scheduler.** Do round-robin sorted access across all 7 channels; maintain each candidate's current exact/partial score; stop reading a channel once its next unseen score, combined via f with the other channels' current thresholds, can no longer promote any candidate past the current k-th best. This is a formal per-query stopping rule, not a static N. [fusion]

**2. For channels that cannot score arbitrary files (history/tests/docs), run NRA-style interval bound tracking instead of a fixed read depth.** Track [lower, upper] bounds per candidate from sequential access only; prune once a candidate's upper bound is dominated by k others' lower bounds. This is the direct fix for "some channels can't score arbitrary files" — an explicit alternative to guessing how many rows to pull. [coverage]

**3. Use MPro-style benefit/cost probe scheduling for expensive channels (symbol-anchor resolution, doc parsing) rather than always/never probing.** Compute a per-candidate benefit-to-cost ratio (expected score-bound tightening ÷ probe cost) and only probe the highest-ratio candidate next; this generalizes today's fixed caps into an adaptive, provably-greedy-optimal-ratio schedule. [within-subsystem]

Runner-up worth flagging even outside top-3: skyline pre-filtering (angle 5) as a cheap dominated-candidate prune *before* any scalarization — removes candidates no weight vector could ever prefer, shrinking the field TA/NRA need to consider. [@1]