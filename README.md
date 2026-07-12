# roust

**Recall-first code retrieval for coding agents.**

Point an agent at grep and it gets perfect recall — at the cost of reading
roughly a million tokens to answer one question. Point it at roust and it
gets the same recall for about 8.5k tokens, in under a second, with no
embeddings, no LLM calls, no API keys, and no training. Validated on 407
held-out SWE-bench Verified instances (92.1% all-gold-files, never tuned on)
and on the archex head-to-head benchmark (40/40 tasks at recall 1.00, 95%
mean token savings vs. raw grep). roust is a ranking-and-packing pipeline over
plain lexical, structural, and version-control signals — it reads like a very
disciplined `grep` session, compressed into one process call.

## Install

From source, until the PyPI release lands:

```bash
uv tool install git+https://github.com/narehart/roust
# or, for local development:
git clone https://github.com/narehart/roust && cd roust && pip install -e .
```

Once published:

```bash
uv tool install roust
# or
pipx install roust
```

Requires Python 3.10+. `git` should be on `PATH` if you want the
commit-history signal (roust degrades gracefully without it).

The first `roust` call against a repo builds an index — a few hundred
milliseconds to a few seconds depending on repo size. The index is cached
under `<repo>/.roust/` (add that directory to your `.gitignore`) and
refreshes automatically whenever indexed files change, so every call after
the first is a cache hit.

## Usage

```
roust QUERY [PATH]
```

`QUERY` can be a natural-language question or raw issue/error text; `PATH`
defaults to `.`. Default output on stdout is a token-budgeted, packed bundle
of the most relevant code regions; a one-line stats summary always goes to
stderr, so stdout stays clean for piping.

A real session, run against `encode/httpx`:

```bash
$ roust "connection pooling" ~/code/httpx
[... ~8.4k tokens of packed file regions on stdout ...]
roust: 25 files, 8366 tokens (indexed 57 files, index 9ms, query 160ms, cache hit)
```

Other flags:

```bash
# Ranked file paths only, one per line -- for fast localization
roust "connection pooling" ~/code/httpx --files-only

# Machine-readable output: files, packed regions, bundle text, timing stats
roust "connection pooling" ~/code/httpx --json

# Cap the file count (0 = no cap, the default)
roust "connection pooling" ~/code/httpx --k 5

# Change the token budget for the packed bundle (default: 8192)
roust "connection pooling" ~/code/httpx --budget 4096

# Force a fresh index build even if a cache entry exists
roust "connection pooling" ~/code/httpx --reindex

# Skip the on-disk cache entirely (neither reads nor writes .roust/)
roust "connection pooling" ~/code/httpx --no-cache

# Disable individual signal channels (all on by default)
roust "connection pooling" ~/code/httpx --no-history     # git commit-message field + co-change frontier
roust "connection pooling" ~/code/httpx --no-docs        # *.rst/*.txt/*.md docs-bridge
roust "connection pooling" ~/code/httpx --no-anchors     # definition-symbol anchor channel
roust "connection pooling" ~/code/httpx --no-testbridge  # test-file lexical bridge

# Dump the full diagnostic record (roust.core.Explain) as JSON to stderr
roust "connection pooling" ~/code/httpx --explain
```

Exit codes: `0` = results found, `1` = no results, `2` = usage error.

## Using with coding agents

This is the point of the tool: an agent that reaches for `roust` before
`grep` gets the files it needs in one shot, at roughly 1% of the token cost,
without needing to iterate on search terms.

### Claude Code

Add to your project's `CLAUDE.md`:

```markdown
## Code search

Before using grep/find/glob to explore this repo, run roust first:

- `roust "<question or issue text>" --files-only` to localize which files
  are relevant.
- `roust "<question or issue text>"` to get a packed bundle of the actual
  relevant code, ready to read.

Pass the raw question or issue text as the query -- don't summarize or
clean it up first. Include error messages, stack traces, file paths, and
backtick-quoted symbol/function names verbatim; roust uses those as
high-precision anchors. Only fall back to grep for a literal string match
roust's bundle doesn't cover.
```

And allowlist it in `.claude/settings.json` so it runs without a permission
prompt:

```json
{
  "permissions": {
    "allow": ["Bash(roust *)"]
  }
}
```

### Cursor

Add to `.cursorrules`:

```
Before grepping this repo, run `roust "<question or issue text>" --files-only`
(or without --files-only for a packed code bundle) in the terminal to find
relevant files. Pass the raw question/issue text as the query, including
error strings and backtick-quoted symbol names -- don't paraphrase it first.
```

### Aider

Invoke it from chat with `/run`:

```
/run roust "TypeError in connection pool cleanup" --files-only
```

And add a line to `CONVENTIONS.md`:

```
Search this repo with `roust "<raw question or error text>"` before grep --
it returns a token-budgeted bundle of the relevant code directly.
```

