"""E25 mechanism mining: WHICH syntactic shapes does the per-language
node-kind allowlist emit that the zero-config name+body field rule does not
(and vice versa)?

Replicates both header predicates from roust-rs/src/core.rs in Python
tree-sitter and runs them over the GOLD files of each slice (the files that
actually carry the patch hunks, i.e. the files the metric depends on), then
tallies node kinds by which rule accepts them. Output is the reusable
finding: the allowlist's earned coverage expressed as a list of node kinds.

Rules replicated:
  shape_header_start -- spans >1 line AND ((body field AND (name|declarator
    field)) OR (value field whose node has a body field))
  *_header_start     -- the per-language kind allowlists, incl. their
    conditional cases (mod_item/struct_specifier/... require a body; C++
    -only kinds gated on cpp).
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
from pathlib import Path

import pandas as pd
import tree_sitter_c, tree_sitter_cpp, tree_sitter_go, tree_sitter_java
import tree_sitter_javascript, tree_sitter_rust, tree_sitter_typescript
from tree_sitter import Language, Parser

TS_DECL = {"function_declaration", "generator_function_declaration",
           "class_declaration", "abstract_class_declaration", "method_definition",
           "interface_declaration", "enum_declaration", "module", "internal_module"}
TS_BOUND = {"variable_declarator", "pair", "field_definition", "public_field_definition"}
TS_FN_VALUE = {"function", "function_expression", "arrow_function",
               "generator_function", "class"}
JAVA = {"class_declaration", "interface_declaration", "enum_declaration",
        "record_declaration", "annotation_type_declaration", "method_declaration",
        "constructor_declaration", "compact_constructor_declaration", "static_initializer"}
GO = {"function_declaration", "method_declaration", "type_declaration"}
RUST_ALWAYS = {"function_item", "impl_item", "trait_item", "struct_item",
               "enum_item", "union_item", "macro_definition"}


def allow_hit(node, lang: str) -> bool:
    k = node.type
    if lang in ("js", "ts", "tsx"):
        if k in TS_DECL:
            return True
        if k in TS_BOUND:
            v = node.child_by_field_name("value")
            return v is not None and v.type in TS_FN_VALUE
        return False
    if lang == "java":
        return k in JAVA
    if lang == "go":
        return k in GO
    if lang == "rust":
        if k in RUST_ALWAYS:
            return True
        return k == "mod_item" and node.child_by_field_name("body") is not None
    if lang in ("c", "cpp"):
        cpp = lang == "cpp"
        if k in ("function_definition", "type_definition", "preproc_function_def"):
            return True
        if k in ("struct_specifier", "enum_specifier", "union_specifier"):
            return node.child_by_field_name("body") is not None
        if k == "class_specifier":
            return cpp and node.child_by_field_name("body") is not None
        if k in ("namespace_definition", "template_declaration"):
            return cpp
        return False
    return False


def shape_hit(node) -> bool:
    if node.start_point[0] == node.end_point[0]:   # must span >1 line
        return False
    has_body = node.child_by_field_name("body") is not None
    named = (node.child_by_field_name("name") is not None
             or node.child_by_field_name("declarator") is not None)
    if has_body and named:
        return True
    v = node.child_by_field_name("value")
    return v is not None and v.child_by_field_name("body") is not None


LANGS = {
    "js": Language(tree_sitter_javascript.language()),
    "ts": Language(tree_sitter_typescript.language_typescript()),
    "tsx": Language(tree_sitter_typescript.language_tsx()),
    "java": Language(tree_sitter_java.language()),
    "go": Language(tree_sitter_go.language()),
    "rust": Language(tree_sitter_rust.language()),
    "c": Language(tree_sitter_c.language()),
    "cpp": Language(tree_sitter_cpp.language()),
}
EXT_LANG = {".js": "js", ".jsx": "js", ".ts": "ts", ".tsx": "tsx", ".java": "java",
            ".go": "go", ".rs": "rust", ".c": "c", ".h": "c", ".cc": "cpp",
            ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp"}
DIFF_RE = re.compile(r"^diff --git a/(\S+) b/(\S+)", re.M)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--repos-dir", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    df = pd.read_parquet(args.parquet)
    if args.limit:
        df = df.head(args.limit)
    allow_only = collections.Counter()
    allow_only_multiline = collections.Counter()   # genuine field-rule misses
    allow_only_oneline = collections.Counter()     # dropped only by the >1-line rule
    shape_only = collections.Counter()
    both = collections.Counter()
    n_files = 0
    for _, r in df.iterrows():
        clone = Path(args.repos_dir) / str(r["repo"]).replace("/", "__")
        if not clone.is_dir():
            continue
        for _a, b in DIFF_RE.findall(r["patch"]):
            lang = EXT_LANG.get(Path(b).suffix)
            if lang is None:
                continue
            p = subprocess.run(["git", "show", f"{r['base_commit']}:{b}"], cwd=clone,
                               capture_output=True)
            if p.returncode != 0 or not p.stdout:
                continue
            tree = Parser(LANGS[lang]).parse(p.stdout)
            n_files += 1
            stack = [tree.root_node]
            while stack:
                node = stack.pop()
                stack.extend(node.named_children)
                a, s = allow_hit(node, lang), shape_hit(node)
                if a and s:
                    both[node.type] += 1
                elif a:
                    allow_only[node.type] += 1
                    if node.start_point[0] == node.end_point[0]:
                        allow_only_oneline[node.type] += 1
                    else:
                        allow_only_multiline[node.type] += 1
                elif s:
                    shape_only[node.type] += 1

    tot_a, tot_s = sum(allow_only.values()), sum(shape_only.values())
    print(f"=== {args.label}: {n_files} gold files parsed ===")
    print(f"emitted by BOTH rules: {sum(both.values())}")
    print(f"ALLOWLIST-ONLY (shape MISSES these): {tot_a}")
    for k, v in allow_only.most_common(12):
        print(f"    {k:34} {v:6d}")
    print(f"  of which MULTI-line (true field-rule miss): {sum(allow_only_multiline.values())}")
    for k, v in allow_only_multiline.most_common(8):
        print(f"      {k:32} {v:6d}")
    print(f"  of which ONE-line (dropped by shape's >1-line rule only): "
          f"{sum(allow_only_oneline.values())}")
    for k, v in allow_only_oneline.most_common(5):
        print(f"      {k:32} {v:6d}")
    print(f"SHAPE-ONLY (allowlist misses these): {tot_s}")
    for k, v in shape_only.most_common(12):
        print(f"    {k:34} {v:6d}")
    Path(args.out).write_text(json.dumps(
        {"label": args.label, "n_gold_files": n_files,
         "both": dict(both), "allowlist_only": dict(allow_only),
         "allowlist_only_multiline": dict(allow_only_multiline),
         "allowlist_only_oneline": dict(allow_only_oneline),
         "shape_only": dict(shape_only)}, indent=1))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
