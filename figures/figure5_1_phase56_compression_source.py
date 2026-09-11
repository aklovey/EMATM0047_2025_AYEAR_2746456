"""Descriptive lengths of 52 accepted Phase56 traces; no inference or re-sampling.

Claim: reductions range from 7.65% to 69.22% within the accepted subset.
Panel a retains every paired length; panel b shows the reduction distribution.
The four unaccepted parents and their deployment fallbacks are not plotted.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
plt.rcParams['svg.fonttype'] = 'none'
plt.rcParams['pdf.fonttype'] = 42
import numpy as np
from matplotlib.ticker import MaxNLocator

plt.rcParams.update({
    'font.size': 8.0, 'axes.labelsize': 8.0, 'axes.titlesize': 8.7,
    'xtick.labelsize': 7.4, 'ytick.labelsize': 7.4,
    'axes.linewidth': 0.65, 'axes.spines.top': False,
    'axes.spines.right': False, 'xtick.major.width': 0.65,
    'ytick.major.width': 0.65, 'text.color': '#243440',
    'axes.labelcolor': '#243440', 'xtick.color': '#40515F',
    'ytick.color': '#40515F', 'figure.facecolor': 'white',
    'savefig.facecolor': 'white', 'legend.frameon': False,
})

HERE = Path(__file__).resolve().parent
STEM = 'figure5_1_phase56_compression'
PNS_FILL = '#E4CCD8'
PNS_LINE = '#7E5F76'

def build(args):
    with args.csv.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    reference = json.loads(args.summary.read_text(encoding='utf-8'))['all_accepted']
    qids = [int(r['question_id']) for r in rows]
    full = np.array([int(r['full_tokens']) for r in rows])
    short = np.array([int(r['pns_tokens']) for r in rows])
    reduction = 1 - short / full
    supplied = np.array([float(r['compression_fraction']) for r in rows])
    assert len(rows) == len(set(qids)) == reference['n'] == 52
    assert not set(qids).intersection({19407, 24494, 29833, 30257})
    assert np.all((full > 0) & (short > 0) & (short < full))
    assert np.allclose(reduction, supplied, rtol=0, atol=1e-12)
    observed = {
        'n': len(rows), 'full_tokens': int(full.sum()), 'pns_tokens': int(short.sum()),
        'aggregate_fraction': float(1 - short.sum() / full.sum()),
        'mean_fraction': float(reduction.mean()), 'min_fraction': float(reduction.min()),
        'q25_fraction': float(np.quantile(reduction, .25, method='linear')),
        'median_fraction': float(np.median(reduction)),
        'q75_fraction': float(np.quantile(reduction, .75, method='linear')),
        'max_fraction': float(reduction.max()),
    }
    assert all(np.isclose(observed[k], reference[k], rtol=0, atol=1e-12) for k in observed)
    fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.9), gridspec_kw={'width_ratios': [1, 1.02]})
    fig.subplots_adjust(left=.105, right=.982, bottom=.20, top=.83, wspace=.43)
    a, b = axes
    maximum = float(np.ceil(full.max() / 1000))
    a.plot([0, maximum], [0, maximum], color='#9AA7B0', lw=.9,
           linestyle=(0, (3, 3)), zorder=1)
    a.scatter(full / 1000, short / 1000, s=24, facecolor=PNS_FILL,
              edgecolor=PNS_LINE, linewidth=.6, alpha=.86, zorder=3)
    a.set(xlim=(0, maximum), ylim=(0, maximum),
          xlabel='Parent reasoning (k tokens)', ylabel='Compressed reasoning (k tokens)')
    a.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
    a.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
    a.set_title('52 accepted trace pairs', loc='left', pad=9, fontweight='bold')
    a.text(.04, .93, 'Equal length', transform=a.transAxes, color='#65727D', fontsize=7.3,
           va='top')
    bins = np.arange(0, 81, 10)
    counts, edges, _ = b.hist(100 * reduction, bins=bins, facecolor=PNS_FILL,
                             edgecolor=PNS_LINE, linewidth=.65, zorder=2)
    assert int(counts.sum()) == 52
    median = 100 * observed['median_fraction']
    b.axvline(median, color=PNS_LINE, linestyle=(0, (3, 2)), linewidth=1.0, zorder=3)
    b.set(xlim=(0, 80), ylim=(0, max(counts) + 4),
          xlabel='Reasoning-token reduction (%)', ylabel='Number of traces')
    b.set_xticks([0, 20, 40, 60, 80])
    b.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
    b.set_title('Reduction varies across traces', loc='left', pad=9, fontweight='bold')
    b.text(.98, .94, f'Median {median:.2f}%', transform=b.transAxes,
           ha='right', va='top', fontsize=7.5, color=PNS_LINE)
    for label, ax in zip(('a', 'b'), axes):
        ax.text(-.17, 1.11, label, transform=ax.transAxes, va='bottom',
                ha='left', fontsize=10, fontweight='bold')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ('svg', 'pdf', 'png'):
        fig.savefig(args.output_dir / f'{args.stem}.{suffix}', dpi=600 if suffix == 'png' else 150)
    plt.close(fig)
    svg = ET.parse(args.output_dir / f'{args.stem}.svg')
    editable = len(svg.findall('.//{http://www.w3.org/2000/svg}text'))
    assert editable >= 15 and not svg.findall('.//{http://www.w3.org/2000/svg}image')
    audit = {
        'figure': '5.1', 'status': 'numeric_match_pass_visual_QA_pending',
        'claim': 'Reasoning-token reductions range from 7.65% to 69.22% among 52 accepted Phase56 traces.',
        'scope': 'Accepted subset only; excludes all four unaccepted parents and deployment fallbacks; not semantic-fidelity evidence.',
        'backend': 'Python/matplotlib', 'width_inches': 6.3, 'height_inches': 2.9,
        'source_data': args.csv.name, 'reference_summary': args.summary.name,
        'source_rows': len(rows), 'plotted_scatter_points': len(full), 'histogram_total': int(counts.sum()),
        'histogram_edges_percent': edges.tolist(), 'histogram_counts': counts.astype(int).tolist(),
        'numeric_match': observed, 'all_source_summary_fields_match': True,
        'editable_svg_text_objects': editable, 'svg_raster_images': 0,
        'statistics': 'Descriptive only; no test, confidence interval, hypothesis or resampling added.',
        'manipulations': 'None; no point omission, jitter, smoothing, outlier removal or image processing.',
        'python': sys.version, 'matplotlib': matplotlib.__version__, 'numpy': np.__version__,
    }
    (args.output_dir / f'{args.stem}_provenance.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'NUMERIC_MATCH_PASS', 'n': len(rows), 'full_tokens': int(full.sum()),
                      'pns_tokens': int(short.sum()), 'width_inches': 6.3, 'height_inches': 2.9}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=HERE / f'{STEM}_source_data.csv')
    parser.add_argument('--summary', type=Path, default=HERE / f'{STEM}_summary.json')
    parser.add_argument('--output-dir', type=Path, default=HERE)
    parser.add_argument('--stem', default=STEM)
    build(parser.parse_args())
