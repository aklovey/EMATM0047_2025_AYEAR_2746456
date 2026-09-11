"""Linux/Windows stdlib paired evaluation runner. One POST per (qid, arm).

Request JSONL rows: {local_only:{target_question_id,arm,...},request_body:{...}}.
SQLite reservation precedes network dispatch. A reserved item has unknown delivery
state after interruption and is never resent. Recovery uses a new explicit run.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

def now():
    return datetime.now(timezone.utc).isoformat()

def read_manifest(path):
    rows = [json.loads(s) for s in Path(path).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
    seen, by_qid = set(), {}
    for row in rows:
        local = row['local_only']
        key = (int(local['target_question_id']), str(local['arm']))
        if key in seen:
            raise ValueError(f'duplicate manifest key {key}')
        seen.add(key)
        body = row.get('request_body')
        if body:
            state = (body['seed'], body['max_tokens'], body['model'])
            if key[0] in by_qid and by_qid[key[0]] != state:
                raise ValueError(f'Within-target seed/output budget/model differs: {key[0]}')
            by_qid[key[0]] = state
            if any(k in body for k in ('gold_answer', 'oracle', 'local_only', 'target_answer')):
                raise ValueError('Scoring metadata in request body')
    return rows

class Journal:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / 'raw_responses').mkdir(exist_ok=True)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(self.directory / 'journal.sqlite3', check_same_thread=False, timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS attempts(qid INTEGER NOT NULL, arm TEXT NOT NULL, status TEXT NOT NULL, reserved_at TEXT, finished_at TEXT, endpoint TEXT, local_json TEXT, request_json TEXT, attempt_json TEXT, PRIMARY KEY(qid,arm))')
        self.db.commit()
    def reserve(self, row, endpoint):
        local = row['local_only']; body = row.get('request_body')
        with self.lock:
            cur = self.db.execute('INSERT OR IGNORE INTO attempts(qid,arm,status,reserved_at,endpoint,local_json,request_json) VALUES(?,?,?,?,?,?,?)',
                                  (int(local['target_question_id']), local['arm'], 'reserved_unknown', now(), endpoint,
                                   json.dumps(local, ensure_ascii=False), json.dumps(body, ensure_ascii=False)))
            self.db.commit()
            if cur.rowcount == 0:
                previous = self.db.execute('SELECT request_json FROM attempts WHERE qid=? AND arm=?', (int(local['target_question_id']), local['arm'])).fetchone()
                if json.loads(previous[0]) != body:
                    raise ValueError(f'Existing reservation has a different request: q{local["target_question_id"]}/{local["arm"]}')
            return cur.rowcount == 1
    def terminal(self, qid, arm, result):
        with self.lock:
            self.db.execute('UPDATE attempts SET status=?,finished_at=?,attempt_json=? WHERE qid=? AND arm=? AND status=?',
                            (result['terminal_status'], now(), json.dumps(result, ensure_ascii=False), qid, arm, 'reserved_unknown'))
            self.db.commit()
    def export(self, rows):
        with self.lock:
            data = self.db.execute('SELECT qid,arm,status,reserved_at,endpoint,local_json,attempt_json FROM attempts').fetchall()
        by_key = {}
        for qid, arm, status, reserved_at, endpoint, local_text, result_text in data:
            result = json.loads(result_text) if result_text else {'question_id': qid, 'arm': arm, 'terminal_status': status,
                      'reserved_at': reserved_at, 'endpoint': endpoint, 'extracted': {}, 'local_only': json.loads(local_text)}
            by_key[(qid, arm)] = result
        ordered = []
        for row in rows:
            loc = row['local_only']; key = (int(loc['target_question_id']), loc['arm'])
            ordered.append(by_key.get(key, {'question_id': key[0], 'arm': key[1], 'terminal_status': 'not_dispatched', 'extracted': {}}))
        arms = sorted({r['arm'] for r in ordered})
        for arm in arms:
            atomic_text(self.directory / f'{arm}.attempts.jsonl', ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in ordered if r['arm'] == arm))
        summary = {'updated_at': now(), 'expected_rows': len(rows), 'reserved_rows': len(by_key),
                   'status_counts': {s: sum(r['terminal_status'] == s for r in ordered) for s in sorted({r['terminal_status'] for r in ordered})},
                   'no_automatic_resend': True}
        atomic_text(self.directory / 'run_state.json', json.dumps(summary, indent=2) + '\n')
        return summary

def atomic_text(path, text):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(path)

def extracted(raw):
    choices = raw.get('choices', []) if isinstance(raw, dict) else []
    if len(choices) != 1 or not isinstance(choices[0], dict):
        raise ValueError('Response must have one choice')
    choice = choices[0]
    message = choice.get('message')
    if not isinstance(message, dict):
        raise ValueError('Choice has no message')
    return {'content': message.get('content'), 'finish_reason': choice.get('finish_reason'),
            'usage': raw.get('usage'), 'response_model': raw.get('model'), 'response_id': raw.get('id')}

def send_one(row, endpoint, journal, timeout):
    local = row['local_only']; qid = int(local['target_question_id']); arm = local['arm']
    if not journal.reserve(row, endpoint):
        return {'question_id': qid, 'arm': arm, 'terminal_status': 'skipped_already_reserved'}
    result = {'question_id': qid, 'arm': arm, 'endpoint': endpoint, 'started_at': now(),
              'local_only': local, 'terminal_status': 'reserved_unknown', 'http_status': None,
              'latency_seconds': None, 'extracted': {}}
    body = row.get('request_body')
    if not body:
        result['terminal_status'] = 'context_budget_error'
        result['error'] = local.get('preflight_error', 'No valid request body')
        journal.terminal(qid, arm, result)
        return result
    result['seed'] = body['seed']; result['max_tokens'] = body['max_tokens']
    request = urllib.request.Request(endpoint, data=json.dumps(body, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result['http_status'] = response.status
            payload = response.read().decode('utf-8')
        raw_path = journal.directory / 'raw_responses' / f'q{qid}_{arm}.json'
        atomic_text(raw_path, payload)
        result['raw_response_path'] = str(raw_path)
        try:
            raw = json.loads(payload)
            result['extracted'] = extracted(raw)
            result['terminal_status'] = 'completed'
        except (ValueError, TypeError) as exc:
            result['terminal_status'] = 'invalid_response'
            result['error'] = str(exc)
    except urllib.error.HTTPError as exc:
        result['terminal_status'] = 'http_error'
        result['http_status'] = exc.code
        result['error'] = exc.read(4096).decode('utf-8', errors='replace')
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        result['terminal_status'] = 'network_error'
        result['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        result['latency_seconds'] = time.monotonic() - started
        result['finished_at'] = now()
        journal.terminal(qid, arm, result)
    return result

def run(args):
    rows = read_manifest(args.manifest)
    for endpoint in args.endpoints:
        p = urllib.parse.urlparse(endpoint)
        if p.scheme != 'http' or p.hostname not in {'127.0.0.1', 'localhost', '::1'} or p.path != '/v1/chat/completions':
            raise ValueError('Run on model host using a loopback /v1/chat/completions endpoint')
    journal = Journal(args.run_dir)
    started_at = now(); started = time.monotonic()
    atomic_text(Path(args.run_dir) / 'execution_config.json', json.dumps({
        'manifest': str(args.manifest), 'endpoints': args.endpoints, 'concurrency_per_endpoint': args.concurrency_per_endpoint,
        'timeout_seconds': args.timeout_seconds, 'started_at': started_at, 'expected_rows': len(rows),
        'routing': 'target_question_id modulo number of endpoints; same target all arms same service'}, indent=2))
    journal.export(rows)
    if args.command == 'export':
        print(json.dumps(journal.export(rows), indent=2)); return
    pools = [ThreadPoolExecutor(max_workers=args.concurrency_per_endpoint) for endpoint in args.endpoints]
    futures = []
    try:
        for row in rows:
            index = int(row['local_only']['target_question_id']) % len(args.endpoints)
            futures.append(pools[index].submit(send_one, row, args.endpoints[index], journal, args.timeout_seconds))
        for index, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if index % args.progress_every == 0 or index == len(futures):
                state = journal.export(rows)
                print(json.dumps({'processed': index, 'expected': len(rows), 'last_status': result['terminal_status'],
                                  'elapsed_seconds': round(time.monotonic() - started, 1), **state}), flush=True)
    finally:
        for pool in pools:
            pool.shutdown(wait=True)
        state = journal.export(rows)
        atomic_text(Path(args.run_dir) / f'invocation_{started_at.replace(":", "-")}.json', json.dumps({
            'started_at': started_at, 'finished_at': now(), 'invocation_wall_seconds': time.monotonic() - started, **state}, indent=2))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['run', 'export'])
    p.add_argument('--manifest', required=True)
    p.add_argument('--run-dir', required=True)
    p.add_argument('--endpoints', nargs='+', default=['http://127.0.0.1:8000/v1/chat/completions', 'http://127.0.0.1:8001/v1/chat/completions'])
    p.add_argument('--concurrency-per-endpoint', type=int, default=8)
    p.add_argument('--timeout-seconds', type=float, default=1800)
    p.add_argument('--progress-every', type=int, default=20)
    run(p.parse_args())
