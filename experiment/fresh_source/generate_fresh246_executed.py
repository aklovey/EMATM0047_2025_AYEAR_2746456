"""Freeze a new four-type SCM extension using unmodified author generation code."""
import sys,os,json,time,random,math,collections,importlib.metadata as md
from pathlib import Path
R=Path(r'C:\Users\Wyatt\Documents\Codex\transfers\fresh_cladder_feasibility_20260910')
sys.path[:0]=[str(R),str(R/'pydeps'),str(R/'source')];os.chdir(R/'source')
from causalbenchmark.generator import generate_questions
from causalbenchmark.graphs.builders import RandomBuilder
from causalbenchmark.queries import create_query
from independent_calc import from_given,from_scm,answer_for_effect,scalar,parse_params

OUT=R/'freeze246';OUT.mkdir(exist_ok=True)
if (OUT/'manifest.json').exists():raise RuntimeError('Frozen manifest exists; do not overwrite')
BASE_SEED=2026092000;ORDER_SEED=2026092099;QID_START=1100000
QUOTAS={'ate':94,'ett':82,'nde':20,'nie':50}
STORIES={'ate':['smoking_frontdoor'],'ett':['smoking_frontdoor'],'nde':['alarm','blood_pressure','encouagement_program','gender_admission','neg_mediation','penguin'],'nie':['alarm','blood_pressure','encouagement_program','gender_admission','neg_mediation','penguin']}
def signature(m,relevant=False):
    p=m['params'];f=parse_params(p);p={k:(scalar(v) if not f[k.split('(')[1].split('|')[0].split(')')[0].strip()][0] else v) for k,v in p.items()}
    if relevant:
        keys={'frontdoor':['p(V3 | X)','p(Y | V1, V3)'],'mediation':['p(V2 | X)','p(Y | X, V2)']}[m['graph_id']]
        p={k:p[k] for k in keys}
    return json.dumps([m['graph_id'],p],sort_keys=True,separators=(',',':'))
