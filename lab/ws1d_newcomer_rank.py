import json,subprocess,os,re,statistics
import pandas as pd
recs=[json.loads(l) for l in open('lab/results_regions/ws1_ceiling_records.jsonl')]
df=pd.read_parquet('lab/mswe_jsts.parquet')
ps={r['instance_id']:r['problem_statement'] for _,r in df.iterrows()}
CODE={'.py','.js','.jsx','.ts','.tsx','.java','.go','.rs','.c','.h','.cc','.cpp','.cxx','.hpp','.hh','.mjs','.cjs'}
tok=lambda s: set(w.lower() for w in re.findall(r'[A-Za-z_][A-Za-z0-9_]{2,}',s))
res=[]
for r in recs:
    iid=r['instance_id']
    if iid not in ps: continue
    repo=f"lab/mswe_repos_e23/{r['slug']}"
    if not os.path.isdir(repo): continue
    out=subprocess.run(['git','-C',repo,'ls-tree','-r','--name-only',r['base_commit']],capture_output=True,text=True)
    if out.returncode: continue
    files=[f for f in out.stdout.split() if os.path.splitext(f)[1].lower() not in CODE]
    q=tok(ps[iid])
    sc=lambda f: len(q & tok(re.sub(r'[/\-._]',' ',f)))
    scored=sorted(files,key=lambda f:(-sc(f),f))
    ranks=[scored.index(g)+1 for g in r['outside'] if g in scored]
    if ranks: res.append((iid,min(ranks),len(files)))
    if len(res)>=40: break
print("instances measured:",len(res))
for k in (1,5,10,20):
    print(f"  gold newcomer within top-{k} by path-token overlap: {sum(1 for _,rk,_ in res if rk<=k)}/{len(res)}")
print("median rank:",statistics.median(rk for _,rk,_ in res),"median newcomer pool:",statistics.median(n for _,_,n in res))
print("worst:",sorted(res,key=lambda x:-x[1])[:4])
