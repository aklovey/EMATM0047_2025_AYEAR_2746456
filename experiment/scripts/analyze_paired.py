"""Paired strict-denominator CLADDER evaluation; missing/failed responses count wrong.

Input --arm ARM=attempts.jsonl accepts the historical runner's attempts schema:
question_id, terminal_status, latency_seconds, extracted.{content,finish_reason,usage}.
Also accepts rows with the extracted fields at top level. Only score-file gold is used.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import numpy as np
from scipy.stats import binomtest

def read(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]

def strict_answer(content):
    if not isinstance(content, str):
        return None
    try:
        parsed = json.loads(content.strip())
    except (ValueError, TypeError):
        return None
    return parsed['answer'] if isinstance(parsed, dict) and set(parsed) == {'answer'} and parsed['answer'] in {'yes', 'no'} else None

def numeric(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and np.isfinite(value) else None

def summarize_values(values):
    clean = [v for v in values if v is not None]
    return {'observed_count': len(clean), 'missing_count': len(values) - len(clean),
            'sum': sum(clean) if clean else None, 'mean': float(np.mean(clean)) if clean else None,
            'median': float(np.median(clean)) if clean else None,
            'p95': float(np.quantile(clean, .95)) if clean else None}

def score_rows(targets, attempts, arm):
    by_id = {}
    for row in attempts:
        qid = int(row.get('question_id', row.get('target_question_id')))
        if qid in by_id:
            raise ValueError(f'{arm}: duplicate terminal qid {qid}; select policy before analysis')
        by_id[qid] = row
    extra = set(by_id) - {int(r['question_id']) for r in targets}
    if extra:
        raise ValueError(f'{arm}: responses outside frozen target manifest: {sorted(extra)[:10]}')
    scored = []
    for target in targets:
        qid = int(target['question_id'])
        a = by_id.get(qid, {})
        e = a.get('extracted', a)
        status = a.get('terminal_status', a.get('status', 'completed' if a else 'missing'))
        api_ok = bool(a) and status in {'completed', 'ok', 'success'} and a.get('http_status', 200) == 200
        answer = strict_answer(e.get('content')) if api_ok else None
        usage = e.get('usage') or {}
        scored.append({'question_id': qid, 'group_id': target.get('group_id', f'q:{qid}'),
                       'query_type': target.get('query_type', 'unknown'), 'arm': arm,
                       'gold_answer': target['gold_answer'], 'predicted_answer': answer,
                       'correct': int(answer is not None and answer == target['gold_answer']),
                       'format_valid': int(answer is not None), 'api_ok': int(api_ok),
                       'status': status, 'truncated': int(e.get('finish_reason') == 'length'),
                       'prompt_tokens': numeric(usage.get('prompt_tokens')),
                       'completion_tokens': numeric(usage.get('completion_tokens')),
                       'total_tokens': numeric(usage.get('total_tokens')),
                       'latency_seconds': numeric(a.get('latency_seconds'))})
    return scored

def cluster_ci(differences, groups, rng, reps):
    group_indices = defaultdict(list)
    for i, g in enumerate(groups):
        group_indices[g].append(i)
    pieces = list(group_indices.values())
    totals = np.array([sum(differences[i] for i in ix) for ix in pieces], dtype=float)
    sizes = np.array([len(ix) for ix in pieces], dtype=float)
    boot = np.empty(reps)
    for start in range(0, reps, 1000):
        take = min(1000, reps - start)
        draws = rng.integers(0, len(pieces), (take, len(pieces)))
        boot[start:start + take] = totals[draws].sum(axis=1) / sizes[draws].sum(axis=1)
    return [float(v) for v in np.quantile(boot, [.025, .975])]

def compare(candidate, reference, rng, reps):
    ca = np.array([r['correct'] for r in candidate])
    re = np.array([r['correct'] for r in reference])
    delta = ca - re
    gain = int(((ca == 1) & (re == 0)).sum())
    loss = int(((ca == 0) & (re == 1)).sum())
    discordant = gain + loss
    p = float(binomtest(gain, discordant, .5).pvalue) if discordant else 1.0
    groups = [r['group_id'] for r in candidate]
    prompt_pairs = [(a['prompt_tokens'], b['prompt_tokens']) for a, b in zip(candidate, reference)
                    if a['prompt_tokens'] is not None and b['prompt_tokens'] is not None]
    full_usage = len(prompt_pairs) == len(candidate)
    prompt_ratio = None
    if prompt_pairs and sum(b for a, b in prompt_pairs) > 0:
        prompt_ratio = 1 - sum(a for a, b in prompt_pairs) / sum(b for a, b in prompt_pairs)
    valid_pairs = [(a, b) for a, b in zip(candidate, reference) if a['format_valid'] and b['format_valid']]
    return {'n': len(candidate), 'gain': gain, 'loss': loss, 'both_correct': int(((ca == 1) & (re == 1)).sum()),
            'both_wrong': int(((ca == 0) & (re == 0)).sum()),
            'accuracy_delta': float(delta.mean()), 'paired_cluster_bootstrap_ci95': cluster_ci(delta, groups, rng, reps),
            'mcnemar_exact_p': p, 'mcnemar_scope': 'independent instances' if len(set(groups)) == len(groups) else 'item-level diagnostic; repeated instances make iid p-value approximate',
            'both_format_valid_n': len(valid_pairs), 'both_format_valid_delta_diagnostic':
                sum(a['correct'] - b['correct'] for a, b in valid_pairs) / len(valid_pairs) if valid_pairs else None,
            'prompt_token_saving_fraction': prompt_ratio, 'prompt_pairs_observed': len(prompt_pairs),
            'prompt_cost_complete': full_usage}

def main(args):
    targets = read(args.targets)
    if not targets or len({int(r['question_id']) for r in targets}) != len(targets):
        raise ValueError('Targets empty or duplicate qid')
    arms = {}
    for spec in args.arm:
        name, path = spec.split('=', 1)
        if name in arms:
            raise ValueError(f'duplicate arm {name}')
        arms[name] = score_rows(targets, read(path), name)
    rng = np.random.default_rng(args.seed)
    report = {'n_frozen_targets': len(targets), 'unique_groups': len({r.get('group_id', r['question_id']) for r in targets}),
              'primary_denominator': 'all frozen targets; missing/API/format failures wrong',
              'claim': 'paired accuracy difference estimation and measured token cost; no non-inferiority claim',
              'bootstrap_replicates': args.bootstrap, 'bootstrap_seed': args.seed,
              'arms': {}, 'comparisons': {}, 'by_query_type': {}}
    for name, rows in arms.items():
        valid = sum(r['format_valid'] for r in rows)
        correct = sum(r['correct'] for r in rows)
        report['arms'][name] = {'correct': correct, 'strict_accuracy': correct / len(rows),
                               'format_valid': valid, 'valid_only_accuracy_diagnostic': correct / valid if valid else None,
                               'api_fail_or_missing': sum(not r['api_ok'] for r in rows),
                               'truncated': sum(r['truncated'] for r in rows),
                               'status_counts': dict(Counter(r['status'] for r in rows)),
                               **{k: summarize_values([r[k] for r in rows]) for k in ['prompt_tokens', 'completion_tokens', 'total_tokens', 'latency_seconds']}}
        for typ in sorted({r['query_type'] for r in rows}):
            subset = [r for r in rows if r['query_type'] == typ]
            report['by_query_type'].setdefault(typ, {})[name] = {'n': len(subset), 'correct': sum(r['correct'] for r in subset), 'accuracy': np.mean([r['correct'] for r in subset]).item()}
    comparison_specs = args.compare or ['PNS_COT:FULL_COT', 'PNS_COT:HEURISTIC_SHORT', 'PNS_COT:ZERO']
    for spec in comparison_specs:
        candidate, reference = spec.split(':')
        if candidate not in arms or reference not in arms:
            raise ValueError(f'Missing arm for {spec}')
        report['comparisons'][spec] = compare(arms[candidate], arms[reference], rng, args.bootstrap)
    ordered = sorted(report['comparisons'], key=lambda k: report['comparisons'][k]['mcnemar_exact_p'])
    current = 0.0
    for i, key in enumerate(ordered):
        current = min(1.0, max(current, (len(ordered) - i) * report['comparisons'][key]['mcnemar_exact_p']))
        report['comparisons'][key]['mcnemar_holm_p'] = current
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'paired_analysis.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    all_rows = [r for rows in arms.values() for r in rows]
    with (out / 'scored_all_frozen_targets.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0]))
        writer.writeheader(); writer.writerows(all_rows)
    lines = ['# Four-condition paired comparison', '', f'The primary denominator contains all {len(targets)} frozen targets. API failures, missing responses and format failures count as incorrect.', '',
             '| Condition | Correct/total | Strict accuracy | Format valid | API failure/missing | Input tokens (observed) | Output tokens (observed) |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for name, r in report['arms'].items():
        lines.append(f"| {name} | {r['correct']}/{len(targets)} | {r['strict_accuracy']:.2%} | {r['format_valid']} | {r['api_fail_or_missing']} | {r['prompt_tokens']['sum']} | {r['completion_tokens']['sum']} |")
    lines += ['', '| Comparison | Difference | Paired 95% CI | gain/loss | McNemar p | Holm p | Input saving |', '|---|---:|---|---:|---:|---:|---:|']
    for name, r in report['comparisons'].items():
        lo, hi = r['paired_cluster_bootstrap_ci95']
        saving = f"{r['prompt_token_saving_fraction']:.2%}" if r['prompt_token_saving_fraction'] is not None else 'missing'
        lines.append(f"| {name} | {r['accuracy_delta']:+.2%} | [{lo:+.2%}, {hi:+.2%}] | {r['gain']}/{r['loss']} | {r['mcnemar_exact_p']:.6g} | {r['mcnemar_holm_p']:.6g} | {saving} |")
    lines += ['', 'CIs are percentile intervals obtained by resampling instance groups with replacement. Missing usage is not counted as zero. Where cost records are incomplete, token totals cover observed calls only. Summed request latency is not GPU wall-clock time.', '', 'Non-significance cannot be interpreted as equivalence or non-inferiority. This analysis specified no non-inferiority margin.']
    (out / 'paired_analysis.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'n': len(targets), 'arms': list(arms), 'output': str(out)}, indent=2))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--targets', required=True)
    p.add_argument('--arm', action='append', required=True, help='ARM=attempts.jsonl')
    p.add_argument('--compare', action='append', help='CANDIDATE:REFERENCE')
    p.add_argument('--bootstrap', type=int, default=20000)
    p.add_argument('--seed', type=int, default=20260910)
    p.add_argument('--output', required=True)
    main(p.parse_args())
