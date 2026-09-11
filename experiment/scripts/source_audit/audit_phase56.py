"""Independent deterministic component audit. No model calls, no source writes."""
from pathlib import Path
import ast,operator,itertools,json,csv,re,sys,collections,math

W=Path(r'C:\Users\aklovey\Documents\Codex\2026-09-10\9-4-cause-1-8-8')
SRC=W/'work/evidence/phase56';OUT=W/'outputs/evidence';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,r'C:\Users\aklovey\Documents\Codex\2026-08-17\qwen36-fewshot-icl-pilot\work\pydeps')
from tokenizers import Tokenizer
TOKPATH=Path(r'C:\Users\aklovey\Documents\Codex\2026-08-17\qwen36-fewshot-icl-pilot\work\tokenizer\tokenizer.json')
tok=Tokenizer.from_file(str(TOKPATH))
def jl(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
originals=jl(SRC/'phase56_original_inputs56.jsonl');accepted={r['question_id']:r for r in jl(SRC/'phase56_accepted52_demo_pool.jsonl')}
lineages={r['qid']:r for r in jl(SRC/'phase56_selected_lineage52.jsonl')}
pending=jl(SRC/'phase56_pending_candidate_rows.jsonl')
data={r['question_id']:r for r in json.loads(Path(r'D:\CAUSE_DATASETS\dataset21_20260908\source_root\data\cladder-v1-balanced.json').read_text(encoding='utf-8-sig'))}
models={r['model_id']:r for r in json.loads(Path(r'D:\CAUSE_DATASETS\dataset21_20260908\source_root\data\cladder-v1-meta-models.json').read_text(encoding='utf-8-sig'))}

BINOPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow}
def safe_number(s):
    s=s.strip().replace('−','-').replace('×','*').replace('÷','/').replace('^','**')
    if len(s)>500:raise ValueError('expression too long')
    tree=ast.parse(s,mode='eval')
    if sum(1 for _ in ast.walk(tree))>150:raise ValueError('too many AST nodes')
    def visit(n):
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float,bool)):return float(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub,ast.Not)):
            x=visit(n.operand);return x if isinstance(n.op,ast.UAdd) else (-x if isinstance(n.op,ast.USub) else float(not x))
        if isinstance(n,ast.BoolOp):
            vals=[bool(visit(x)) for x in n.values];return float(all(vals) if isinstance(n.op,ast.And) else any(vals))
        if isinstance(n,ast.BinOp) and type(n.op) in BINOPS:
            x,y=visit(n.left),visit(n.right)
            if isinstance(n.op,ast.Pow) and (abs(y)>10 or abs(x)>1e6):raise ValueError('power limit')
            return BINOPS[type(n.op)](x,y)
        if isinstance(n,(ast.List,ast.Tuple)) and len(n.elts)==1:return visit(n.elts[0])
        raise ValueError('unsupported AST')
    v=visit(tree.body)
    if not math.isfinite(v):raise ValueError('nonfinite')
    return v

def source_arithmetic(expr,det=False):
    parts=[x.strip() for x in expr.split('=')]
    if parts and parts[0]=='Y':parts=parts[1:]
    try:
        vals=[safe_number(p) for p in parts]
        if len(vals)<2:return {'status':'UNKNOWN_NO_EQUALITY','text':expr}
        tol=1e-10 if det else .005000001
        error=max(vals)-min(vals)
        return {'status':'PASS' if error<=tol else 'NUMERIC_MISMATCH','text':expr,'values':vals,'absolute_gap':error,'tolerance':tol}
    except (ValueError,SyntaxError,ZeroDivisionError,OverflowError) as e:
        adjacent=bool(re.search(r'\)\s+\d',expr))
        return {'status':'AMBIGUOUS_ADJACENT_PRODUCTS' if adjacent else 'UNSUPPORTED_EXPRESSION','text':expr,'error':str(e)[:150],'note':'No explicit operator between adjacent products; do not infer an arithmetic error solely from parser rejection.' if adjacent else 'Parser coverage limitation, not by itself proof of mathematical error.'}

