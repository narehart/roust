# E30 — per-source seating breadth (`--seats-per-source`)

**Verdict: NO-ADOPT.** Default unchanged (`seats_per_source = 1`). Go's 3+
stratum is *worse* at every setting tried, monotonically, at two cap settings.

## Why this lever, and why it looked different from E28

E29 established that file selection is blind to the token budget, so breadth
is reachable only through admission. Every admission lever tried before this
one worked on the **global rank tail**: E28 raised `max_additions`, which
admits the next-highest-scoring pool candidate overall. That is exactly the
place where the campaign's standing meta-finding bites — gold and non-gold
pool candidates are not distinguishable on co-change (E27), directory
proximity or hub centrality (E20, WS3d), or shared identifiers.

Guarantee 2 in `select_files` is a structurally different admission rule:

```rust
// Guarantee 2: each source's best neighbor overall.
for s in &sources {
    if let Some(grp) = groups.get(s) {
        if let Some(first) = grp.first() {   // exactly ONE, per source
```

`groups` is keyed by `owner[c]` — the highest-BM25 source that reaches `c` —
and `grp` is score-sorted, so each source seats its single best-owned
candidate. Seating K instead of 1 spends admissions on **ownership
diversity** rather than on global rank. Multi-gold instances are exactly the
ones whose gold spans several modules, so this is the shape of the target.

## Result (Go, n=143, the >= 3-gold-file stratum)

| arm | all-gold FILE | FUNCTION | LINE | frac | tokens |
|---|---|---|---|---|---|
| cap 16, seats 1 (shipped default) | 27.27 | 3.50 | 0.70 | .2498 | 8488 |
| cap 32, seats 1 (E28) | **37.06** | 3.50 | 0.70 | .2343 | 8618 |
| cap 16, seats 2 | 26.57 | 4.20 | 0.70 | .2471 | 8491 |
| cap 16, seats 3 | 26.57 | 4.20 | 0.70 | .2495 | 8515 |
| cap 32, seats 2 | 36.36 | 3.50 | 0.70 | .2350 | 8617 |
| cap 32, seats 3 | 34.97 | 4.20 | 0.70 | .2357 | 8616 |

## The mechanism, and a framing this round had to correct mid-flight

Seats never *add* breadth at any cap. `max_additions` binds the total, so
extra seats displace tail-fill candidates one-for-one: mean bundle tokens are
flat to within 2 across cap-32 arms (8616 / 8617 / 8618) and within 27 across
cap-16 arms. The round was launched believing cap 32 would make the seats
additive; it does not, and the token column is what falsifies it. What E30
therefore measures — at both caps — is **composition at constant breadth**.

That makes it the cleanest test of the meta-finding the campaign has run,
because it is a controlled *swap* rather than a widening:

| comparison | records changed | FILE gained | FILE lost |
|---|---|---|---|
| cap 16: seats 2 vs seats 1 | 26 / 143 | **0** | 1 |
| cap 32: seats 2 vs seats 1 | — | **0** | 1 |

Swapping a rank-ordered candidate for an ownership-diverse one rescued a
missing gold file **zero times in 143 instances**, twice over. Mean
file-coverage delta on the changed records: −0.0387.

## Standing meta-finding, fourth sighting

Candidate-level discrimination is exhausted for this signal set. Prior
sightings: E20 (hub centrality), WS3d (fire shape), E27 (co-change seats).
E30 adds ownership diversity, and adds it in the strongest form — at fixed
admission count, where a signal with *any* gold-discriminating value would
show a positive swap rate. It showed zero.

The consequence for the per-language parity goal is that the multi-file gap
is not reachable by re-ranking or re-composing the existing candidate pool.
It needs a candidate-generation signal the engine does not currently have.

## Provenance

Pinned binary `roust 0.3.2 (7c8f6bb, clean)`, built once in an isolated
worktree, never rebuilt mid-run; engine diff between the two build SHAs is
0 lines (`git diff 4709470 7c8f6bb -- roust-rs/`). Instances are E29's Go
3+ list (143), so every arm is directly comparable to E29's. 143/143 records,
0 errors, per arm. Arms record `seats_per_source` per instance; the shipped
default forwards no flag at all (harness sentinel 0), so a default arm's argv
stays byte-identical to every pre-E30 default arm's.
