"""For instances failing File@10: measure (a) definition-symbol anchors — gold file
defines a class/def whose name appears in the issue text; (b) code-block n-gram
overlap — issue's ``` blocks share character 5-grams with the gold file more than
with the files currently outranking it."""
import json, re, subprocess
from pathlib import Path
import pandas as pd

LAB = Path(__file__).resolve().parent
df = pd.read_parquet(LAB / 'swebench_lite.parquet')
inst = {r['instance_id']: r for _, r in df.iterrows()}
rows = {r['instance_id']: r for r in map(json.loads, open(LAB/'results_swebench/abl_hist_v3.jsonl')) if 'error' not in r}

DEF_RE = re.compile(r'^\s*(?:class|def)\s+(\w+)', re.M)
CODEBLOCK_RE = re.compile(r'```[a-z]*\n(.*?)```', re.S)

def checkout(repo_dir, sha):
    subprocess.run(['git','checkout','-f','-q',sha], cwd=repo_dir, capture_output=True, timeout=120)

def grams(text, n=5):
    text = re.sub(r'\s+', ' ', text)
    return {text[i:i+n] for i in range(len(text)-n)}

sym_anchor = 0; sym_cases = []
ng_better = 0; ng_cases = []
fail_insts = []
for iid, r in rows.items():
    gold = set(r['gold_files']); top10 = r['returned_files'][:10]
    if gold <= set(top10): continue
    fail_insts.append(iid)
    meta = inst[iid]
    repo_dir = LAB / 'swebench_repos' / meta['repo'].replace('/', '__')
    checkout(repo_dir, meta['base_commit'])
    text = meta['problem_statement']
    blocks = '\n'.join(CODEBLOCK_RE.findall(text))
    bg = grams(blocks) if len(blocks) > 40 else set()
    inst_sym = False; inst_ng = False
    for g in gold - set(top10):
        p = repo_dir / g
        if not p.exists(): continue
        content = p.read_text(encoding='utf-8', errors='replace')
        defs = set(DEF_RE.findall(content))
        hits = [d for d in defs if len(d) > 3 and re.search(r'\b'+re.escape(d)+r'\b', text)]
        if hits: inst_sym = True; sym_cases.append((iid, g, hits[:4]))
        if bg:
            gscore = len(bg & grams(content)) / max(len(bg),1)
            # compare vs the current top-5 files
            top_scores = []
            for t in top10[:5]:
                tp = repo_dir / t
                if tp.exists():
                    top_scores.append(len(bg & grams(tp.read_text(encoding='utf-8', errors='replace'))) / max(len(bg),1))
            if top_scores and gscore > max(top_scores):
                inst_ng = True; ng_cases.append((iid, g, round(gscore,3), round(max(top_scores),3)))
    sym_anchor += inst_sym; ng_better += inst_ng

print(f"instances failing @10: {len(fail_insts)}")
print(f"  with a DEFINITION-SYMBOL anchor for a stray gold file: {sym_anchor}")
print(f"  where code-block 5-gram overlap ranks stray gold ABOVE all current top-5: {ng_better}")
both = len({c[0] for c in sym_cases} | {c[0] for c in ng_cases})
print(f"  union (either signal): {both}")
cur10 = sum(1 for r in rows.values() if set(r['gold_files']) <= set(r['returned_files'][:10]))
print(f"File@10 ceiling if union-signal instances were fixed: {(cur10+both)/len(rows):.3f}")
print("\nsymbol-anchor cases:")
for c in sym_cases[:20]: print('  ', c)
print("\nngram cases:")
for c in ng_cases[:20]: print('  ', c)