def scalar(v):
    while isinstance(v,list) and len(v)==1:v=v[0]
    return float(v)

def parse_params(params):
    factors={}
    for key,val in params.items():
        m=re.fullmatch(r'p\(([^|)]+)(?:\|([^)]+))?\)',key)
        if not m:raise ValueError('unsupported parameter key '+key)
        var=m.group(1).strip();parents=[x.strip() for x in (m.group(2) or '').split(',') if x.strip()]
        factors[var]=(parents,val)
    return factors

def probability_one(factor,assignment):
    parents,val=factor
    for pa in parents:val=val[assignment[pa]]
    return scalar(val)

def joint(factors,intervention=None):
    intervention=intervention or {};variables=list(factors);rows=[]
    for bits in itertools.product([0,1],repeat=len(variables)):
        a=dict(zip(variables,bits));prob=1.
        for v in variables:
            if v in intervention:prob*=float(a[v]==intervention[v])
            else:
                p=probability_one(factors[v],a);prob*=p if a[v] else 1-p
        if prob>1e-15:rows.append((a,prob))
    if abs(sum(p for _,p in rows)-1)>1e-8:raise ValueError('joint distribution not normalized')
    return rows

def deterministic_counterfactual(model,meta):
    f=parse_params(model['params']);roots=[v for v,(pa,_) in f.items() if not pa]
    conditional=[v for v,(pa,_) in f.items() if pa]
    for v in conditional:
        def flatten(x):
            if isinstance(x,list):return [a for y in x for a in flatten(y)]
            return [x]
        if any(x not in [0,1] for x in flatten(f[v][1])):raise ValueError('nondeterministic downstream kernel')
    def propagate(rootvalues,action=None):
        a=dict(rootvalues)
        if action is not None:a[meta['treatment']]=action
        remain=set(f)-set(a)
        while remain:
            ready=[v for v in remain if all(pa in a for pa in f[v][0])]
            if not ready:raise ValueError('cycle or unresolved variable')
            for v in ready:a[v]=int(probability_one(f[v],a));remain.remove(v)
        return a
    worlds=[]
    for bits in itertools.product([0,1],repeat=len(roots)):
        rv=dict(zip(roots,bits)); factual=propagate(rv)
        prior=math.prod(probability_one(f[v],{}) if rv[v] else 1-probability_one(f[v],{}) for v in roots)
        if prior<=0 or any(factual[v]!=val for v,val in meta['given_info'].items()):continue
        counterfactual=propagate(rv,meta['action']);worlds.append({'roots':rv,'factual':factual,'do':counterfactual,'prior':prior})
    outcomes=sorted({w['do'][meta['outcome']] for w in worlds})
    if len(outcomes)!=1:raise ValueError('counterfactual not uniquely determined from evidence')
    truth=int(outcomes[0]==meta['polarity'])
    return {'effect_or_truth':truth,'outcome_under_do':outcomes[0],'compatible_worlds':worlds,'formula':'Enumerate binary exogenous roots consistent with factual evidence; replace treatment equation by action and re-evaluate deterministic CPTs; compare Y_do with requested polarity.'}

