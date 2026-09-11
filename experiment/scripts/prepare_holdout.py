"""Offline CLADDER instance-disjoint selection; no model calls or outcome selection."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random

TYPES = ['ate', 'det-counterfactual', 'ett', 'nde', 'nie']

def load(path):
    p = Path(path)
    text = p.read_text(encoding='utf-8-sig')
    if p.suffix == '.jsonl':
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)

def qids(value):
    """Extract explicit qid metadata, never parse IDs out of problem/CoT text."""
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'question_id', 'qid', 'target_question_id', 'demo_question_id'}:
                try:
                    found.add(int(str(item).removeprefix('q')))
                except (TypeError, ValueError):
                    pass
            elif key in {'demo_question_ids_in_order', 'question_ids', 'qids'} and isinstance(item, list):
                for x in item:
                    try:
                        found.add(int(str(x).removeprefix('q')))
                    except (TypeError, ValueError):
                        pass
            elif isinstance(item, (dict, list)):
                found.update(qids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(qids(item))
    return found

def allocate(n, counts):
    total = sum(counts.values())
    quotas = {t: int(n * v / total) for t, v in counts.items()}
    order = sorted(counts, key=lambda t: (-(n * counts[t] / total - quotas[t]), t))
    for t in order[:n - sum(quotas.values())]:
        quotas[t] += 1
    return quotas

def build(args):
    rows = load(args.data)
    models = {int(r['model_id']): r for r in load(args.models)}
    by_id = {int(r['question_id']): r for r in rows}
    excluded = set()
    source_counts = {}
    for path in args.exclude:
        ids = qids(load(path))
        source_counts[str(path)] = len(ids)
        excluded.update(ids)
    excluded.update(args.exclude_qid)
    excluded_groups = {by_id[q]['meta']['model_id'] for q in excluded if q in by_id}
    eligible = [r for r in rows if r['meta']['query_type'] in args.types
                and r['meta']['model_id'] not in excluded_groups]
    counts = Counter(r['meta']['query_type'] for r in eligible)
    quotas = allocate(args.n, counts)
    pools = defaultdict(list)
    for r in eligible:
        pools[r['meta']['query_type']].append(r)
    rng = random.Random(args.seed)
    for values in pools.values():
        values.sort(key=lambda r: int(r['question_id']))
        rng.shuffle(values)
    selected, used_groups = [], set()
    # Start with rare strata. The final estimand is this deduplicated five-type population.
    for typ in sorted(quotas, key=lambda t: (len(pools[t]), t)):
        chosen = 0
        for row in pools[typ]:
            group = row['meta']['model_id']
            if group in used_groups:
                continue
            selected.append(row)
            used_groups.add(group)
            chosen += 1
            if chosen == quotas[typ]:
                break
        if chosen != quotas[typ]:
            raise ValueError(f'{typ}: only {chosen} distinct groups for quota {quotas[typ]}')
    rng.shuffle(selected)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    public, gold = [], []
    for index, row in enumerate(selected, 1):
        mid = int(row['meta']['model_id'])
        entry = {'test_index': index, 'question_id': int(row['question_id']),
                 'group_id': f'model:{mid}', 'query_type': row['meta']['query_type'],
                 'story_id': row['meta']['story_id'], 'graph_id': row['meta']['graph_id'],
                 'background': models[mid]['background'], 'given_info': row['given_info'],
                 'question': row['question']}
        public.append(entry)
        gold.append({'question_id': entry['question_id'], 'group_id': entry['group_id'],
                     'query_type': entry['query_type'], 'gold_answer': row['answer']})
    write_jsonl(out / 'targets_public.jsonl', public)
    write_jsonl(out / 'targets_scoring_only.jsonl', gold)
    report = {'status': 'PREPARED_NO_MODEL_CALLS', 'seed': args.seed, 'n': len(public),
              'unique_groups': len(used_groups), 'stratum_counts': dict(Counter(r['query_type'] for r in public)),
              'eligible_rows': len(eligible), 'eligible_groups': len({r['meta']['model_id'] for r in eligible}),
              'excluded_qids_in_dataset': len(excluded & set(by_id)), 'excluded_groups': len(excluded_groups),
              'exclusion_sources': source_counts, 'exclusions_not_in_dataset': sorted(excluded - set(by_id)),
              'source_data': str(args.data), 'source_models': str(args.models),
              'selection_rule': 'five-type proportional quotas; one target per model_id; no gold/correctness selection',
              'independence_limit': 'All source rows have historical baseline exposure. Known development/demo groups are excluded; unknown historical use and shared graph/story templates remain possible. This is not a fresh benchmark.'}
    (out / 'selection_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))

def write_jsonl(path, rows):
    Path(path).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', required=True)
    p.add_argument('--models', required=True)
    p.add_argument('--exclude', action='append', default=[])
    p.add_argument('--exclude-qid', type=int, action='append', default=[])
    p.add_argument('--types', nargs='+', default=TYPES)
    p.add_argument('--n', type=int, default=300)
    p.add_argument('--seed', type=int, default=20260910)
    p.add_argument('--output', required=True)
    build(p.parse_args())
