"""Plot separate CAUSE evaluation cohorts from read-only statistical artifacts.

The main analysis's existing interval field is intentionally NEVER read. Explicit
interval maps point to separately reviewed statistical artifacts. Run --help for
inputs. --final refuses missing cohorts or interval evidence.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
plt.rcParams['svg.fonttype'] = 'none'
plt.rcParams['pdf.fonttype'] = 42
import matplotlib.ticker as mticker
import numpy as np

plt.rcParams.update({
    'font.size': 7.7, 'axes.labelsize': 7.7, 'axes.titlesize': 8.4,
    'xtick.labelsize': 7.3, 'ytick.labelsize': 7.6,
    'axes.linewidth': 0.65, 'axes.spines.top': False,
    'axes.spines.right': False, 'axes.spines.left': False,
    'xtick.major.width': 0.6, 'ytick.major.size': 0,
    'text.color': '#243440', 'axes.labelcolor': '#243440',
    'xtick.color': '#40515F', 'ytick.color': '#243440',
    'savefig.facecolor': 'white', 'figure.facecolor': 'white',
})

MAIN_ROOT = Path(r'C:\Users\aklovey\Documents\Codex\2026-09-10\9-4-cause-1-8-8')
DEFAULT_MAIN = MAIN_ROOT / 'work/evaluation/observed_main300/analysis/paired_analysis.json'
DEFAULT_CPT = MAIN_ROOT / 'outputs/experiment/main_CPT_sensitivity.json'
ARMS = ('FULL_COT', 'HEURISTIC_SHORT', 'PNS_COT')
LABELS = {'FULL_COT': 'FULL', 'HEURISTIC_SHORT': 'HEURISTIC', 'PNS_COT': 'PNS'}
COLORS = {'FULL_COT': '#7884B4', 'HEURISTIC_SHORT': '#D8D8D8', 'PNS_COT': '#E4CCD8'}
COMPARISONS = ('PNS_COT:FULL_COT', 'PNS_COT:HEURISTIC_SHORT')


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pointer(doc, path: str):
    """Resolve an RFC 6901 JSON pointer; there is no fuzzy field matching."""
    if not path.startswith('/'):
        raise ValueError(f'JSON pointer must begin with /: {path}')
    value = doc
    for bit in path[1:].split('/'):
        key = bit.replace('~1', '/').replace('~0', '~')
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


@dataclass
class Cohort:
    identity: str
    label: str
    source: Path
    n: int
    mean_inputs: dict
    input_saving: float
    deltas: dict
    correct: dict
    gains_losses: dict
    intervals: dict
    interval_provenance: dict | None = None


def load_cohort(path: Path, identity: str, label: str) -> Cohort:
    raw = read_json(path)
    n = int(raw['n_frozen_targets'])
    if n <= 0:
        raise ValueError(f'{identity}: empty frozen target set')
    means, correct = {}, {}
    for arm in ARMS:
        item = raw['arms'][arm]
        count = int(item['correct'])
        if not 0 <= count <= n:
            raise ValueError(f'{identity}/{arm}: invalid correct count')
        if not math.isclose(float(item['strict_accuracy']), count / n, abs_tol=1e-12):
            raise ValueError(f'{identity}/{arm}: strict accuracy does not reconcile')
        tok = item['prompt_tokens']
        if int(tok['observed_count']) != n or int(tok['missing_count']) != 0:
            raise ValueError(f'{identity}/{arm}: incomplete input-token accounting')
        means[arm] = float(tok['sum']) / n
        if not math.isclose(means[arm], float(tok['mean']), abs_tol=1e-8):
            raise ValueError(f'{identity}/{arm}: mean token count does not reconcile')
        correct[arm] = count
    deltas, pairs = {}, {}
    for key in COMPARISONS:
        comp = raw['comparisons'][key]
        if int(comp['n']) != n:
            raise ValueError(f'{identity}/{key}: paired denominator differs from n')
        delta = float(comp['accuracy_delta'])
        gain, loss = int(comp['gain']), int(comp['loss'])
        other = key.split(':')[1]
        if not math.isclose(delta, (correct['PNS_COT'] - correct[other]) / n, abs_tol=1e-12):
            raise ValueError(f'{identity}/{key}: point estimate differs from correct counts')
        if not math.isclose(delta, (gain - loss) / n, abs_tol=1e-12):
            raise ValueError(f'{identity}/{key}: point estimate differs from discordances')
        deltas[key] = delta
        pairs[key] = (gain, loss)
    saving = 1 - means['PNS_COT'] / means['FULL_COT']
    recorded = raw['comparisons']['PNS_COT:FULL_COT']['prompt_token_saving_fraction']
    if not math.isclose(saving, float(recorded), abs_tol=1e-12):
        raise ValueError(f'{identity}: recorded input saving does not reconcile')
    return Cohort(identity, label, path.resolve(), n, means, saving, deltas, correct, pairs, {})


def load_intervals(cohort: Cohort, map_path: Path, require_cpt: bool):
    """Load only explicit mappings to actual reviewed source numbers.

    Mapping schema (all numeric values remain in source_json, never in the map):
    {"schema_version": 1, "cohort_id": "main300", "source_json": "...",
     "n_pointer": "/n_frozen_targets", "method_label": "...",
     "resampling_unit": "CPT group", "confidence_level": 0.95,
     "comparisons": {"PNS_COT:FULL_COT":
       {"delta_pointer": "/comparisons/PNS_COT:FULL_COT/accuracy_delta",
        "ci_pointer": "/comparisons/PNS_COT:FULL_COT/ACTUAL_VERIFIED_CI_KEY"}, ...}}

    A map is created only after inspecting the actual statistical artifact.
    Fields are never guessed or inferred from the word 'cluster' alone.
    """
    mapping = read_json(map_path)
    if mapping.get('schema_version') != 1 or mapping['cohort_id'] != cohort.identity:
        raise ValueError(f'{cohort.identity}: wrong interval-map schema or cohort')
    if float(mapping['confidence_level']) != 0.95:
        raise ValueError('This figure is contracted for 95% intervals')
    unit = str(mapping['resampling_unit']).strip()
    method = str(mapping['method_label']).strip()
    if not unit or not method:
        raise ValueError('Interval method and resampling unit must be explicit')
    if require_cpt and 'cpt' not in unit.lower():
        raise ValueError('Main interval unit must explicitly identify CPT grouping')
    source = Path(mapping['source_json'])
    if not source.is_absolute():
        source = (map_path.parent / source).resolve()
    if require_cpt and source.resolve() == cohort.source:
        raise ValueError('Main point-estimate JSON cannot supply the main CPT interval')
    stats = read_json(source)
    if int(pointer(stats, mapping['n_pointer'])) != cohort.n:
        raise ValueError(f'{cohort.identity}: interval source n differs from point source')
    for key in COMPARISONS:
        refs = mapping['comparisons'][key]
        delta = float(pointer(stats, refs['delta_pointer']))
        if not math.isclose(delta, cohort.deltas[key], abs_tol=1e-10):
            raise ValueError(f'{cohort.identity}/{key}: interval source targets a different estimate')
        ci = pointer(stats, refs['ci_pointer'])
        if not isinstance(ci, list) or len(ci) != 2:
            raise ValueError(f'{cohort.identity}/{key}: expected two CI endpoints')
        low, high = map(float, ci)
        if not all(math.isfinite(x) for x in (low, high)) or not -1 <= low <= high <= 1:
            raise ValueError(f'{cohort.identity}/{key}: invalid fractional CI endpoints')
        cohort.intervals[key] = (low, high)
    cohort.interval_provenance = {
        'map': str(map_path.resolve()), 'map_sha256': sha256(map_path),
        'source': str(source.resolve()), 'source_sha256': sha256(source),
        'method_label': method, 'resampling_unit': unit,
        'confidence_level': 0.95, 'pointers': mapping['comparisons'],
    }


def plot(cohorts: list[Cohort], output: Path, stem: str, final: bool, joint_source: Path | None = None):
    joint_records = {}
    joint_provenance = None
    if joint_source:
        joint = read_json(joint_source)
        if joint['cohorts_pooled'] is not False or int(joint['family_size']) != 6:
            raise ValueError('Joint analysis must declare an unpooled six-comparison family')
        names = {'main300': 'released_followup300', 'fresh246': 'fresh_SCM246'}
        for c in cohorts:
            for key in COMPARISONS:
                matches = [r for r in joint['comparisons'] if r['cohort'] == names[c.identity] and r['comparison'] == key]
                if len(matches) != 1:
                    raise ValueError('Missing or duplicate joint comparison')
                item = matches[0]
                if int(item['n']) != c.n or not math.isclose(float(item['accuracy_delta']), c.deltas[key], abs_tol=1e-12):
                    raise ValueError('Joint analysis point estimate or denominator mismatch')
                if not all(math.isclose(float(a), b, abs_tol=1e-12) for a, b in zip(item['paired_ci95'], c.intervals[key])):
                    raise ValueError('Joint analysis interval differs from explicit figure source')
                joint_records[(c.identity, key)] = item
        joint_provenance = {'source': str(joint_source.resolve()), 'sha256': sha256(joint_source),
                            'family_size': 6, 'adjustment': joint['adjustment'], 'cohorts_pooled': False,
                            'displayed_contrasts': list(joint_records.values()),
                            'ci_coverage': 'pointwise 95%; not simultaneous; p-values adjusted separately'}
    output.mkdir(parents=True, exist_ok=True)
    width_mm, height_mm = 160.02, 67.0 if len(cohorts) == 1 else 110.49
    fig = plt.figure(figsize=(width_mm / 25.4, height_mm / 25.4))
    grid = fig.add_gridspec(len(cohorts), 2, left=.102, right=.967, top=.82 if len(cohorts) == 1 else .88,
                            bottom=.31 if len(cohorts) == 1 else .145,
                            hspace=.98, wspace=.64, width_ratios=(1.06, 1.0))
    max_input = max(v for c in cohorts for v in c.mean_inputs.values()) / 1000
    input_max = math.ceil(max_input * 1.20)
    effects = [100 * v for c in cohorts for v in c.deltas.values()]
    effects += [100 * x for c in cohorts for ci in c.intervals.values() for x in ci]
    lo = min(-3, math.floor(min(effects) - 1.1))
    hi = max(4, math.ceil(max(effects) + 1.1))
    # Keep the zero reference visible and use one numeric scale across cohorts.
    source_rows = []
    axes = []
    for row, c in enumerate(cohorts):
        left = fig.add_subplot(grid[row, 0])
        right = fig.add_subplot(grid[row, 1])
        axes.extend([left, right])
        y = np.arange(len(ARMS))[::-1]
        for yy, arm in zip(y, ARMS):
            val = c.mean_inputs[arm] / 1000
            left.barh(yy, val, height=.52, color=COLORS[arm], edgecolor='#607081', linewidth=.55)
            left.text(val + input_max * .021, yy, f'{c.mean_inputs[arm]:,.0f}', va='center', ha='left', fontsize=7.5)
            source_rows.append({'cohort': c.identity, 'n': c.n, 'quantity': 'mean_prompt_tokens',
                                'condition': arm, 'estimate': c.mean_inputs[arm], 'ci_low': '', 'ci_high': '',
                                'unit': 'tokens per frozen target', 'source_json': str(c.source),
                                'source_pointer': f'/arms/{arm}/prompt_tokens/sum divided by n'})
        left.set(yticks=y, yticklabels=[LABELS[a] for a in ARMS], xlim=(0, input_max), ylim=(-.58, 2.55))
        left.xaxis.set_major_locator(mticker.MaxNLocator(nbins=5, integer=True))
        left.set_xlabel('Mean input tokens per target (thousands)', labelpad=5)
        left.set_title('Measured input context', loc='left', pad=7, fontweight='bold')
        pos = left.get_position()
        note_y = pos.y0 - (.22 if len(cohorts) == 1 else .112)
        fig.text(pos.x0, note_y, f'PNS vs FULL: {100*c.input_saving:+.2f}% input saving',
                 fontsize=7.6, color='#4B536B')

        ry = [1.15, .0]
        right.axvline(0, color='#9AA7B0', linestyle=(0, (3, 3)), linewidth=.75, zorder=1)
        rlabels = []
        for yy, key in zip(ry, COMPARISONS):
            value = 100 * c.deltas[key]
            if key in c.intervals:
                ci = c.intervals[key]
                # Plot endpoints directly; never substitute an iid interval.
                right.hlines(yy, 100*ci[0], 100*ci[1], color='#7E5F76', linewidth=1.45, zorder=2)
                right.vlines([100*ci[0], 100*ci[1]], yy-.075, yy+.075, color='#7E5F76', linewidth=.85)
            right.scatter([value], [yy], s=29, marker='o', color='#E4CCD8', edgecolor='#6C5369', linewidth=.8, zorder=3)
            other = LABELS[key.split(':')[1]]
            rlabels.append(f'PNS − {other}\n{value:+.2f} pp')
            ci = c.intervals.get(key)
            source_rows.append({'cohort': c.identity, 'n': c.n, 'quantity': 'paired_accuracy_delta',
                                'condition': key, 'estimate': c.deltas[key],
                                'ci_low': ci[0] if ci else '', 'ci_high': ci[1] if ci else '',
                                'unit': 'fraction correct', 'source_json': str(c.source),
                                'source_pointer': f'/comparisons/{key}/accuracy_delta'})
        right.set(xlim=(lo, hi), ylim=(-.47, 1.65), yticks=ry, yticklabels=rlabels)
        right.xaxis.set_major_locator(mticker.MaxNLocator(nbins=5, integer=True))
        right.set_xlabel('Accuracy difference (percentage points)', labelpad=5)
        right.set_title('Paired strict accuracy', loc='left', pad=7, fontweight='bold')
        interval_note = '95% intervals not yet supplied' if not c.intervals else c.interval_provenance['method_label']
        fig.text(right.get_position().x0, note_y, interval_note, fontsize=7.0, color='#606C75')
        pos = left.get_position()
        fig.text(.05, pos.y1 + (.10 if len(cohorts) == 1 else .063),
                 f'{chr(97+row)}  {c.label} (n = {c.n})', fontsize=9.3, fontweight='bold', ha='left')

    if not final:
        notes = ['Internal preview']
        if not cohorts[0].intervals:
            notes.append('main CPT intervals pending')
        if len(cohorts) == 1:
            notes.append('fresh cohort not plotted')
        fig.text(.05, .027, ' · '.join(notes), fontsize=7.2, color='#7A5B30')
    # Record all exact numbers used, including deliberately empty interval cells.
    csv_path = output / f'{stem}_source_data.csv'
    for row in source_rows:
        joint_item = joint_records.get((row['cohort'], row['condition']))
        row['holm_across_six_p'] = joint_item['holm_across_six_p'] if joint_item else ''
    with csv_path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(source_rows[0]))
        writer.writeheader()
        writer.writerows(source_rows)
    paths = {}
    for fmt in ('svg', 'pdf', 'png'):
        path = output / f'{stem}.{fmt}'
        fig.savefig(path, dpi=600 if fmt == 'png' else 150)
        paths[fmt] = str(path.resolve())
    plt.close(fig)
    svg = ET.parse(output / f'{stem}.svg')
    text_count = len(svg.findall('.//{http://www.w3.org/2000/svg}text'))
    assert text_count > 10
    assert not svg.findall('.//{http://www.w3.org/2000/svg}image')
    provenance = {
        'status': 'final' if final else 'internal_preview', 'pooled': False,
        'width_mm': width_mm, 'height_mm': height_mm,
        'cohorts': [{'id': c.identity, 'n': c.n, 'source': str(c.source),
                     'source_sha256': sha256(c.source), 'interval_provenance': c.interval_provenance,
                     'input_saving_fraction': c.input_saving, 'gains_losses': c.gains_losses}
                    for c in cohorts],
        'main_iid_interval_used': False, 'svg_text_objects': text_count,
        'joint_inference_provenance': joint_provenance,
        'source_data': str(csv_path.resolve()), 'exports': paths,
        'python': sys.executable, 'python_version': sys.version,
        'matplotlib_version': matplotlib.__version__, 'numpy_version': np.__version__,
        'visual_qa': 'Pending inspection of matplotlib PNG at final dimensions',
    }
    (output / f'{stem}_provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    copy_path = output / f'{stem}_source.py'
    if copy_path.resolve() != Path(__file__).resolve():
        shutil.copyfile(__file__, copy_path)
    print(json.dumps(provenance, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main', type=Path, default=DEFAULT_MAIN)
    parser.add_argument('--fresh', type=Path)
    parser.add_argument('--main-interval-map', type=Path)
    parser.add_argument('--fresh-interval-map', type=Path)
    parser.add_argument('--joint', type=Path, help='Verified unpooled six-comparison Holm result; retained in source data/provenance')
    parser.add_argument('--main-label', default='Main cohort')
    parser.add_argument('--fresh-label', default='Fresh cohort')
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).parent / 'evaluation_figure_preview')
    parser.add_argument('--stem', default='figure2_main300_preview')
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    cohorts = [load_cohort(args.main, 'main300', args.main_label)]
    if args.main_interval_map:
        load_intervals(cohorts[0], args.main_interval_map, require_cpt=True)
    if args.fresh:
        cohorts.append(load_cohort(args.fresh, 'fresh246', args.fresh_label))
        if args.fresh_interval_map:
            load_intervals(cohorts[1], args.fresh_interval_map, require_cpt=False)
    if args.final:
        if len(cohorts) != 2 or any(len(c.intervals) != len(COMPARISONS) for c in cohorts):
            parser.error('Final figure requires main + fresh results and both reviewed interval maps; no iid fallback.')
        if args.stem == 'figure2_main300_preview':
            parser.error('Choose a final figure basename explicitly, e.g. figure2_evaluation_efficiency')
    elif not args.main_interval_map:
        state = 'present but unmapped' if DEFAULT_CPT.exists() else 'not yet present'
        print(f'Main CPT source {state}; plotting main point estimates only.', file=sys.stderr)
    plot(cohorts, args.output_dir.resolve(), args.stem, args.final, args.joint)


if __name__ == '__main__':
    main()