old=json.loads(Path(r'E:\CAUSE\data\cladder-v1-meta-models.json').read_text(encoding='utf-8-sig'))
probe=json.loads((R/'probe8.json').read_text(encoding='utf-8'))
prior=old+probe['models'];old_full={signature(m) for m in prior};old_relevant={signature(m,True) for m in prior if m['graph_id'] in ['frontdoor','mediation']}
seen_full=set();seen_relevant=set();seen_public=set();selected=[];attempts=[];models=[];start=time.monotonic()
protocol={'status':'FROZEN_BEFORE_GENERATION','base_seed':BASE_SEED,'order_seed':ORDER_SEED,'quota':QUOTAS,'stories':STORIES,'generator':'unmodified author RandomBuilder + generate_questions','distribution':'independent Uniform(0,1) over all CPT cells','expected_graphs':{'ate':'frontdoor','ett':'frontdoor','nde':'mediation','nie':'mediation'},'query_polarity':'alternate True/False by within-type accepted target index, set before each generation; no answer-balance selection','qid_start':QID_START,'exclude_full_CPT_sources':['historical meta-models7064','probe8 models','already selected fresh models'],'exclude_relevant_CPT_definition':{'frontdoor':['p(V3 | X)','p(Y | V1, V3)'],'mediation':['p(V2 | X)','p(Y | X, V2)']},'fixed_exclusion_rules':['generation failure or missing query','author answer not yes/no','full or relevant CPT duplicate','full-precision independent numeric disagreement >1e-8','full-precision independent label disagreement','rounded-public probability label disagreement or zero/unknown','duplicate public text'],'model_calls':0,'official_commit':'3d2d1169b4b939a09048a6a75956c8972a93cc38'}
(OUT/'generation_protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'sampling_attempts.jsonl').open('w',encoding='utf-8') as af,(OUT/'all_attempt_models.jsonl').open('w',encoding='utf-8') as mf:
    for ti,(typ,quota) in enumerate(QUOTAS.items()):
        kept=0;attempt=0
        while kept<quota:
            if attempt>=quota*4:raise RuntimeError('fixed candidate cap exceeded for '+typ)
            seed=BASE_SEED+ti*100000+attempt;story=STORIES[typ][attempt%len(STORIES[typ])];polarity=(kept%2==0);attempt+=1
            record={'attempt_index':len(attempts)+1,'query_type':typ,'within_type_attempt':attempt,'seed':seed,'story_id':story,'requested_polarity':polarity,'status':'pending'}
            prevlen=len(models)
            try:
                kwargs={'ask_polarities':True}
                if typ in ['ate','ett']:kwargs.update(ask_treatments=False,ask_outcomes=False)
                queries=[create_query(typ,**kwargs)]
                qs=list(generate_questions(story,RandomBuilder(seed=seed),None,queries,spec_limit=1,model_meta_list=models,include_background=True,include_reasoning=True,seed=seed,pbar=False))
                choices=[(i,q) for i,q in enumerate(qs) if q['meta']['polarity']==polarity]
                if not choices:raise RuntimeError('missing chosen-polarity query')
                official_i,q=choices[0];meta=q['meta'];m=models[meta['model_id']];fs,rs=signature(m),signature(m,True)
                record.update({'author_model_id':meta['model_id'],'author_desc_id':q['desc_id'],'author_query_index':official_i,'author_answer':q['answer'],'author_groundtruth':meta['groundtruth']})
                reasons=[]
                if q['answer'] not in ['yes','no']:reasons.append('author_answer_not_binary')
                if fs in old_full or fs in seen_full:reasons.append('full_CPT_duplicate')
                if rs in old_relevant or rs in seen_relevant:reasons.append('query_relevant_CPT_duplicate')
                a,_=from_given(meta);b,_=from_given(meta,True);c,_=from_scm(m,meta)
                labs=[answer_for_effect(v,meta) for v in [a,b,c]]
                record.update({'independent_given_effect':a,'independent_rounded_public_effect':b,'independent_SCM_effect':c,'independent_labels':labs})
                if abs(a-meta['groundtruth'])>1e-8 or abs(c-meta['groundtruth'])>1e-8:reasons.append('full_precision_numeric_disagreement')
                if labs[0]!=q['answer'] or labs[2]!=q['answer']:reasons.append('full_precision_label_disagreement')
                if labs[1]!=q['answer'] or abs(b)<1e-10:reasons.append('public_precision_label_conflict_or_zero')
                pubtext=q['background']+'\n'+q['given_info']+'\n'+q['question']
                if pubtext in seen_public:reasons.append('public_text_duplicate')
                if reasons:record.update(status='excluded',exclusion_reasons=reasons)
                else:
                    qid=QID_START+len(selected);group='fresh:seed:'+str(seed)
                    selected.append({'question_id':qid,'group_id':group,'generator_seed':seed,'official_question_id':None,'official_query_index_within_model':official_i,'author_desc_id':q['desc_id'],'author_model_id':meta['model_id'],'author_row':q,'model':m,'independent_validation':{'given_effect':a,'public_rounded_effect':b,'SCM_effect':c,'label':q['answer']}})
                    seen_full.add(fs);seen_relevant.add(rs);seen_public.add(pubtext);kept+=1
                    record.update(status='selected',question_id=qid,group_id=group)
            except Exception as e:record.update(status='generation_or_validation_failed',error=repr(e))
            for m in models[prevlen:]:mf.write(json.dumps({'attempt_index':record['attempt_index'],'seed':seed,'author_model':m},ensure_ascii=False)+'\n')
            attempts.append(record);af.write(json.dumps(record,ensure_ascii=False)+'\n');af.flush();mf.flush()
        print('FROZEN_TYPE',typ,kept,'attempts',attempt,flush=True)
selected_order=selected.copy();random.Random(ORDER_SEED).shuffle(selected_order)
public=[];scoring=[]
for i,row in enumerate(selected_order,1):
    q=row['author_row'];meta=q['meta'];e={'test_index':i,'question_id':row['question_id'],'group_id':row['group_id'],'query_type':meta['query_type'],'story_id':meta['story_id'],'graph_id':meta['graph_id'],'background':q['background'],'given_info':q['given_info'],'question':q['question']};public.append(e)
    scoring.append({'question_id':row['question_id'],'group_id':row['group_id'],'query_type':meta['query_type'],'gold_answer':q['answer']})
def writejl(p,rows):p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
writejl(OUT/'targets_public.jsonl',public);writejl(OUT/'targets_scoring_only.jsonl',scoring);writejl(OUT/'selected_source_and_validation246.jsonl',selected)
manifest={**protocol,'status':'OFFLINE_FROZEN_FRESH246_READY_NO_MODEL_CALLS','n':len(selected),'unique_groups':len({r['group_id'] for r in selected}),'unique_full_CPT':len(seen_full),'unique_relevant_CPT':len(seen_relevant),'type_counts':dict(collections.Counter(r['query_type'] for r in public)),'answer_counts':dict(collections.Counter(r['gold_answer'] for r in scoring)),'story_counts':dict(collections.Counter(r['story_id'] for r in public)),'sampling_attempts':len(attempts),'status_counts':dict(collections.Counter(r['status'] for r in attempts)),'exclusion_counts':dict(collections.Counter(v for r in attempts for v in r.get('exclusion_reasons',[]))),'generation_seconds':time.monotonic()-start,'versions':{p:md.version(p) for p in ['pomegranate','omnibelt','omnifig','omniply','numpy','pandas','scipy','networkx']},'official_question_id_note':'Author generate_questions emits desc_id and within-model query index but no global question_id; our evaluation question_id is a separate explicit namespace.'}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');print('MANIFEST',json.dumps(manifest,ensure_ascii=True))
