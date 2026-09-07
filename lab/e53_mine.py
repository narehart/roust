#!/usr/bin/env python3
"""Audit absent-file evidence without mutating benchmark checkouts.

Companions are same-directory C source/header stems and JS implementation /
TypeScript declarations, including index.js/index.d.ts. Gold is used only
for labels after candidates have been generated from retrieved files.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path
import subprocess
import sys
import pandas as pd
from e51_mine import SOURCE_EXT
from e51_run import SLICES, ROOT
sys.path.insert(0, str(ROOT / 'parity'))
from region_eval import parse_gold_hunks


def companions(path):
    for ext, alternatives in [('.c', ['.h']), ('.h', ['.c']),
                              ('.js', ['.d.ts']), ('.jsx', ['.d.ts']),
                              ('.d.ts', ['.js', '.jsx', '.tsx'])]:
        if path.endswith(ext):
            return [path[:-len(ext)] + alt for alt in alternatives]
    return []


def main():
    report = {}
    for sl, old in [('jsts', 'jsts_ts40ship'), ('c', 'c_ts40ship'), ('java', 'java_ts40ship')]:
        pq, repos, n = SLICES[sl]
        gold = ROOT / 'lab' / pq
        predfile = ROOT / 'lab/results_regions/e47/arms' / (old + '.jsonl')
        preds = {r['instance_id']: r for r in map(json.loads, predfile.read_text().splitlines())}
        rows = pd.read_parquet(gold).to_dict('records')
        assert len(rows) == len(preds) == n and set(preds) == {r['instance_id'] for r in rows}
        details, counts, ext_counts = [], Counter(), Counter()
        for row in rows:
            pred = preds[row['instance_id']]
            assert row['base_commit'] == pred['base_commit']
            goldpaths = set(parse_gold_hunks(row['patch']))
            retrieved = list(pred.get('regions', {})) if not pred.get('error') else []
            repo = ROOT / 'lab' / repos / row['repo'].replace('/', '__')
            paths = set(subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', row['base_commit']], cwd=repo, text=True).splitlines())
            # Ordered by source rank, then declared extension order; cap 2 is
            # a diagnostic candidate policy, not fitted to gold labels.
            candidates = list(dict.fromkeys(p for f in retrieved for p in companions(f)
                                            if p in paths and p not in retrieved))
            missing = goldpaths - set(retrieved)
            source = {p for p in missing if Path(p).suffix.lower() in SOURCE_EXT}
            named = sorted(p for p in source if Path(p).name in row['problem_statement'])
            proposed = candidates[:2]
            counts.update(instances=1, errors=int(bool(pred.get('error'))), missing_source_files=len(source),
                          missing_named_basename=len(named), candidates=len(candidates),
                          proposed=len(proposed), gold_proposed=len(set(proposed) & goldpaths),
                          source_gold_proposed=len(set(proposed) & source),
                          file_rescues=int(bool(missing) and missing.issubset(proposed)))
            ext_counts.update(Path(p).suffix for p in source)
            details.append(dict(instance_id=row['instance_id'], repo=row['repo'], base_commit=row['base_commit'],
                                missing=sorted(missing), source_missing=sorted(source), named=named,
                                candidates=candidates, proposed=proposed, gold_proposed=sorted(set(proposed)&goldpaths)))
        report[sl] = dict(gold_sha256=hashlib.sha256(gold.read_bytes()).hexdigest(),
                          predictions_sha256=hashlib.sha256(predfile.read_bytes()).hexdigest(),
                          counts=dict(counts), missing_extensions=dict(ext_counts), instances=details)
        print(sl, dict(counts), flush=True)
    out = ROOT / 'lab/results_regions/e53/mining.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
