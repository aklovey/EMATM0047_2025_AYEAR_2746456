"""Assemble 52 accepted plus four explicit parent fallbacks; freeze main/dev inputs."""
from __future__ import annotations
from argparse import Namespace
from collections import Counter as Counts
import json
from pathlib import Path
import random
from heuristic_short import Counter, compress
from prepare_holdout import build, qids, write_jsonl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OLD = Path(r'C:\Users\aklovey\Documents\Codex\2026-08-17\qwen36-fewshot-icl-pilot')
DATA = Path(r'D:\CAUSE_DATASETS\dataset21_20260908\source_root\data')
CORE = Path(r'C:\Users\aklovey\cause_handoffs\qwen36_full10112_cot_screened_pns_20260816\tiers\pns_core_ready.jsonl')
def read(p):
    return [json.loads(s) for s in p.read_text(encoding='utf-8-sig').splitlines() if s.strip()]

accepted = {int(r['question_id']): r for r in read(ROOT / 'work/evidence/phase56/phase56_accepted52_demo_pool.jsonl')}
original_path = ROOT / 'work/evidence/phase56/phase56_original_inputs56.jsonl'
original = read(original_path)
dataset = json.loads((DATA / 'cladder-v1-balanced.json').read_text(encoding='utf-8'))
by_id = {int(r['question_id']): r for r in dataset}
models = {int(r['model_id']): r for r in json.loads((DATA / 'cladder-v1-meta-models.json').read_text(encoding='utf-8'))}
assert len(original) == 56 and len(accepted) == 52
assert qids(original).issubset(qids(read(CORE))), 'Additional phase groups must be included explicitly'
tok = Counter(OLD / 'work/tokenizer/tokenizer.json', OLD / 'work/pydeps')
pool = []
for index, source in enumerate(original):
    qid = int(source['question_id']); raw = by_id[qid]; mid = int(raw['meta']['model_id'])
    full = source['parent_reasoning']; fallback = qid not in accepted
    if not fallback:
        assert accepted[qid]['full_cot'] == full
    pns = full if fallback else accepted[qid]['pns_cot']
    budget = tok.count(pns)
    heuristic, details = compress(full, budget, tok)
    actual = tok.count(heuristic)
    row = {'question_id': qid, 'group_id': f'model:{mid}', 'query_type': source['query_type'],
           'gold_answer': source['gold_answer'], 'background': models[mid]['background'],
           'given_info': raw['given_info'], 'question': raw['question'], 'full_cot': full,
           'pns_cot': pns, 'heuristic_cot': heuristic, 'fallback': fallback,
           'phase56_status': 'failed_parent_fallback_for_new_icl_only' if fallback else 'accepted',
           'selected_request_key': None if fallback else accepted[qid]['selected_request_key'],
           'length_audit': {'full_tokens': tok.count(full), 'pns_tokens': budget, 'heuristic_tokens': actual,
                            'absolute_gap': actual - budget, 'relative_gap': (actual - budget) / budget,
                            'within_tolerance': abs(actual - budget) <= max(16, .05 * budget), **details}}
    if fallback:
        assert full == pns == heuristic
    pool.append(row)
    if (index + 1) % 10 == 0:
        print(json.dumps({'prepared_demos': index + 1, 'expected': len(original)}), flush=True)
assert all(r['length_audit']['within_tolerance'] for r in pool)
assert all(n >= 2 for n in Counts(r['query_type'] for r in pool).values())
write_jsonl(HERE / 'canonical56_with_heuristic.jsonl', pool)
challenge = OLD / 'outputs/plan/qwentest100.jsonl'
build(Namespace(data=DATA / 'cladder-v1-balanced.json', models=DATA / 'cladder-v1-meta-models.json',
                exclude=[CORE, challenge, original_path], exclude_qid=[],
                types=['ate', 'det-counterfactual', 'ett', 'nde', 'nie'], n=300, seed=20260910, output=HERE / 'freeze300'))
main = read(HERE / 'freeze300/targets_public.jsonl')
main_groups = {r['group_id'] for r in main}
demo_groups = {r['group_id'] for r in pool}
rng = random.Random(20260910)
smoke = []
used_groups = set()
challenge_qids = qids(read(challenge))
for typ in ['ate', 'det-counterfactual', 'ett', 'nde', 'nie']:
    eligible = [by_id[q] for q in sorted(challenge_qids) if by_id[q]['meta']['query_type'] == typ
                and f"model:{by_id[q]['meta']['model_id']}" not in main_groups | demo_groups]
    rng.shuffle(eligible)
    n = 0
    for raw in eligible:
        mid = int(raw['meta']['model_id']); group = f'model:{mid}'
        if group in used_groups:
            continue
        used_groups.add(group)
        smoke.append({'test_index': len(smoke) + 1, 'question_id': int(raw['question_id']), 'group_id': group,
                      'query_type': typ, 'story_id': raw['meta']['story_id'], 'graph_id': raw['meta']['graph_id'],
                      'background': models[mid]['background'], 'given_info': raw['given_info'], 'question': raw['question']})
        n += 1
        if n == 2:
            break
    assert n == 2, f'No smoke pair for {typ}'
(HERE / 'dev10').mkdir(exist_ok=True)
write_jsonl(HERE / 'dev10/targets_public.jsonl', smoke)
write_jsonl(HERE / 'dev10/targets_scoring_only.jsonl', [{'question_id': r['question_id'], 'group_id': r['group_id'],
             'query_type': r['query_type'], 'gold_answer': by_id[r['question_id']]['answer']} for r in smoke])
report = {'status': 'READY_FOR_EXACT_PROMPT_TOKENIZATION', 'generation_calls': 0,
          'pool_total': len(pool), 'accepted': len(accepted), 'parent_fallback': 4,
          'fallback_qids': [r['question_id'] for r in pool if r['fallback']],
          'type_counts': dict(Counts(r['query_type'] for r in pool)),
          'full_cot_tokens': sum(r['length_audit']['full_tokens'] for r in pool),
          'pns_policy_tokens': sum(r['length_audit']['pns_tokens'] for r in pool),
          'heuristic_tokens': sum(r['length_audit']['heuristic_tokens'] for r in pool),
          'max_abs_heuristic_gap': max(abs(r['length_audit']['absolute_gap']) for r in pool),
          'main_targets': 300, 'dev_targets': 10,
          'main_vs_demo_group_overlap': len(main_groups & demo_groups),
          'main_vs_dev_group_overlap': len(main_groups & used_groups),
          'dev_vs_demo_group_overlap': len(used_groups & demo_groups),
          'main_generation_budget': 1200, 'dev_generation_budget': 40}
(HERE / 'input_preparation_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2), flush=True)
