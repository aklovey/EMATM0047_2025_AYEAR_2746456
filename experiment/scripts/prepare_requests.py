"""Prepare four conditions using exact live vLLM /tokenize; no generation calls."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import random
import urllib.request

ARMS = ['ZERO', 'FULL_COT', 'HEURISTIC_SHORT', 'PNS_COT']
MODEL = 'Qwen/Qwen3.6-35B-A3B'
SYSTEM = 'You are an expert in causal inference. Treat the scenario as a self-contained hypothetical world and reason only from the provided information. Return exactly one JSON object: {"answer":"yes"} or {"answer":"no"}.'
BASE = {'model': MODEL, 'chat_template_kwargs': {'enable_thinking': True, 'preserve_thinking': False},
        'temperature': 1.0, 'top_p': .95, 'top_k': 20, 'min_p': 0.0,
        'repetition_penalty': 1.0, 'presence_penalty': 0.0, 'frequency_penalty': 0.0,
        'n': 1, 'stream': False, 'ignore_eos': False, 'include_stop_str_in_output': False}

def read(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8-sig').splitlines() if s.strip()]

def problem(row):
    return f"Background:\n{row['background']}\n\nGiven information:\n{row['given_info']}\n\nQuestion:\n{row['question']}\n\nCandidate answers:\nYes\nNo"

def messages(target, demos, arm):
    text = ''
    if arm != 'ZERO':
        text = 'You will see 2 worked examples, followed by one target problem. Use the examples as in-context demonstrations of the task and answer format. Then solve the target problem independently and return exactly the required JSON object.\n\n'
        field = {'FULL_COT': 'full_cot', 'HEURISTIC_SHORT': 'heuristic_cot', 'PNS_COT': 'pns_cot'}[arm]
        for i, demo in enumerate(demos, 1):
            final = json.dumps({'answer': demo['gold_answer']}, separators=(',', ':'))
            text += f"=== Worked example {i} ===\n[Problem]\n{problem(demo)}\n\n[Assistant response]\n<think>\n{demo[field]}\n</think>\n\n{final}\n\n"
    text += '=== Target problem ===\n' + problem(target)
    return [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': text}]

def token_count(endpoint, msgs, model):
    body = {'model': model, 'messages': msgs, 'add_generation_prompt': True,
            'chat_template_kwargs': BASE['chat_template_kwargs']}
    request = urllib.request.Request(endpoint, data=json.dumps(body, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.load(response)
    count = result.get('count')
    if not isinstance(count, int):
        tokens = result.get('tokens')
        count = len(tokens) if isinstance(tokens, list) else None
    if not isinstance(count, int) or count <= 0:
        raise ValueError(f'No exact token count returned: {str(result)[:500]}')
    return count

def main(args):
    targets = read(args.targets)
    demos = read(args.demos)
    by_type = {}
    for demo in demos:
        by_type.setdefault(demo['query_type'], []).append(demo)
    for pool in by_type.values():
        pool.sort(key=lambda x: int(x['question_id']))
    output, summary = [], []
    for i, target in enumerate(targets):
        qid = int(target['question_id'])
        eligible = [d for d in by_type.get(target['query_type'], [])
                    if int(d['question_id']) != qid and (not target.get('group_id') or d.get('group_id') != target['group_id'])]
        if len(eligible) < 2:
            raise ValueError(f'Fewer than two group-disjoint demos for q{qid}/{target["query_type"]}')
        selected = random.Random(args.seed + qid).sample(eligible, 2)
        conditions = {arm: messages(target, selected, arm) for arm in ARMS}
        counts = {arm: token_count(args.tokenize_endpoint, msgs, args.model) for arm, msgs in conditions.items()}
        budget = min(args.max_output, args.context - max(counts.values()) - args.reserve)
        order = ARMS[i % len(ARMS):] + ARMS[:i % len(ARMS)]
        for arm in order:
            local = {'target_question_id': qid, 'test_index': target.get('test_index', i + 1), 'arm': arm,
                     'group_id': target.get('group_id'), 'target_query_type': target['query_type'],
                     'demo_question_ids_in_order': [int(d['question_id']) for d in selected] if arm != 'ZERO' else [],
                     'counterfactual_demo_assignment': [int(d['question_id']) for d in selected],
                     'demo_fallback_flags_in_order': [bool(d.get('fallback', False)) for d in selected] if arm != 'ZERO' else [],
                     'serialized_prompt_token_count': counts[arm], 'max_four_arm_prompt_tokens': max(counts.values()),
                     'effective_max_tokens': budget, 'protocol': 'cladder_followup300_20260910_v2_parent_fallback'}
            body = {**BASE, 'model': args.model, 'messages': conditions[arm], 'seed': args.seed + qid, 'max_tokens': budget} if budget > 0 else None
            if body is None:
                local['preflight_error'] = 'fixed_two_shot_exceeds_context'
            output.append({'local_only': local, 'request_body': body})
        summary.append({'question_id': qid, 'prompt_tokens': counts, 'common_max_tokens': budget,
                        'demo_ids': [int(d['question_id']) for d in selected],
                        'fallback_slots': sum(bool(d.get('fallback', False)) for d in selected)})
        if (i + 1) % 20 == 0:
            print(json.dumps({'prepared_targets': i + 1, 'expected_targets': len(targets)}), flush=True)
    p = Path(args.output); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in output), encoding='utf-8')
    p.with_suffix('.token_summary.json').write_text(json.dumps({'targets': len(targets), 'request_rows': len(output),
        'generation_calls': 0, 'exact_tokenize_calls': len(targets) * 4, 'model': args.model,
        'context_errors': sum(r['common_max_tokens'] <= 0 for r in summary),
        'demo_slots_per_fewshot_arm': 2 * len(targets),
        'fallback_slots_per_fewshot_arm': sum(r['fallback_slots'] for r in summary),
        'optimized_slots_per_fewshot_arm': 2 * len(targets) - sum(r['fallback_slots'] for r in summary),
        'rows': summary}, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'PREPARED', 'targets': len(targets), 'requests': len(output), 'generation_calls': 0}))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--targets', required=True)
    p.add_argument('--demos', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--tokenize-endpoint', default='http://127.0.0.1:8000/tokenize')
    p.add_argument('--model', default=MODEL)
    p.add_argument('--seed', type=int, default=20260910)
    p.add_argument('--context', type=int, default=16384)
    p.add_argument('--max-output', type=int, default=12000)
    p.add_argument('--reserve', type=int, default=128)
    main(p.parse_args())
