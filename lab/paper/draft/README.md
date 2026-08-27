# Paper draft

First full draft of the roust preprint: *Deterministic, Training-Free Code
Localization for Agent Context*.

- `main.tex` — the paper (article class, ~10pp + appendix).
- `refs.bib` — 20 references, all verified against the wave-2/wave-5
  literature scans in `lab/research/`; no invented citations.
- `Makefile` — `make` (pdflatex+bibtex) or `make tectonic`.

**Compile status: NOT compiled.** No LaTeX toolchain is installed in the
environment this draft was written in (`pdflatex`, `tectonic`, and `latexmk`
are all absent). Structural checks that were run instead: balanced braces,
matched `\begin`/`\end` pairs (9/9), and every `\cite` key resolving to a
`refs.bib` entry with no unused entries. First compile on a machine with
LaTeX may still surface formatting issues.

## Open decisions (human)

1. **Venue.** Drafted for an arXiv preprint (cs.SE). ICSE/FSE/ASE would want
   a different framing and page budget; the negative-results section is
   unusually load-bearing and might suit an empirical-track venue.
2. **Author list and affiliation.** Placeholder in `main.tex`.
3. **Title.** Current title emphasises determinism; an alternative
   emphasises the result ("Function-Level Issue Localization Without a
   Model").
4. **Whether to re-measure the complete split** before submission. The
   2,294-instance table predates the trace-boost and structural-block
   adoptions and is therefore a lower bound on the current engine; the
   re-run is ~2,294 × ~5s of eval plus scoring.
5. **Whether to include the agent-loop experiment** at n=15 (currently
   reported as indicative with the spend-cap caveat stated).

## Claim sourcing

Every table cell traces to a committed artifact; the appendix names the
harnesses and directories. Numbers were taken from the README scoreboard and
the per-round reports in `lab/research/langagnostic/` and
`lab/research/wave5/`, which are themselves sourced to
`lab/results_regions/`.
