"""Content-stable function/gap units for incremental semantic indexing."""
from e57_regions import definitions


def source_units(path, source):
    lines = source.splitlines(keepends=True)
    outer = []
    for a, b in sorted(definitions(path, source), key=lambda s: (s[0], -s[1])):
        a, b = max(1, a), min(len(lines), b)
        if a > b:
            continue
        if outer and a <= outer[-1][1]:
            outer[-1] = (outer[-1][0], max(outer[-1][1], b))
        else:
            outer.append((a, b))
    result, cursor = [], 1
    for a, b in outer + [(len(lines) + 1, len(lines))]:
        if cursor < a:
            text = "".join(lines[cursor - 1:a - 1])
            if text.strip():
                result.append((cursor, a - 1, text))
        if a <= b:
            result.append((a, b, "".join(lines[a - 1:b])))
        cursor = b + 1
    return result


def documents(tokenizer, corpus, ast_units):
    docs = []
    for path, source in sorted(corpus.items()):
        units = source_units(path, source) if ast_units else [(1, len(source.splitlines()), source)]
        for _, _, text in units:
            ids = tokenizer.encode(text, add_special_tokens=False)
            for start in range(0, max(1, len(ids)), 320):
                docs.append(path + "\n" + tokenizer.decode(ids[start:start + 384]))
    return docs
