import base64
import gzip
import json
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
REMOTE = r'''
import pathlib,json,sqlite3,gzip,base64,sys
sys.stdout.reconfigure(encoding='ascii')
p=pathlib.Path(r'E:\wt\cause-qwen-pns-adaptive-20260826')
r=p/'artifacts/experiments/qwen_pns_phase56_20260826_v2_recovery_18plus3_v1'
b=p/'artifacts/experiments/qwen_pns_phase56_20260826_v2'
def db(f):
 c=sqlite3.connect('file:'+str(f).replace('\\','/')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
c=db(r/'journal.sqlite3')
items=[]
for row in c.execute('select qid,ordinal,query_type,input_json,state,parent_token_count,result_json,completed_at from items order by ordinal'):
 d=dict(row); d['input']=json.loads(d.pop('input_json'));d['result']=json.loads(d.pop('result_json') or 'null');items.append(d)
request_counts=[dict(x) for x in c.execute('select qid,branch,state,valid,correct,invalid_reason,count(*) as count from requests group by qid,branch,state,valid,correct,invalid_reason')]
candidate_rows=[dict(x) for x in c.execute('select request_key,qid,step_index,branch,rollout,state,valid,correct,invalid_reason,complete_chain,chain_token_count,final_content,parsed_answer from requests where qid in (19407,24494,29833,30257)')]
judge_rows=[]
for f in [r/'cli_proxy_future_semantic_judge.sqlite3',b/'cli_proxy_future_semantic_judge.sqlite3',b/'gpt55_judge_recovery_113_xhigh_strict.sqlite3']:
 j=db(f)
 tables=[x[0] for x in j.execute("select name from sqlite_master where type='table'")]
 for table in tables:
  for row in j.execute('select * from '+table):
   d=dict(row);text=json.dumps(d)
   if any('q'+str(q) in text for q in [19407,24494,29833,30257]):
    for key in list(d):
     if key.endswith('_json') and d[key]:
      try:d[key[:-5]]=json.loads(d.pop(key))
      except:pass
    judge_rows.append({'source_db':str(f),'table':table,'row':d})
files={}
for f in [r/'existing_candidate_review18/terminal_report.json',r/'existing_candidate_review18/batch_manifest.json',r/'existing_candidate_review18/q29833/terminal_report.json',r/'existing_candidate_review18/q29833/candidate_manifest.json',b/'gpt55_judge_recovery_113_xhigh_strict_summary.json',b/'qwen_request_recovery_128_manifest.json']:
 if f.exists():files[str(f.relative_to(p))]=json.loads(f.read_text(encoding='utf-8'))
configs={str(f.relative_to(p)):f.read_text(encoding='utf-8') for f in (p/'configs/experiments').glob('qwen_pns_phase56*.yaml')}
out={'source_root':str(p),'source_journal':str(r/'journal.sqlite3'),'items':items,'request_counts':request_counts,'pending_candidate_rows':candidate_rows,'pending_judge_rows':judge_rows,'reports':files,'configs':configs,'meta':{x[0]:json.loads(x[1]) for x in c.execute('select * from meta')}}
print(base64.b64encode(gzip.compress(json.dumps(out,ensure_ascii=False).encode('utf-8'))).decode())
'''
result = subprocess.run(['ssh','main-laptop','D:/env/python.exe','-'],input=REMOTE.encode(),capture_output=True,check=True)
raw=gzip.decompress(base64.b64decode(result.stdout.strip()))
(HERE/'phase56_source_export.json').write_bytes(raw)
data=json.loads(raw)
canonical=[]
accepted=[]
for x in data['items']:
    inp=x['input']; art=(x['result'] or {}).get('artifact')
    row={'question_id':x['qid'],'query_type':x['query_type'],'gold_answer':inp['gold_answer'],'messages':inp['messages'],'full_cot':inp['parent_reasoning'],'full_cot_tokens':x['parent_token_count'],'pns_cot':art['final_cot'] if art else None,'pns_cot_tokens':art['final_qwen_tokens'] if art else None,'historical_state':x['state'],'closure_status':'accepted' if art else 'failed_no_accepted_chain_at_close','selected_request_key':art.get('selected_request_key') if art else None,'audit':art.get('audit') if art else None,'historical_artifact':art}
    canonical.append(row)
    if art:accepted.append({k:v for k,v in row.items() if k!='historical_artifact'})
def jsonl(name,rows):
    (HERE/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
jsonl('phase56_closure_all56.jsonl',canonical)
jsonl('phase56_accepted52_demo_pool.jsonl',accepted)
jsonl('phase56_original_inputs56.jsonl',[x['input'] for x in data['items']])
jsonl('phase56_pending_candidate_rows.jsonl',data['pending_candidate_rows'])
jsonl('phase56_pending_judge_rows.jsonl',data['pending_judge_rows'])
print(json.dumps({'accepted':len(accepted),'closed_total':len(canonical),'pending':[x['question_id'] for x in canonical if x['pns_cot'] is None],'full_tokens':sum(x['full_cot_tokens'] for x in accepted),'pns_tokens':sum(x['pns_cot_tokens'] for x in accepted),'source_export_bytes':len(raw)}))
