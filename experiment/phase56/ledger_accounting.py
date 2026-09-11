import json
import pathlib
import subprocess

HERE=pathlib.Path(__file__).resolve().parent
REMOTE=r'''
import pathlib,json,sqlite3,collections,sys
sys.stdout.reconfigure(encoding='utf-8')
p=pathlib.Path(r'E:\wt\cause-qwen-pns-adaptive-20260826/artifacts/experiments')
base=p/'qwen_pns_phase56_20260826_v2'
recovery=p/'qwen_pns_phase56_20260826_v2_recovery_18plus3_v1'
out={}
def db(f):
 c=sqlite3.connect('file:'+str(f).replace('\\','/')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
for f in [base/'deepseek_semantic_judge.sqlite3',base/'gpt55_judge_recovery_113.sqlite3',base/'gpt55_judge_recovery_113_xhigh_strict.sqlite3',base/'cli_proxy_future_semantic_judge.sqlite3',recovery/'cli_proxy_future_semantic_judge.sqlite3']:
 c=db(f); summary={'path':str(f),'rows':0,'states':{},'result_status':{},'provider_call_count_sum':0,'usage_sum':{},'provider_count_missing_completed':0}
 for row in c.execute('select * from judge_evidence'):
  summary['rows']+=1;state=row['state'];summary['states'][state]=summary['states'].get(state,0)+1
  if row['result_json']:
   r=json.loads(row['result_json']);status=r.get('status');summary['result_status'][status]=summary['result_status'].get(status,0)+1
   pc=r.get('provider_call_count')
   if pc is None:summary['provider_count_missing_completed']+=1
   else:summary['provider_call_count_sum']+=pc
   for k,v in (r.get('usage') or {}).items():
    if isinstance(v,(int,float)):summary['usage_sum'][k]=summary['usage_sum'].get(k,0)+v
 out[str(f.relative_to(p))]=summary
f=base/'qwen_request_recovery_128_g1.sqlite3';c=db(f)
out['qwen_g1']={'states':[dict(x) for x in c.execute('select state,count(*) as n from recovery_dispatches group by state')],'rows':128}
c=db(recovery/'journal.sqlite3')
out['qwen_original']={'states':[dict(x) for x in c.execute('select state,count(*) as n from requests group by state')],'branches':[dict(x) for x in c.execute('select branch,count(*) as n from requests group by branch')],'rollout_ge6':c.execute('select count(*) from requests where rollout>=6').fetchone()[0], 'usage_sum':{}}
for row in c.execute('select provider_usage_json from requests where provider_usage_json is not null'):
 for k,v in json.loads(row[0]).items():
  if isinstance(v,(int,float)):out['qwen_original']['usage_sum'][k]=out['qwen_original']['usage_sum'].get(k,0)+v
print(json.dumps(out,ensure_ascii=False))
'''
result=subprocess.run(['ssh','main-laptop','D:/env/python.exe','-'],input=REMOTE.encode(),capture_output=True,check=True)
obj=json.loads(result.stdout)
(HERE/'phase56_ledger_accounting.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(obj,ensure_ascii=False,indent=2))
