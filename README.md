# roust

**Give your coding agent the right code in one call.**

roust is a command-line code search tool built for AI coding agents. Hand it a
question, an issue, or an error message, and it hands back one ranked,
token-budgeted bundle of the code most likely to matter. No embeddings, no
model calls, no API keys, nothing leaves your machine. A warm query takes
well under a second.

[Install](#install) · [Quick start](#quick-start) · [Use it with your agent](#use-it-with-your-agent) · [Results](#results) · [Docs site](https://narehart.github.io/roust/)

## Why roust

- **One call replaces the grep loop.** An agent using grep has to guess search
  terms, read through matches, and try again. roust returns the relevant code
  in one shot. In our agent-loop test, the same agent solved 93% of tasks with
  roust and 27% with grep.
- **Fast and local.** The first call indexes the repo (hundreds of
  milliseconds to a few seconds). Every call after that is a cache hit, and a
  warm query runs in roughly 60 to 500 ms on repos up to a few thousand files.
- **Eight languages, packed as functions and classes.** Python, JavaScript,
  TypeScript, Java, Go, Rust, C, and C++ are returned as real syntactic units
  rather than blind line windows. Any other language still indexes and ranks;
  it just packs windows instead.
- **Every number is measured.** Each claim in these docs comes from a
  committed artifact you can re-run. The honest parts are published too:
  Python is the strongest language by a wide margin, and trained retrievers
  beat roust on accuracy. roust is the best result you can get for free.

## Install

roust is a single binary (about 15 MB, most of it the bundled language
grammars). Pick one:

```bash title="shell — install via npm"
# Prebuilt binary for your platform; the package is roust-cli, the command is roust
npm install -g roust-cli
npx roust-cli "connection pooling" ~/code/httpx
```

```bash title="shell — install via cargo"
# Builds from source
cargo install roust
```

Or download a binary from [GitHub Releases](https://github.com/narehart/roust/releases)
(darwin-x64, darwin-arm64, linux-x64, linux-arm64, win32-x64, each with a
`.sha256` checksum), or build a checkout with `cargo install --path roust-rs`.

Two small notes:

- `git` on your `PATH` enables the commit-history signal. roust works without
  it.
- The index lives under `<repo>/.roust/`. Add that directory to your
  `.gitignore`. It refreshes itself whenever indexed files change.

## Quick start

```bash title="shell — a real session against encode/httpx"
$ roust "connection pooling" ~/code/httpx
[... ~8.4k tokens of packed file regions on stdout ...]
roust: 25 files, 8366 tokens (indexed 57 files, index 9ms, query 160ms, cache hit)
```

`roust QUERY [PATH]`. The query can be a plain question or raw issue text;
`PATH` defaults to the current directory. The bundle goes to stdout and a
one-line summary goes to stderr, so stdout is safe to pipe.

The three flags you will actually use:

```bash title="shell — the everyday flags"
# Just the ranked file paths, one per line
roust "connection pooling" ~/code/httpx --files-only

# Machine-readable: files, regions, bundle text, timing, confidence
roust "connection pooling" ~/code/httpx --json

# Cap the number of files (default: no cap)
roust "connection pooling" ~/code/httpx --k 5
```

Exit codes: `0` results found (including low-confidence ones), `1` no query
term matched anything in the repo, `2` usage error.

### Reading the output

The default bundle is sized for a model's context window, not for a person.
It is deliberately broad: it covers as many plausible edit sites as fit in
the budget, because an agent reads selectively and recall is what wins tasks.
If you are reading it yourself, shrink it instead of scrolling past it:

```bash title="shell — smaller output for humans"
roust "connection pooling" ~/code/httpx --budget 2048   # quarter-size bundle
roust "connection pooling" ~/code/httpx --k 8           # fewer files
roust "connection pooling" ~/code/httpx --files-only    # a list, not code
```

Leave the default budget alone in agent configs. Shrinking it trades away
measured recall for no benefit to the agent.

### Weak matches

roust always answers when at least one query term exists in the repo, even
when the match is weak. With `--json`, the `stats` block tells you how much to
trust it: `top_score` (the raw score of the best file, comparable across
queries), `matched_query_terms` out of `total_query_terms`, and
`low_confidence: true` when a calibrated threshold trips. The stderr summary
also appends `[low-confidence match]`. The threshold was calibrated to trip on
zero of the 300 real SWE-bench Lite queries, so a tiny toy repo can trip it
even on a good query.

### More flags

`roust --help` lists everything. The groups worth knowing about:

| Group | Flags | What they do |
|---|---|---|
| Budget | `--budget N` (default 8192) | Token target for the bundle. A target, not a hard cap: small budgets can overshoot by 4 to 22% because a minimum core of regions is always seated. |
| Cache | `--reindex`, `--no-cache` | Force a rebuild, or neither read nor write `.roust/`. |
| Signals | `--no-history`, `--no-docs`, `--no-anchors`, `--no-testbridge`, `--no-trace-boost` | Switch off one evidence channel (git history, docs pages, definition anchors, test files, stack-trace frames). All on by default. |
| Packing | `--pad-lines` (5), `--len-exp` (0.85), `--pack-floor` (0.15), `--tail-seat-tokens` (40) | The shipped region-packing defaults, each adopted after a measured gate. |
| Diagnostics | `--explain` | Dump the engine's full explanation record as JSON to stderr. |

Flags not listed here are opt-in experiments that are measured but not
adopted; the [Research](docs/RESEARCH.md) page explains how a flag becomes a
default.

## Use it with your agent

The whole point: an agent that runs `roust` before `grep` gets the files it
needs in one shot. Two rules apply to every agent below. Pass the raw
question or issue text as the query, including error messages, stack traces,
file paths, and symbol names, because roust uses those as high-precision
anchors. And don't summarize the text first: on paraphrases that drop key
terms, measured recall fell from 1.00 to 0.833.

### Claude Code

Add to your project's `CLAUDE.md`:

```markdown title="CLAUDE.md"
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

And allowlist it in `.claude/settings.json` so it runs without a prompt:

```json title=".claude/settings.json"
{
  "permissions": {
    "allow": ["Bash(roust *)"]
  }
}
```

### Cursor

Add to `.cursorrules`:

```text title=".cursorrules"
Before grepping this repo, run `roust "<question or issue text>" --files-only`
(or without --files-only for a packed code bundle) in the terminal to find
relevant files. Pass the raw question/issue text as the query, including
error strings and backtick-quoted symbol names -- don't paraphrase it first.
```

### Aider

Invoke it from chat with `/run`, and add a line to `CONVENTIONS.md`:

```text title="aider"
/run roust "TypeError in connection pool cleanup" --files-only
```

```text title="CONVENTIONS.md"
Search this repo with `roust "<raw question or error text>"` before grep --
it returns a token-budgeted bundle of the relevant code directly.
```

### OpenAI Codex CLI and other agents

Add to `AGENTS.md`:

```markdown title="AGENTS.md"
## Code search

Run `roust "<question or issue text>" --files-only` to localize relevant
files, or `roust "<question or issue text>"` for a ready-to-read code
bundle. Pass the raw question/issue text verbatim as the query (error
messages, paths, and backtick-quoted symbols included) rather than a
cleaned-up paraphrase.
```

### MCP

No MCP server yet; it is on the roadmap. roust is shell-first by design:
every agent already has a shell, and `roust` is one subprocess call with
`--json` when you need structure.

One measured warning: giving an agent grep *alongside* roust made it worse in
our test (93% to 57% solved). Replace grep, don't supplement it.

## How it works

roust is a ranking-and-packing pipeline over signals that already exist in
your repository. In plain terms:

1. **Find the words.** A BM25F text index over identifier pieces (camelCase
   and snake_case split, light stemming), with file paths as a separate field
   and tests, docs, and examples down-weighted.
2. **Follow the structure.** Files that import, or are imported by, the
   lexical hits get a share of their evidence, so quiet neighbors surface.
3. **Listen to history and tests.** Commit messages and test files are
   treated as developer-written descriptions of the code they touch, added
   as tail-only evidence that never reorders the strongest matches.
4. **Trust names and traces.** A symbol defined in only a few files, or a
   file named in a stack trace, is a strong anchor and gets promoted.
5. **Pack, don't dump.** Instead of whole files, roust returns the functions
   and classes that cover the most evidence per token, until the budget is
   spent.

Every stage was added to fix a specific, measured miss. The
[Research](docs/RESEARCH.md) page describes the loop that decides what ships.

## Results

All numbers are the shipped defaults, scored with the Agentless localization
metric on real bug reports. FILE means every file the fix touched was
returned; FUNCTION means every function the fix touched was returned in full;
LINE means every changed line was included.

| Language (benchmark, instances) | FILE | FUNCTION | LINE |
|---|---|---|---|
| Python (SWE-bench Lite, 300) | 92.3 | 57.7 | 46.0 |
| Python (SWE-bench Verified, 407, held out) | 92.4 | 48.9 | 37.8 |
| Go (Multi-SWE-bench, 428) | 65.0 | 32.9 | 18.5 |
| C++ (Multi-SWE-bench, 129) | 65.9 | 20.9 | 8.5 |
| Rust (Multi-SWE-bench, 239) | 60.3 | 20.9 | 7.5 |
| C (Multi-SWE-bench, 128) | 51.6 | 28.1 | 13.3 |
| Java (Multi-SWE-bench, 128) | 49.2 | 39.8 | 14.8 |
| JavaScript/TypeScript (Multi-SWE-bench, 580) | 46.4 | 31.6 | 14.1 |

How to read it:

- **Python leads, and the gap is real.** Part of it is corpus shape (the
  JS/TS slice has gold files in file types nobody indexes, and Go is mostly
  one repository), and part of it is the engine. Compare within a row over
  time rather than down the column.
- **Against other systems**, roust exceeds Agentless GPT-4o at function and
  line level while using no model, and trails trained retrievers such as
  SweRank at file level. In an agent loop it solved 93% of tasks versus 27%
  for grep and 80% for an embedding search (n=15, a partial run).
- **Speed**: warm queries run in 61 to 495 ms on the seven repos we time,
  identical output to the previous release at 8 to 23 times the speed.

The summary with charts is on [Benchmarks](docs/BENCHMARKS.md). The complete
record, with every comparison, caveat, re-measurement, and artifact path, is
the [Evaluation record](docs/EVALUATION.md).

## Limits

- **It returns regions, not a diff.** roust points at the files and the
  functions worth reading. It does not tell you which line to change.
- **Rank 1 is not "the file".** Top-1 accuracy on held-out Python is about
  35%. Read down the list; roust is built for recall across the set.
- **Vague prose is the hard case.** Like every non-semantic method, roust
  leans on identifiers, paths, and error strings. A description with none of
  those gives it little to hold on to.
- **Import-graph expansion is uneven.** Python, JavaScript/TypeScript, Rust,
  and Go get it by default. Java, C, and C++ import edges exist behind
  `--import-edges-v2`, measured but not yet a default.
- **Breadth costs precision.** About half a percent of the returned lines are
  the actual fix. That trade is intentional and measured; see the
  [Evaluation record](docs/EVALUATION.md#contextbench).

## Roadmap

- Import-graph parity for Java, C, and C++ as a default (the flag exists; the
  adoption gate does not yet pass everywhere).
- More languages. Scala is the most requested; each language needs a
  benchmark slice before its structural support ships.
- MCP server.
- Homebrew tap.
- Cheaper index refresh on large repositories.

## Research

roust is also a research project. Every mechanism starts as a flag that is
off by default, is gated on a fixed protocol (SWE-bench Lite for tuning, the
held-out Verified set and seven language slices as the check), and either
becomes a default or is written up as a negative result with its artifacts.
The negative results are kept on purpose; they are the more useful half of
the record.

- [Research](docs/RESEARCH.md): the loop, what was adopted, what failed and why.
- [Benchmarks](docs/BENCHMARKS.md): every published number and where it came from.
- [Evaluation record](docs/EVALUATION.md): the complete technical record.
- [`lab/README.md`](https://github.com/narehart/roust/blob/main/lab/README.md):
  the frozen research sandbox, per-round writeups, and raw artifacts.
- [`CHANGELOG.md`](https://github.com/narehart/roust/blob/main/CHANGELOG.md) and [`RELEASE.md`](https://github.com/narehart/roust/blob/main/RELEASE.md): what shipped when, and how.

## License and history

MIT. Formerly `bgrep`; renamed to avoid collision with the binary-grep tool
of that name.