### OpenAI Codex CLI / generic agents

Add to `AGENTS.md`:

```markdown
## Code search

Run `roust "<question or issue text>" --files-only` to localize relevant
files, or `roust "<question or issue text>"` for a ready-to-read code
bundle. Pass the raw question/issue text verbatim as the query (error
messages, paths, and backtick-quoted symbols included) rather than a
cleaned-up paraphrase.
```

### MCP

No MCP server yet (it's on the roadmap) -- roust is shell-first by design
today, since every agent already has a shell and `roust` is a single
subprocess call with structured `--json` output when you need it.

> **Query tips for agents**
> - Pass the raw issue/question text verbatim as the query.
> - Include error messages, stack traces, and symbol names -- don't strip
>   them out.
> - Don't summarize the question into clean prose first: measured on
>   adversarial paraphrases that drop key terms, task recall falls from
>   1.00 to 0.833 (14/19 tasks) -- summarization removes the anchors roust
>   relies on. See "Known limits" in `lab/README.md`.

## How it works

- **BM25F** over identifier subtokens (camelCase/snake_case split, Porter-lite
  stemming), with path tokens as a separate weighted field and an
  implementation-file prior (tests/docs/examples down-weighted).
- **1-hop structural expansion** over the import/same-package graph, with RM3
  pseudo-relevance feedback carrying evidence from lexical hits to their
  quiet neighbors.
- **Commit-message channel**: git history text folded in as a monotone
  addition-only signal (never reorders the lexical head).
- **Definition-symbol anchors**: rarity-gated (symbol defined in ≤3 impl
  files), tiered promotion so only strong anchors can enter the top ranks.
- **Test/docs bridges**: tests and docs are treated as developer-written
  natural-language-to-code mappings, appended tail-only.
- **Greedy weighted-coverage region packing** under a token budget, so the
  final bundle is code regions, not whole files, chosen to maximize coverage
  per token.

Every component above was added to fix a concrete, measured miss, and every
number in this README is reproduced in the pipeline's research log,
including negative results and a pre-registered held-out validation run:
see [`lab/README.md`](lab/README.md).

## Benchmarks

| benchmark | metric | result |
|---|---|---|
| SWE-bench Verified, held-out (n=407, unseen) | all-gold-files | 92.1% |
| SWE-bench Verified, held-out (n=407, unseen) | File@10 | 79.4% |
| SWE-bench Lite, dev (n=300) | all-gold-files | 92.3% |
| SWE-bench Lite, dev (n=300) | File@10 | 82.7% |
| archex (40 tasks, 17 repos, 5 languages) | file recall | 1.00 (40/40) |
| archex | token savings vs. raw grep | 94–96% (mean) |

Bundles run ~8.5k tokens; index build is ~0.2–6s cold and ~10ms on a cache
hit; queries run 150–550ms end to end. All numbers above are training-free
and model-free -- no embeddings, no fine-tuning, no GPU.

Trained embedding retrievers reach higher File@10 (90.9–94.2, per SweRank,
arXiv:2505.07849) at the cost of a model and GPU inference on every query.
roust is the strongest training-free, model-free point on that curve.

## Limits

- **File-level, not line-level.** roust localizes to files and packs regions
  within them; it doesn't point at a specific line or diff hunk.
- **@1 precision is the measured weak spot.** Top-1 file accuracy on the
  held-out SWE-bench Verified set is .354 -- if you need "the one file",
  read further down the ranked list, don't trust rank 1 alone.
- **Natural-language issues with no identifiers are the hard class.** Every
  non-semantic retrieval method (roust included) leans on identifiers, paths,
  and error strings as anchors; a vague prose description with none of those
  gives the pipeline little to grab onto.
- **Python gets the full signal set** (import graph, definition-symbol
  index). Other languages (JS/TS, Go, Rust, Java, etc.) get a best-effort
  subset -- lexical/BM25F, paths, and history still apply, but there's no
  import-graph or def-index expansion yet.

## Roadmap

- ~~Rust port~~ **v0.2 complete**: `roust-rs/` — feature-parity with Python v0.2 (channel-aware packing, on-disk cache with incremental updates, deterministic seed). Parity re-proven 300/300 exact on SWE-bench Lite (report in `parity/rust_gate_300_v2.json`). Cold 3.6–4.2× faster than Python (httpx 145ms vs 522ms, django 1.8s vs 7.6s); warm/incremental 2–3×. Build: `cd roust-rs && cargo build --release`. Prebuilt binaries / Homebrew: still to come.
- MCP server.
- Incremental index updates (avoid full reindex on every change).
- Publish to PyPI and Homebrew.

---

Research artifacts -- benchmark JSONLs, diagnostics, and pre-registered
held-out predictions -- live in [`lab/`](lab/README.md).

License: MIT.

## History

Formerly `bgrep`; renamed to avoid collision with the binary-grep tool of
that name.
