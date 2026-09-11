"""Parse Qwen self-reviews without treating them as independent truth labels."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
from prepare_self_review import CRITERIA, VALUES, read_jsonl, write_jsonl

def check_schema(value):
    if not isinstance(value, dict) or set(value) != {*CRITERIA, 'overall', 'brief_summary'}:
        return 'root_keys_or_type'
    if value['overall'] not in VALUES or not isinstance(value['brief_summary'], str):
        return 'overall_or_summary'
    for key in CRITERIA:
        item = value[key]
        if not isinstance(item, dict) or set(item) != {'verdict', 'quote', 'reason'}:
            return f'{key}_keys_or_type'
        if item['verdict'] not in VALUES or not all(isinstance(item[x], str) for x in ('quote', 'reason')):
            return f'{key}_field_type'
    return None

def parse_attempt(attempt, candidate):
    loc = candidate['local_only']; ex = attempt.get('extracted') or {}
    out = {'blind_audit_id': loc['blind_audit_id'], 'question_id': loc['target_question_id'],
           'source_status': loc['source_status'], 'source_request_key': loc['source_request_key'],
           'query_type': loc['target_query_type'], 'terminal_status': attempt.get('terminal_status', 'not_dispatched'),
           'review_status': None, 'effective_overall': 'unknown', 'reported_overall': None,
           'criteria': None, 'usage': ex.get('usage'), 'latency_seconds': attempt.get('latency_seconds'),
           'response_model': ex.get('response_model'), 'raw_response_path': attempt.get('raw_response_path'),
           'finish_reason': ex.get('finish_reason'), 'review': None, 'validation_notes': []}
    # A well-formed partial answer does not turn a truncated review into a success.
    if ex.get('finish_reason') == 'length':
        out['review_status'] = 'review_truncated'
        return out
    if out['terminal_status'] != 'completed':
        out['review_status'] = 'review_' + out['terminal_status']
        out['error'] = attempt.get('error')
        return out
    text = ex.get('content')
    if not isinstance(text, str) or not text.strip():
        out['review_status'] = 'review_empty_final'
        return out
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        out['review_status'] = 'review_parse_error'
        return out
    error = check_schema(value)
    if error:
        out['review_status'] = 'review_schema_error'
        out['error'] = error
        return out
    out['review'] = value
    out['reported_overall'] = value['overall']
    out['criteria'] = {key: value[key]['verdict'] for key in CRITERIA}
    grades = list(out['criteria'].values())
    derived = 'fail' if 'fail' in grades else 'unknown' if 'unknown' in grades else 'pass'
    out['derived_overall'] = derived
    if derived != value['overall']:
        out['review_status'] = 'review_overall_inconsistent'
        out['validation_notes'].append('reported_overall_disagrees_with_criterion_rule')
    else:
        out['review_status'] = 'review_parsed'
        out['effective_overall'] = derived
    inp = candidate['review_input']
    texts = [inp['candidate_reasoning'], inp['candidate_final_content'] or '',
             *[x['content'] for x in inp['public_problem_messages']]]
    out['quote_checks'] = {}
    for key in CRITERIA:
        quote = value[key]['quote']
        exact = not quote or any(quote in text for text in texts)
        out['quote_checks'][key] = {'empty': not bool(quote), 'exact_source_match': exact, 'characters': len(quote)}
        if not exact:
            out['validation_notes'].append(f'{key}_quote_not_verbatim')
        if len(quote) > 180:
            out['validation_notes'].append(f'{key}_quote_over_180_characters')
    return out

def analyze(attempts, candidates):
    by_qid = {}
    for row in attempts:
        if row['arm'] != 'SELF_REVIEW':
            raise ValueError('Unexpected arm in self-review attempts')
        qid = int(row['question_id'])
        if qid in by_qid:
            raise ValueError('Duplicate self-review response identity')
        by_qid[qid] = row
    records = [parse_attempt(by_qid.get(int(c['local_only']['target_question_id']), {}), c) for c in candidates]
    usage = Counter()
    for r in records:
        usage.update({k: v for k, v in (r.get('usage') or {}).items() if isinstance(v, (int, float))})
    groups = {}
    for group in sorted({r['source_status'] for r in records}):
        rows = [r for r in records if r['source_status'] == group]
        groups[group] = {'candidates': len(rows), 'effective_overall_counts': dict(Counter(r['effective_overall'] for r in rows)),
                         'review_status_counts': dict(Counter(r['review_status'] for r in rows))}
    summary = {'method': 'same_generator_Qwen3.6_public_only_single_self_review', 'candidate_count': len(records),
               'expected_generation_calls_upper': len(candidates), 'unknown_is_not_pass': True,
               'review_status_counts': dict(Counter(r['review_status'] for r in records)),
               'effective_overall_counts': dict(Counter(r['effective_overall'] for r in records)),
               'criterion_counts_among_parsed': {key: dict(Counter(r['criteria'][key] for r in records if r['criteria'])) for key in CRITERIA},
               'source_groups': groups, 'reported_usage_sum': dict(usage),
               'latency_seconds_sum': sum(r.get('latency_seconds') or 0 for r in records),
               'records_with_quote_notes': sum(bool(r['validation_notes']) for r in records),
               'independent_human_or_external_ground_truth': False,
               'changes_to_main_evaluation_or_demo_policy': False,
               'limitations': ['Same-model self-review is correlated with the generator and may repeat its mistakes.',
                              'The 52 historically accepted and four selected unaccepted candidates are a fixed diagnostic set, not a random population sample.',
                              'Self-review disagreement with historical acceptance is a diagnostic signal, not an independently verified error rate.',
                              'No review, parse failure, unknown response, or truncation is retried; main evaluation data and policy are unchanged.']}
    return records, summary

def load_attempts(run_dir):
    root = Path(run_dir)
    source = root / 'SELF_REVIEW.attempts.jsonl'
    if source.exists():
        return read_jsonl(source)
    db = sqlite3.connect((root / 'journal.sqlite3').resolve().as_uri() + '?mode=ro', uri=True)
    rows = []
    for qid, arm, status, local, result in db.execute('SELECT qid,arm,status,local_json,attempt_json FROM attempts'):
        rows.append(json.loads(result) if result else {'question_id': qid, 'arm': arm, 'terminal_status': status,
                                                     'local_only': json.loads(local), 'extracted': {}})
    db.close()
    return rows

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir', required=True)
    p.add_argument('--candidates', default=str(Path(__file__).parent / 'candidate_inputs56.jsonl'))
    p.add_argument('--output-dir', required=True)
    args = p.parse_args()
    records, summary = analyze(load_attempts(args.run_dir), read_jsonl(args.candidates))
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / 'self_review_records56.jsonl', records)
    (out / 'self_review_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