def from_given(meta,rounded=False):
    g=meta['given_info']
    def tr(x):return [tr(v) for v in x] if isinstance(x,list) else round(x,2)
    if rounded:g={k:tr(v) for k,v in g.items()}
    typ=meta['query_type'];graph=meta['graph_id']
    if graph=='frontdoor' and typ in {'ate','ett','nie'}:
        m=g['p(V3 | X)'];y=g['p(Y | X, V3)']
        if typ=='ett':return (m[1]-m[0])*(y[1][1]-y[1][0]),'(m1-m0)*(y11-y10)'
        x=scalar(g['p(X)']);return (m[1]-m[0])*((1-x)*(y[0][1]-y[0][0])+x*(y[1][1]-y[1][0])),'(m1-m0)*[(1-pX)*(y01-y00)+pX*(y11-y10)]'
    if graph=='mediation' and typ in {'nie','nde'}:
        m=g['p(V2 | X)'];y=g['p(Y | X, V2)']
        if typ=='nie':return (m[1]-m[0])*(y[0][1]-y[0][0]),'(m1-m0)*(y01-y00)'
        return (1-m[0])*(y[1][0]-y[0][0])+m[0]*(y[1][1]-y[0][1]),'(1-m0)*(y10-y00)+m0*(y11-y01)'
    if graph=='arrowhead' and typ=='nie':
        y=g['p(Y | X, V3)'];m=g['p(V3 | X, V2)'];z=scalar(g['p(V2)'])
        return (y[0][1]-y[0][0])*((1-z)*(m[1][0]-m[0][0])+z*(m[1][1]-m[0][1])),'(y01-y00)*[(1-pZ)*(m10-m00)+pZ*(m11-m01)]; evaluates supplied estimand, not proof that it identifies natural indirect effect'
    if graph=='diamondcut' and typ=='ate':
        y=g['p(Y | V1, X)'];z=scalar(g['p(V1)'])
        return (1-z)*(y[0][1]-y[0][0])+z*(y[1][1]-y[1][0]),'(1-pZ)*(y01-y00)+pZ*(y11-y10)'
    raise ValueError('unsupported type/graph')

def from_scm(model,meta):
    typ=meta['query_type'];graph=meta['graph_id'];p=model['params'];f=parse_params(p)
    if typ=='ate' or (typ=='nie' and graph=='frontdoor'):
        return sum(a['Y']*q for a,q in joint(f,{'X':1}))-sum(a['Y']*q for a,q in joint(f,{'X':0})),'Truncated factorization do(X=1)-do(X=0); frontdoor has no direct X->Y edge, so NIE equals ATE.'
    if typ=='ett' and graph=='frontdoor':
        obs=joint(f);px=sum(q for a,q in obs if a['X']==1);pu=[sum(q for a,q in obs if a['X']==1 and a['V1']==u)/px for u in [0,1]]
        y=p['p(Y | V1, V3)'];m=p['p(V3 | X)'];return sum(pu[u]*(y[u][1]-y[u][0])*(m[1]-m[0]) for u in [0,1]),'Sum_u P(u|X=1)*(m1-m0)*(y_u1-y_u0) from complete frontdoor CPTs.'
    if graph=='mediation' and typ in {'nie','nde'}:
        return from_given({'given_info':p,'graph_id':graph,'query_type':typ})
    if typ=='nie' and graph=='arrowhead':
        z=scalar(p['p(V2)']);m=p['p(V3 | X, V2)'];y=p['p(Y | X, V2, V3)']
        return sum(([1-z,z][k])*(m[1][k]-m[0][k])*(y[0][k][1]-y[0][k][0]) for k in [0,1]),'Pure NIE under modular independent-noise binary SCM: sum_z P(z)*(m1z-m0z)*(y0z1-y0z0). Additional cross-world assumption is explicit.'
    raise ValueError('SCM scope unsupported')

def answer_for_effect(value,meta):
    if meta['query_type']=='det-counterfactual':return 'yes' if value else 'no'
    if abs(value)<1e-10:return 'UNKNOWN_ZERO_EFFECT'
    positive_requested=bool(meta['polarity'])
    if meta['query_type']=='ett':
        if meta.get('treated') is not True or meta.get('result') is not True:raise ValueError('ETT language variant unsupported')
        positive_requested=not positive_requested # less likely under untreated counterfactual means positive treated-minus-untreated effect
    return 'yes' if ((value>0)==positive_requested) else 'no'

