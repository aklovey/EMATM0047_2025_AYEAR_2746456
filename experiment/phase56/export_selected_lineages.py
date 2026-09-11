import json,pathlib,subprocess
HERE=pathlib.Path(__file__).resolve().parent
REMOTE=r'''
import sqlite3,pathlib,json,sys
sys.stdout.reconfigure(encoding='utf-8')
p=pathlib.Path(r'E:\wt\cause-qwen-pns-adaptive-20260826/artifacts/experiments/qwen_pns_phase56_20260826_v2_recovery_18plus3_v1/journal.sqlite3')
c=sqlite3.connect('file:'+str(p).replace('\\','/')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
for item in c.execute("select qid,result_json from items where state='completed' order by ordinal"):
 art=json.loads(item['result_json'])['artifact'];key=art['selected_request_key']
 row=c.execute('select r.request_key,r.qid,r.branch,r.step_index,r.reasoning_suffix,r.complete_chain,r.final_content,r.prompt_key,r.state,p.frozen_prefix,p.prompt_token_count,p.effective_max_tokens from requests r join prompts p on p.prompt_key=r.prompt_key where r.request_key=?',(key,)).fetchone()
 d=dict(row);d['artifact_final_cot']=art['final_cot'];d['source_journal']=str(p)
 if d['state']=='posting':
  gp=p.parent.parent/'qwen_pns_phase56_20260826_v2/qwen_request_recovery_128_g1.sqlite3'
  g=sqlite3.connect('file:'+str(gp).replace('\\','/')+'?mode=ro',uri=True);g.row_factory=sqlite3.Row
  gr=dict(g.execute('select dispatch_id,state,response_json from recovery_dispatches where source_request_key=?',(key,)).fetchone())
  raw=json.loads(gr['response_json'])['choices'][0]['text']
  suffix,sep,content=raw.partition('</think>')
  assert sep
  d['reasoning_suffix']=suffix;d['complete_chain']=(d['frozen_prefix'] or '')+suffix;d['final_content']=content.strip()
  d['effective_state']='g1_'+gr['state'];d['recovery_dispatch_id']=gr['dispatch_id'];d['recovery_source']=str(gp)
 else:d['effective_state']=d['state']
 print(json.dumps(d,ensure_ascii=False))
'''
r=subprocess.run(['ssh','main-laptop','D:/env/python.exe','-'],input=REMOTE.encode(),capture_output=True,check=True)
rows=[json.loads(x) for x in r.stdout.decode('utf-8').splitlines()]
(HERE/'phase56_selected_lineage52.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
print(json.dumps({'rows':len(rows),'states':sorted(set(x['state'] for x in rows)),'nonempty_chain':sum(bool(x['complete_chain']) for x in rows),'exact_concat':sum((x['frozen_prefix'] or '')+(x['reasoning_suffix'] or '')==x['complete_chain'] for x in rows),'artifact_exact':sum(x['artifact_final_cot']==x['complete_chain'] for x in rows)}))
