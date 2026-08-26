// Port of lintp's scripts/build-docs.test.ts to node:test (no vitest dep).
// Same coverage: the pure transforms, the markdown-native site conventions,
// llms.txt generation, and a full buildDocs() into a temp dir with a
// broken-internal-link sweep.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import {
  buildDocs,
  colorizeCodeLine,
  firstParagraph,
  generateLlmsTxt,
  preprocess,
  rewriteLinks,
  slugify,
  toComponents,
} from "./build-docs.mjs";

test("slugify matches GitHub-style anchors", () => {
  assert.equal(slugify("Using with coding agents"), "using-with-coding-agents");
  assert.equal(slugify("matches(string, pattern)"), "matchesstring-pattern");
});

test("rewriteLinks maps README and docs links to built pages", () => {
  assert.equal(
    rewriteLinks("see [gs](../README.md#usage) and [b](BENCHMARKS.md#metric)"),
    "see [gs](getting-started.html#usage) and [b](benchmarks.html#metric)",
  );
});

test("rewriteLinks leaves external links alone", () => {
  const md = "[repo](https://github.com/narehart/roust)";
  assert.equal(rewriteLinks(md), md);
});

test("colorizeCodeLine marks pass, fail, and comment lines", () => {
  assert.match(colorizeCodeLine("✓ python"), /class="pass"/);
  assert.match(colorizeCodeLine("✗ nothing indexed"), /class="fail"/);
  assert.match(colorizeCodeLine("# a comment"), /class="cmt"/);
  assert.match(colorizeCodeLine("roust query   # warm cache"), /class="cmt"/);
  assert.equal(colorizeCodeLine("plain code"), "plain code");
});

test("preprocess extracts site:sub, heading notes, and drops skipped sections", () => {
  const { md, notes, sub } = preprocess(
    [
      "# Title",
      "",
      "<!-- site:sub One-line intro. -->",
      "",
      "## Install <!-- note: npm, from source -->",
      "body",
      "",
      "## Contributing <!-- site:skip -->",
      "should not survive",
      "",
      "## Usage",
      "more body",
    ].join("\n"),
  );
  assert.equal(sub, "One-line intro.");
  assert.equal(notes.get("install"), "npm, from source");
  assert.match(md, /## Install\n/);
  assert.doesNotMatch(md, /should not survive/);
  assert.match(md, /## Usage/);
});

test("preprocess drops standalone image and badge lines", () => {
  const { md } = preprocess("![demo](assets/demo.gif)\n\ntext\n");
  assert.doesNotMatch(md, /demo\.gif/);
  assert.match(md, /text/);
});

test("firstParagraph skips headings, blanks, and comments", () => {
  assert.equal(
    firstParagraph("# Title\n\n<!-- c -->\n\nThe intro line.\n\nmore"),
    "The intro line.",
  );
  assert.equal(firstParagraph("# Title\n\n## Only headings"), "");
});

test("generateLlmsTxt derives from the page registry and README intro", () => {
  const txt = generateLlmsTxt();
  assert.match(txt, /^# roust/);
  assert.match(txt, /\[getting-started\]\(https:\/\/narehart\.github\.io\/roust\/getting-started\.html\)/);
  assert.match(txt, /\[benchmarks\]/);
  assert.match(txt, /\[research\]/);
  assert.doesNotMatch(txt, /^- \[\w+\]\([^)]*\): #/m); // note markers stripped
  assert.doesNotMatch(txt, /\*\*/); // plain text: no markdown emphasis survives
});

test("toComponents emits design-system classes", () => {
  const { html, sections } = toComponents(
    ['## Install', '', 'Some `code` here.', '', '```bash title="shell — npm"', 'npm i -g roust', '```', '', '- a', '- b'].join("\n"),
    new Map([["install", "npm, from source"]]),
  );
  assert.match(html, /<h2 class="h2" id="install">install<span class="slash">\/<\/span><\/h2>/);
  assert.match(html, /<p class="p">/);
  assert.match(html, /<code class="ic">/);
  assert.match(html, /<ul class="ul">/);
  assert.match(html, /<div class="cbar">shell — npm<\/div>/);
  assert.doesNotMatch(html, /<pre><code/); // panels replaced marked's default
  assert.equal(sections[0].slug, "install");
  assert.equal(sections[0].note, "npm, from source");
});

test("buildDocs builds every page, assets, and llms.txt", (t) => {
  const outDir = mkdtempSync(path.join(tmpdir(), "roust-docs-"));
  t.after(() => rmSync(outDir, { recursive: true, force: true }));

  const written = buildDocs(outDir);
  for (const file of [
    "getting-started.html",
    "benchmarks.html",
    "research.html",
    "index.html",
    "llms.txt",
  ]) {
    assert.ok(existsSync(path.join(outDir, file)), `${file} missing`);
  }
  assert.ok(existsSync(path.join(outDir, "assets", "docs.css")));
  assert.ok(written.length >= 5);

  // homepage nav tree came from the registry, not hand-maintained HTML
  const home = readFileSync(path.join(outDir, "index.html"), "utf8");
  assert.doesNotMatch(home, /<!-- nav-tree -->/);
  assert.match(home, /href="benchmarks\.html"/);

  // md pages carry crumb, toc tree, and continue tree
  const page = readFileSync(path.join(outDir, "benchmarks.html"), "utf8");
  assert.match(page, /<div class="crumb">/);
  assert.match(page, /class="tree"/);
  assert.match(page, /continue\//);

  // no page ships raw markdown or a broken internal link
  for (const file of ["getting-started.html", "benchmarks.html", "research.html", "index.html"]) {
    const html = readFileSync(path.join(outDir, file), "utf8");
    assert.doesNotMatch(html, /```/, `${file} leaked a markdown fence`);
    const links = [...html.matchAll(/href="([^"#]+)(?:#[^"]*)?"/g)]
      .map((m) => m[1])
      .filter((h) => !h.startsWith("http") && !h.startsWith("mailto"));
    for (const link of links) {
      assert.ok(existsSync(path.join(outDir, link)), `${file} → ${link} is broken`);
    }
  }
});