def numeric_equalities(text):
    """Conservative extraction of pure arithmetic LHS = single numeric RHS.
    Every mismatch is a local flag, NEVER a whole semantic-path rejection.
    """
    results=[];offset=0
    for line in text.splitlines(keepends=True):
        norm=line.replace('−','-').replace('×','*').replace('÷','/').replace('\\times','*').replace('\\cdot','*').replace('≈','=')
        norm=re.sub(r'\\frac\{([0-9.+\-*/ ]+)\}\{([0-9.+\-*/ ]+)\}',r'(\1)/(\2)',norm)
        for eq in re.finditer('=',norm):
            left=norm[:eq.start()];right=norm[eq.end():]
            lm=re.search(r'([0-9.()+\-*/\s]+)$',left);rm=re.match(r'\s*([0-9.()+\-*/\s]+)',right)
            if not lm or not rm:continue
            expr=lm.group(1).strip();rv=rm.group(1).strip().rstrip('.')
            if not re.search(r'\d\s*[-+*/]|\)\s*[-+*/]',expr):continue
            if re.match(r'\s*%',right[rm.end():]):continue
            try:lv=safe_number(expr);rhs=safe_number(rv)
            except (ValueError,SyntaxError,ZeroDivisionError,OverflowError):continue
            constant=re.fullmatch(r'[-+]?\d+(?:\.(\d+))?',rv)
            decimals=len(constant.group(1) or '') if constant else None
            tol=max(1e-9,.5*10**(-decimals)) if decimals is not None else 1e-8
            gap=abs(lv-rhs);status='PASS' if gap<=tol+1e-9 else 'LOCAL_ARITHMETIC_FLAG'
            context=text[max(0,offset-400):min(len(text),offset+len(line)+400)]
            correction=bool(re.search(r'\b(wait|wrong|mistake|incorrect|correct(?:ion|ed)?|recalculate|actually|instead|sorry)\b',context,re.I))
            results.append({'line_offset':offset,'line':line.strip(),'lhs':expr,'rhs':rv,'lhs_value':lv,'rhs_value':rhs,'tolerance':tol,'absolute_gap':gap,'status':status,'near_correction_or_scratch_language':correction})
        offset+=len(line)
    return results

def trace_checks(orig,acc,lineage):
    parent=orig['parent_reasoning'];segs=orig['segments'];nt=lambda t:len(tok.encode(t,add_special_tokens=False).ids)
    spans=[s['char_start']==(0 if i==0 else segs[i-1]['char_end']) and parent[s['char_start']:s['char_end']]==s['text'] and s['char_start']<=s['semantic_end']<=s['char_end'] for i,s in enumerate(segs)]
    out={'segment_count':len(segs),'segment_all_text_and_bounds_exact':all(spans),'segments_concat_equals_parent':''.join(s['text'] for s in segs)==parent,'last_segment_reaches_parent_end':bool(segs and segs[-1]['char_end']==len(parent)),'independent_parent_tokens':nt(parent),'parent_stored_tokens':orig['parent_reasoning_tokens_stored'],'parent_final_answer_matches_gold':bool(re.fullmatch(r'\s*\{"answer"\s*:\s*"'+orig['gold_answer']+r'"\}\s*',orig['parent_final_content'])),'full_natural_language_semantics':'UNKNOWN_NOT_COVERED_BY_DETERMINISTIC_COMPONENT_AUDIT'}
    if not acc:
        out['accepted_output']='NONE';out['selected_lineage_status']='NOT_APPLICABLE_NO_ACCEPTED_OUTPUT';return out
    cot=acc['pns_cot'];out.update({'accepted_output':'PRESENT','candidate_tokens':nt(cot),'strictly_shorter':nt(cot)<nt(parent),'pool_full_cot_equals_original_parent':acc['full_cot']==parent,'pool_parent_token_count_matches':acc['full_cot_tokens']==nt(parent),'pool_candidate_token_count_matches':acc['pns_cot_tokens']==nt(cot),'selected_request_key':acc['selected_request_key']})
    out['candidate_last_explicit_json_answer']=(re.findall(r'\{\s*"answer"\s*:\s*"(yes|no)"\s*\}',cot) or [None])[-1]
    out['candidate_last_explicit_answer_matches_gold']=out['candidate_last_explicit_json_answer']==orig['gold_answer'] if out['candidate_last_explicit_json_answer'] is not None else None
    out['reasoning_json_extraction_is_not_final_scoring']='Diagnostic only: reasoning may quote both allowed JSON alternatives. Score the separate raw final_content, not the last quoted template.'
    if not lineage:out['selected_lineage_status']='UNKNOWN_NO_RAW_LINEAGE';return out
    prefix=lineage.get('frozen_prefix',lineage.get('prefix'));suffix=lineage.get('reasoning_suffix',lineage.get('suffix'));chain=lineage['complete_chain']
    out.update({'selected_lineage_status':'CHECKED','lineage_fields':list(lineage),'prefix_plus_suffix_equals_chain':prefix+suffix==chain if isinstance(prefix,str) and isinstance(suffix,str) else None,'raw_complete_chain_equals_accepted_cot':chain==cot,'raw_state':lineage.get('state'),'effective_state':lineage.get('effective_state'),'recovery_source':lineage.get('recovery_source')})
    branch=lineage['branch'];step=lineage['step_index'];seg=next((s for s in segs if s['step_index']==step),None)
    expected=parent[:seg['char_end']] if branch=='keep' and seg else (parent[:seg['char_start']] if branch=='delete' and seg else None)
    out['branch']=branch;out['step_index']=step;out['prefix_expected_from_parent_matches']=prefix==expected if expected is not None else None
    out['prefix_answer_exposed_marker']=seg['answer_exposed_prefix'] if seg else None
    final=lineage.get('final_content','');m=re.fullmatch(r'\s*\{\s*"answer"\s*:\s*"(yes|no)"\s*\}\s*',final)
    out['raw_final_content_exact_lowercase_json']=bool(m)
    try:
        finalobj=json.loads(final);ans=finalobj['answer'].lower() if isinstance(finalobj,dict) and set(finalobj)=={'answer'} and isinstance(finalobj['answer'],str) else None
        out['raw_final_content_strict_json']=ans in ['yes','no'];out['raw_final_content_answer']=ans;out['raw_final_answer_matches_gold']=ans==orig['gold_answer']
    except (ValueError,KeyError,TypeError):
        out['raw_final_content_strict_json']=False;out['raw_final_content_answer']=None;out['raw_final_answer_matches_gold']=False
    return out

