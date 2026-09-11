"""No-model extractive comparator, matched to each PNS demo's reasoning token budget.

Canonical input: question_id, query_type, gold_answer, full_cot, pns_cot.
PNS content is read only to count tokens. No target material is accepted.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys

class Counter:
    def __init__(self, path, pydeps=None):
        if pydeps:
            sys.path.insert(0, str(pydeps))
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_file(str(path))
    def ids(self, text):
        return self.tokenizer.encode(text, add_special_tokens=False).ids
    def count(self, text):
        return len(self.ids(text))
    def decode(self, ids):
        return self.tokenizer.decode(ids, skip_special_tokens=False)

def sentence_units(text, tok):
    chunks = []
    for sentence in re.split(r'\n+|(?<=[.!?])\s+(?=[A-Z])', text.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        ids = tok.ids(sentence)
        # Very long prose is divided at tokenizer boundaries into ordinary extractive chunks.
        if len(ids) > 128:
            chunks.extend(tok.decode(ids[i:i + 64]).strip() for i in range(0, len(ids), 64))
        else:
            chunks.append(sentence)
    return [s for s in chunks if s]

def score(text, index, total):
    # Fixed generic salience rules, not a causal verifier, oracle, or learned compressor.
    numeric = bool(re.search(r'\d', text))
    equation = bool(re.search(r'=|\bP\(|\bE\[|->|\\(?:sum|frac)', text))
    conclusion = bool(re.search(r'\b(therefore|thus|hence|conclude|answer|result)\b', text, re.I))
    relation = bool(re.search(r'\b(causal|counterfactual|intervention|effect|probability)\b', text, re.I))
    filler = bool(re.search(r"\b(wait|double.check|let me|let's|alternatively|user input)\b", text, re.I))
    return 2.5 * equation + 1.5 * numeric + conclusion + 0.5 * relation + 0.25 * (index in {0, total - 1}) - 1.5 * filler

def compress(full_cot, budget, tok):
    if budget <= 0:
        raise ValueError('PNS token budget must be positive')
    if tok.count(full_cot) <= budget:
        return full_cot, {'selected_units': None, 'partial_unit': False, 'mode': 'full_fits'}
    units = sentence_units(full_cot, tok)
    ranked = sorted(range(len(units)), key=lambda i: (-score(units[i], i, len(units)), i))
    selected = {}
    def render(parts):
        return '\n'.join(parts[i] for i in sorted(parts))
    for i in ranked:
        candidate = {**selected, i: units[i]}
        if tok.count(render(candidate)) <= budget:
            selected[i] = units[i]
    partial = False
    # Fill the remaining budget with at most one excerpt. No padding or invented text.
    for i in ranked:
        if i in selected:
            continue
        ids = tok.ids(units[i])
        remaining = budget - tok.count(render(selected))
        if remaining < 4:
            break
        for take in range(min(len(ids) - 1, remaining + 4), 0, -1):
            excerpt = tok.decode(ids[:take]).rstrip()
            if not excerpt:
                continue
            candidate = {**selected, i: excerpt}
            if tok.count(render(candidate)) <= budget:
                selected = candidate
                partial = True
                break
        if partial:
            break
    result = render(selected)
    if not result:
        result = tok.decode(tok.ids(full_cot)[:budget])
        partial = True
    return result, {'selected_units': sorted(selected), 'total_units': len(units),
                    'partial_unit': partial, 'mode': 'salience_extract_then_single_excerpt'}

def main(args):
    tok = Counter(args.tokenizer, args.pydeps)
    rows = [json.loads(x) for x in Path(args.input).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
    output = []
    for row in rows:
        budget = tok.count(row['pns_cot'])
        short, audit = compress(row['full_cot'], budget, tok)
        actual = tok.count(short)
        output.append({**row, 'heuristic_cot': short, 'length_audit': {
            'full_tokens': tok.count(row['full_cot']), 'pns_tokens': budget,
            'heuristic_tokens': actual, 'absolute_gap': actual - budget,
            'relative_gap': (actual - budget) / budget,
            'within_tolerance': abs(actual - budget) <= max(16, 0.05 * budget), **audit}})
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in output), encoding='utf-8')
    print(json.dumps({'n': len(output), 'model_calls': 0, 'outside_tolerance':
                      [r['question_id'] for r in output if not r['length_audit']['within_tolerance']],
                      'full_tokens': sum(r['length_audit']['full_tokens'] for r in output),
                      'pns_tokens': sum(r['length_audit']['pns_tokens'] for r in output),
                      'heuristic_tokens': sum(r['length_audit']['heuristic_tokens'] for r in output)}, indent=2))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--tokenizer', required=True)
    p.add_argument('--pydeps')
    main(p.parse_args())
