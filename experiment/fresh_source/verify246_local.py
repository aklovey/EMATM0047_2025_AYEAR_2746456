from pathlib import Path
import json,math,collections,sys
F=Path(__file__).resolve().parent;sys.path.insert(0,str(F))
from independent_calc import from_given,from_scm,answer_for_effect,scalar,parse_params
def jl(p):return [json.loads(s) for s in p.read_text(encoding='utf-8-sig').splitlines() if s.strip()]
P=F/'freeze246';pub=jl(P/'targets_public.jsonl');gold=jl(P/'targets_scoring_only.jsonl');sel=jl(P/'selected_source_and_validation246.jsonl');attempts=jl(P/'sampling_attempts.jsonl');manifest=json.loads((P/'manifest.json').read_text(encoding='utf-8'))
prior=json.loads(Path(r'D:\CAUSE_DATASETS\dataset21_20260908\source_root\data\cladder-v1-meta-models.json').read_text(encoding='utf-8-sig'))+json.loads((F/'probe8.json').read_text(encoding='utf-8'))['models']
def sig(m,relevant=False):
    factors=parse_params(m['params']);p={k:(scalar(v) if '|' not in k else v) for k,v in m['params'].items()}
    if relevant:p={k:p[k] for k in {'frontdoor':['p(V3 | X)','p(Y | V1, V3)'],'mediation':['p(V2 | X)','p(Y | X, V2)']}[m['graph_id']]}
    return json.dumps([m['graph_id'],p],sort_keys=True,separators=(',',':'))
priorfull={sig(m) for m in prior};priorrel={sig(m,True) for m in prior if m['graph_id'] in ['frontdoor','mediation']};seenfull=set();seenrel=set();errors=[];rowchecks=[]
goldix={r['question_id']:r for r in gold};pubix={r['question_id']:r for r in pub}
for r in sel:
    qid=r['question_id'];m=r['model'];q=r['author_row'];meta=q['meta'];a,_=from_given(meta);b,_=from_given(meta,True);c,_=from_scm(m,meta);f,rel=sig(m),sig(m,True)
    reasons=[]
    if f in priorfull or f in seenfull:reasons.append('full_duplicate')
    if rel in priorrel or rel in seenrel:reasons.append('relevant_duplicate')
    seenfull.add(f);seenrel.add(rel)
    if max(abs(a-meta['groundtruth']),abs(c-meta['groundtruth']))>1e-8:reasons.append('numeric')
    labs=[answer_for_effect(v,meta) for v in [a,b,c]]
    if any(l!=q['answer'] for l in labs):reasons.append('label')
    if goldix[qid]['gold_answer']!=q['answer']:reasons.append('scoring_map')
    for key in ['background','given_info','question']:
        if pubix[qid][key]!=q[key]:reasons.append('public_text_'+key)
    if r['group_id']!=pubix[qid]['group_id'] or r['group_id']!=goldix[qid]['group_id']:reasons.append('group_mapping')
    rowchecks.append({'question_id':qid,'threeway_labels':labs,'author_label':q['answer'],'max_absolute_numeric_error':max(abs(a-meta['groundtruth']),abs(c-meta['groundtruth'])),'errors':reasons})
    if reasons:errors.append({'question_id':qid,'reasons':reasons})
assert len(pub)==len(gold)==len(sel)==246
assert {r['question_id'] for r in pub}=={r['question_id'] for r in gold}=={r['question_id'] for r in sel}
assert len({r['group_id'] for r in pub})==246
assert set(r['test_index'] for r in pub)==set(range(1,247))
assert collections.Counter(r['query_type'] for r in pub)=={'ate':94,'ett':82,'nde':20,'nie':50}
assert all(set(r)=={'test_index','question_id','group_id','query_type','story_id','graph_id','background','given_info','question'} for r in pub)
assert len(attempts)==257 and sum(a['status']=='selected' for a in attempts)==246
assert not errors
summary={'status':'PASS_LOCAL_INDEPENDENT_RECOMPUTATION_FRESH246','n':246,'unique_groups':246,'unique_full_CPT':len(seenfull),'unique_relevant_CPT':len(seenrel),'full_CPT_historical_or_probe_overlap':0,'relevant_CPT_historical_or_probe_overlap':0,'threeway_label_agreement':246,'numeric_agreement':246,'public_field_only':True,'public_text_matches_author_output':True,'sampling_attempts':257,'excluded_attempts':11,'row_errors':errors,'max_numeric_error':max(r['max_absolute_numeric_error'] for r in rowchecks),'model_calls':0,'main300_results_read':False}
(P/'local_independent_verification.json').write_text(json.dumps({'summary':summary,'rows':rowchecks},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True,indent=2))