# Safety and false-positive regressions: chained arithmetic is evaluated in full.
assert source_arithmetic('0.01 * (0.43 - 0.83)+ 0.82 * (0.50 - 0.73)= 0.33')['status']=='NUMERIC_MISMATCH'
assert source_arithmetic('Y = [1] = 1 or 0',True)['status']=='PASS'
assert all(x['status']=='PASS' for x in numeric_equalities('0.49*0.58+0.40*0.42=0.2842+0.168=0.4522'))
try:safe_number('__import__("os").system("not allowed")');raise AssertionError('unsafe AST accepted')
except ValueError:pass

rows=[]
for orig in originals:
    q=orig['question_id'];d=data[q];meta=d['meta'];model=models[meta['model_id']];acc=accepted.get(q);row={'question_id':q,'query_type':meta['query_type'],'graph_id':meta['graph_id'],'model_id':meta['model_id'],'asset_status':'accepted' if acc else 'failed_no_accepted_output','gold_answer':d['answer'],'source_effect_or_truth':meta['groundtruth'],'source_question':d['question'],'source_estimand':meta.get('estimand',meta.get('formal_form'))}
    row['source_metadata_matches_frozen_input']=meta==orig['audit_reference']['offline_oracle']['source_meta']
    row['source_step5']=source_arithmetic(d['reasoning']['step5'],meta['query_type']=='det-counterfactual')
    try:
        if meta['query_type']=='det-counterfactual':
            calc=deterministic_counterfactual(model,meta);effect=calc['effect_or_truth'];row['recalculation']=calc;scmeffect=effect;publiceffect=effect
            row['source_step5_outcome_matches_recomputed_do']=row['source_step5'].get('values',[None])[0]==calc['outcome_under_do']
        else:
            effect,formula=from_given(meta);publiceffect,pubformula=from_given(meta,True);scmeffect,scmformula=from_scm(model,meta)
            row['recalculation']={'effect_or_truth':effect,'formula':formula,'rounded_public_probabilities_effect':publiceffect,'rounded_public_formula':pubformula,'SCM_effect':scmeffect,'SCM_formula':scmformula}
        row.update({'recomputed_label':answer_for_effect(effect,meta),'rounded_public_label':answer_for_effect(publiceffect,meta),'SCM_label':answer_for_effect(scmeffect,meta),'given_estimand_numeric_matches_source':abs(effect-meta['groundtruth'])<1e-8,'SCM_numeric_matches_source':abs(scmeffect-meta['groundtruth'])<1e-8,'given_estimand_minus_source':effect-meta['groundtruth'],'SCM_minus_source':scmeffect-meta['groundtruth']})
        row['recomputed_label_matches_gold']=row['recomputed_label']==d['answer'];row['rounded_public_label_matches_gold']=row['rounded_public_label']==d['answer'];row['SCM_label_matches_gold']=row['SCM_label']==d['answer'];row['oracle_component_status']='RECOMPUTED'
    except Exception as e:row['oracle_component_status']='UNKNOWN';row['oracle_error']=str(e)
    row['trace_checks']=trace_checks(orig,acc,lineages.get(q))
    if acc:
        checks=numeric_equalities(acc['pns_cot']);row['candidate_numeric_equalities']=checks;row['candidate_numeric_equalities_extracted']=len(checks);row['candidate_local_arithmetic_flags']=sum(c['status']!='PASS' for c in checks)
    else:
        cands=[r for r in pending if r['qid']==q];row['pending_candidate_count']=len(cands);row['pending_candidate_state_counts']=dict(collections.Counter(c['state'] for c in cands));row['pending_saved_correct_count']=sum(bool(c.get('correct')) for c in cands)
        row['candidate_numeric_equalities_extracted']=None;row['candidate_local_arithmetic_flags']=None
    rows.append(row)

