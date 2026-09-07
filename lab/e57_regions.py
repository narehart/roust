"""Semantic region packing with bounded navigation context; no gold inputs."""
import ast
from bisect import bisect_right
from functools import lru_cache
import importlib
from pathlib import Path

import tiktoken
from tree_sitter import Language, Parser

from e56_dense import INSTRUCTION, Retriever


@lru_cache(maxsize=16)
def parser_for(suffix):
    key = {".rs": "rust", ".c": "c", ".h": "cpp", ".cc": "cpp", ".cpp": "cpp",
           ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".java": "java", ".go": "go",
           ".js": "javascript", ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript"}.get(suffix)
    if key is None:
        return None
    module = importlib.import_module("tree_sitter_" + key)
    factory = getattr(module, "language_tsx" if suffix == ".tsx" else "language_typescript" if key == "typescript" else "language")
    return Parser(Language(factory()))


def definitions(path, source):
    """Source-only function boundaries, independent of evaluation labels."""
    if path.endswith(".py"):
        try:
            return [(min([n.lineno] + [d.lineno for d in n.decorator_list]), n.end_lineno)
                    for n in ast.walk(ast.parse(source)) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        except (SyntaxError, ValueError):
            return []
    parser = parser_for(Path(path).suffix.lower())
    if parser is None:
        return []
    kinds = {"function_item", "function_definition", "function_declaration", "method_declaration",
             "constructor_declaration", "function_expression", "arrow_function", "method_definition",
             "generator_function", "generator_function_declaration"}
    tree = parser.parse(source.encode())
    result, stack = [], [tree.root_node]
    while stack:
        node = stack.pop()
        stack.extend(node.named_children)
        if node.type not in kinds:
            continue
        # Point.row attribute access corrupts memory in the installed Python
        # 3.13/tree-sitter 0.26.0 combination. Tuple access survives the same
        # corpus repro and matches the established scorer's access pattern.
        start = node.start_point[0] + 1
        if node.parent is not None and node.parent.type in {"template_declaration", "export_statement"}:
            start = node.parent.start_point[0] + 1
        if path.endswith(".rs"):
            prev = node.prev_sibling
            while prev is not None and prev.type == "attribute_item":
                start = prev.start_point[0] + 1
                prev = prev.prev_sibling
        result.append((start, node.end_point[0] + 1))
    return result


def union(spans):
    result = []
    for a, b in sorted(spans):
        if result and a <= result[-1][1] + 1:
            result[-1] = (result[-1][0], max(b, result[-1][1]))
        else:
            result.append((a, b))
    return result


def render(regions, lines):
    return "\n\n".join("### " + path + "\n" + "\n...\n".join(
        "\n".join(lines[path][a - 1:b]) for a, b in spans)
        for path, spans in regions.items() if spans)


class RegionRetriever(Retriever):
    def candidates(self, query, corpus):
        docs, locations = [], []
        for path, source in sorted(corpus.items()):
            encoded = self.tokenizer(source, add_special_tokens=False, return_offsets_mapping=True)
            ids, offsets = encoded["input_ids"], encoded["offset_mapping"]
            line_starts, offset = [], 0
            for line in source.splitlines(keepends=True):
                line_starts.append(offset)
                offset += len(line)
            if not ids or not line_starts:
                continue
            for start in range(0, len(ids), 320):
                stop = min(start + 384, len(ids))
                docs.append(path + "\n" + self.tokenizer.decode(ids[start:stop]))
                a = bisect_right(line_starts, offsets[start][0])
                b = bisect_right(line_starts, max(offsets[start][0], offsets[stop - 1][1] - 1))
                locations.append((path, a, b))
        vectors, cost = self.encode(docs)
        q, qcost = self.encode([INSTRUCTION + query])
        scores = vectors @ q[0]
        order = sorted(range(len(docs)), key=lambda i: (-float(scores[i]), locations[i]))
        return [(float(scores[i]), *locations[i]) for i in order], {"documents": cost, "query": qcost}


def pack(corpus, baseline_regions, ranked, budget=8192):
    """Keep brief navigation seats, then greedily add ranked code regions."""
    encoder = tiktoken.get_encoding("cl100k_base")
    count = lambda s: len(encoder.encode_ordinary(s))
    lines = {p: s.splitlines() for p, s in corpus.items()}
    regions = {}
    # The navigation seat is an actual, nonempty line from the baseline's
    # returned text. It is not a filename-only claim of source coverage.
    for path, spans in baseline_regions.items():
        choices = [i for a, b in spans for i in range(a, b + 1) if lines[path][i - 1].strip()]
        if choices:
            i = min(choices, key=lambda i: (count(lines[path][i - 1]) > 64, i))
            regions[path] = [(i, i)]
    bundle = render(regions, lines)
    if count(bundle) > budget:
        raise ValueError("navigation seats exceed budget")
    seat_tokens = count(bundle)
    defs = {}
    accepted, examined = 0, 0
    for score, path, a, b in ranked[:1000]:
        if path not in defs:
            defs[path] = definitions(path, corpus[path])
        overlap = [(x, y) for x, y in defs[path] if x <= b and y >= a]
        expanded = (min([a] + [x for x, _ in overlap]), max([b] + [y for _, y in overlap]))
        for candidate in dict.fromkeys([expanded, (a, b)]):
            examined += 1
            before = regions.get(path, [])
            after = union(before + [candidate])
            if after == before:
                continue
            trial = dict(regions)
            trial[path] = after
            proposed = render(trial, lines)
            if count(proposed) <= budget:
                regions, bundle = trial, proposed
                accepted += 1
    assert set(baseline_regions) <= set(regions), "lost a baseline navigation file"
    return regions, bundle, {"bundle_tokens": count(bundle), "seat_tokens": seat_tokens,
                             "accepted_regions": accepted, "examined_regions": examined}
