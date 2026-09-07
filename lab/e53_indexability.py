#!/usr/bin/env python3
"""Read-only attribution of absent source files to index limits or ranking.

Diagnostic mirrors the fixed shipped source suffixes / vendor / size guards;
it does not change gold, enable indexing, or treat eligibility as retrieval.
Git reads are from recorded base commits, never the current working tree.
"""
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
from e51_run import ROOT, SLICES

SUFFIXES = set('.py .ts .js .go .rs .java .kt .cs .swift .tsx .jsx .c .h .cc .cpp .cxx .hpp .hh .rb .pony'.split())
VENDOR = re.compile(r'(vendor|vendored|third_party|node_modules|\.min\.(js|css)$|bundle\.js$|(^|/)(cextern|extern)(/|$)|(^|/)(libsvm|liblinear)(/|$)|(^|/)thirdparty(/|$))', re.I)
TEST = re.compile(r'(?i)(^|/)(tests?|testing|spec|specs|fixtures?|mocks?|__tests__|e2e|docs_src|tutorials?|samples?|demos?|playground|scripts?|integration|t)(/|$)|(^|/)(test_|conftest)|_test\.[A-Za-z0-9]+$|\.test\.|\.spec\.')


def main():
    mining = json.loads((ROOT/'lab/results_regions/e53/mining.json').read_text())
    report = {}
    for sl, data in mining.items():
        counts, repos, rows = Counter(), Counter(), []
        for r in data['instances']:
            repo = ROOT/'lab'/SLICES[sl][1]/r['repo'].replace('/', '__')
            for path in r['source_missing']:
                blob = subprocess.run(['git','show',r['base_commit']+':'+path],cwd=repo,capture_output=True)
                reason = 'eligible_shape'
                if blob.returncode: reason = 'git_read_error'
                elif Path(path).suffix not in SUFFIXES: reason = 'unsupported_suffix'
                elif VENDOR.search(path): reason = 'vendor_guard'
                elif len(blob.stdout) > 2_000_000: reason = 'file_size_guard'
                elif max(map(len,blob.stdout.decode('utf8',errors='replace').splitlines()),default=0) > 3000: reason = 'line_length_guard'
                # No whitespace/token approximation is used as a membership
                # proof: eligible_shape means only these declared guards pass.
                record = dict(instance_id=r['instance_id'],repo=r['repo'],path=path,reason=reason,
                              test_shaped=bool(TEST.search(path)),bytes=len(blob.stdout))
                rows.append(record); counts[reason]+=1; repos[r['repo']]+=1
        report[sl] = dict(counts=dict(counts),by_repo=dict(repos),test_shaped=sum(r['test_shaped'] for r in rows),files=rows)
        print(sl,report[sl]['counts'], 'test_shaped',report[sl]['test_shaped'],flush=True)
    (ROOT/'lab/results_regions/e53/indexability.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