summary={'input_count':len(rows),'accepted':len(accepted),'failed':len(rows)-len(accepted),'query_types':dict(collections.Counter(r['query_type'] for r in rows)),'source_step5_status_counts':dict(collections.Counter(r['source_step5']['status'] for r in rows)),'oracle_component_status_counts':dict(collections.Counter(r['oracle_component_status'] for r in rows)),'label_agreement':{k:sum(r.get(k) is True for r in rows) for k in ['recomputed_label_matches_gold','rounded_public_label_matches_gold','SCM_label_matches_gold']},'numeric_value_agreement':{k:sum(r.get(k) is True for r in rows) for k in ['given_estimand_numeric_matches_source','SCM_numeric_matches_source']},'source_numeric_mismatch_qids':[r['question_id'] for r in rows if r.get('given_estimand_numeric_matches_source') is False],'SCM_numeric_mismatch_qids':[r['question_id'] for r in rows if r.get('SCM_numeric_matches_source') is False],'tokenizer':str(TOKPATH),'tokenizer_add_special_tokens':False,'model_calls':0,'full_semantic_labels':'UNKNOWN for all; no human/expert labels and no empirical full-Judge FPR/FNR estimated.'}
summary['accepted_trace_checks']={k:{'pass':sum(r['trace_checks'].get(k) is True for r in rows if r['asset_status']=='accepted'),'fail':sum(r['trace_checks'].get(k) is False for r in rows if r['asset_status']=='accepted'),'unknown':sum(r['trace_checks'].get(k) is None for r in rows if r['asset_status']=='accepted')} for k in ['segment_all_text_and_bounds_exact','segments_concat_equals_parent','strictly_shorter','pool_full_cot_equals_original_parent','pool_parent_token_count_matches','pool_candidate_token_count_matches','prefix_plus_suffix_equals_chain','raw_complete_chain_equals_accepted_cot','prefix_expected_from_parent_matches','raw_final_content_strict_json','raw_final_content_exact_lowercase_json','raw_final_answer_matches_gold']}
summary['all56_source_trace_checks']={k:sum(r['trace_checks'].get(k) is True for r in rows) for k in ['segment_all_text_and_bounds_exact','segments_concat_equals_parent','last_segment_reaches_parent_end','parent_final_answer_matches_gold']}
summary['all36_deterministic_source_step5_outcomes_agree']=sum(r.get('source_step5_outcome_matches_recomputed_do') is True for r in rows)
summary['legacy_parent_stored_token_count_differences']={'n':sum(r['trace_checks']['parent_stored_tokens']!=r['trace_checks']['independent_parent_tokens'] for r in rows),'note':'Legacy stored field does not equal independently tokenized parent_reasoning. Preserve raw value and use common tokenizer for current comparison, not evidence of changed text.'}
summary['candidate_arithmetic']={'accepted_with_extracted_equalities':sum((r['candidate_numeric_equalities_extracted'] or 0)>0 for r in rows),'extracted_equalities':sum(r['candidate_numeric_equalities_extracted'] or 0 for r in rows),'flagged_equalities':sum(r['candidate_local_arithmetic_flags'] or 0 for r in rows),'accepted_with_flags':sum((r['candidate_local_arithmetic_flags'] or 0)>0 for r in rows),'flagged_qids':[r['question_id'] for r in rows if (r['candidate_local_arithmetic_flags'] or 0)>0],'note':'Flags are local numeric expressions and may be scratch work later corrected; not full-path errors.'}
summary['accepted_token_counts']={'original':sum(r['trace_checks']['independent_parent_tokens'] for r in rows if r['asset_status']=='accepted'),'compressed':sum(r['trace_checks']['candidate_tokens'] for r in rows if r['asset_status']=='accepted')}
summary['failed_qids']=[r['question_id'] for r in rows if r['asset_status']!='accepted']
summary['full_source_token_count']=sum(r['trace_checks']['independent_parent_tokens'] for r in rows)
summary['reasoning_JSON_diagnostic_context_review']={
    '9577':{'finding':'uppercase_No_not_semantic_disagreement','evidence':'Reasoning repeatedly commits Answer: No and ends with {"answer":"No"}; separate final_content is same. Lowercase-only regex misses it.','scope':'Answer commitment/context only, not full semantic calibration.'},
    '23635':{'finding':'uppercase_No_not_semantic_disagreement','evidence':'Reasoning states indirect effect is positive, so negative-effect question answer is No; JSON answer is No with uppercase N.','scope':'Answer commitment/context only, not full semantic calibration.'},
    '20959':{'finding':'last_lowercase_no_is_quoted_output_template','evidence':'After Final answer: {"answer":"yes"}, reasoning says Check formatting: {"answer":"yes"} or {"answer":"no"}. Final_content is yes.','scope':'Quoted alternatives are not final answer commitments.'},
    '30505':{'finding':'last_lowercase_no_is_quoted_output_template','evidence':'Reasoning quotes Return exactly one JSON object: {"answer":"yes"} or {"answer":"no"}; later Final decision: Yes. Final_content is yes.','scope':'Quoted alternatives are not final answer commitments.'}
}
(OUT/'phase56_independent_component_audit.json').write_text(json.dumps({'summary':summary,'items':rows},ensure_ascii=False,indent=2),encoding='utf-8')
flat=[]
for r in rows:
    x={k:r.get(k) for k in ['question_id','query_type','graph_id','model_id','asset_status','gold_answer','recomputed_label','rounded_public_label','SCM_label','given_estimand_numeric_matches_source','SCM_numeric_matches_source','given_estimand_minus_source','SCM_minus_source','candidate_numeric_equalities_extracted','candidate_local_arithmetic_flags']}
    x.update({'source_step5_status':r['source_step5']['status'],'source_step5':r['source_step5']['text'],'source_oracle':r['source_effect_or_truth'],'recomputed_given_estimand':r.get('recalculation',{}).get('effect_or_truth'),'recomputed_SCM':r.get('recalculation',{}).get('SCM_effect'),'full_semantic_status':'UNKNOWN'})
    x.update({k:v for k,v in r['trace_checks'].items() if not isinstance(v,(dict,list))})
    flat.append(x)
keys=list(dict.fromkeys(k for x in flat for k in x))
with (OUT/'phase56_independent_component_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(flat)
print(json.dumps(summary,ensure_ascii=True,indent=2))
