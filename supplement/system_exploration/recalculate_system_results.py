"""Recalculate historical system results from the released records, without model calls."""
from __future__ import annotations
import argparse
import collections
import csv
import importlib.util
import json
import platform
from pathlib import Path
import numpy
import scipy

ROOT=Path(__file__).resolve().parent


def load_module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'source_snapshots'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def read(path):return json.loads(path.read_text('utf8'))


def boolean(value):
    if value not in ('True','False','true','false'):raise ValueError(f'Invalid Boolean {value!r}')
    return value.lower()=='true'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    aggregate=load_module('resource_aggregation');stats=load_module('paired_statistics')
    base=ROOT/'shared_first_pass'
    matrix=rows(base/'paired_sample_matrix.csv');original_comparisons=rows(base/'primary_paired_comparisons.csv')
    original_resources=read(base/'resource_metrics.json')['packs']
    result={'verification_date':'2026-09-14','kind':'offline reanalysis of preserved records; no model execution',
            'runtime':{'python':platform.python_version(),'numpy':numpy.__version__,'scipy':scipy.__version__},'packs':{}}
    for pack in ['clean_holdout_natural','structural_stress_holdout']:
        paired=[r for r in matrix if r['pack']==pack]
        ids=[r['question_id'] for r in paired]
        assert len(ids)==len(set(ids))
        assert all(r['candidate_answer']==r['c0_answer'] and not boolean(r['candidate_changed_from_c0']) for r in paired)
        path=base/pack
        legacy_manifest=read(path/'legacy_run_manifest.release.json')
        shared_manifest=read(path/'shared_first_pass_manifest.release.json')
        assert ids==legacy_manifest['ordered_question_ids']==shared_manifest['ordered_question_ids']
        assert legacy_manifest['input_pack_sha256']==shared_manifest['input_pack_sha256']
        legacy_table=rows(path/'legacy_accounting.csv')
        assert [r['question_id'] for r in legacy_table]==ids
        legacy_records=[]
        for r in legacy_table:
            assert int(r['model_calls'])==int(r['turn_count'])+int(boolean(r['repair_attempted']))
            legacy_records.append({'turn_count':int(r['turn_count']),'repair_attempted':boolean(r['repair_attempted']),
                                   'tool_call_count':int(r['tool_call_count']),
                                   'usage':{k:int(r[k]) for k in ['prompt_tokens','completion_tokens','total_tokens','reasoning_tokens']}})
        legacy=aggregate.legacy_resource_metrics(legacy_records)
        shard_table=rows(path/'shard_accounting.csv')
        shard_map={r['shard_id']:{'model_calls':int(r['model_calls']),'model_retries':int(r['model_retries']),
                   'usage':{k:int(r[k]) for k in ['prompt_tokens','completion_tokens','total_tokens']}} for r in shard_table}
        assert len(shard_map)==len(shard_table)
        shared=aggregate._aggregate_generic_audits(shard_map)
        for actual,manifest,keys in [(legacy,legacy_manifest,['model_calls','tool_calls','schema_repairs']),(shared,shared_manifest,['model_calls','model_retries','unique_shards'])]:
            for k in keys:assert actual[k]==manifest['resource_metrics'][k]
            for k in actual['usage']:assert actual['usage'][k]==manifest['resource_metrics']['usage'][k]
            assert actual['usage']['prompt_tokens']+actual['usage']['completion_tokens']==actual['usage']['total_tokens']
        for who,actual in [('candidate_deployment',shared),('legacy',legacy)]:
            assert actual['model_calls']==original_resources[pack][who]['model_calls']
            assert actual['usage']['total_tokens']==original_resources[pack][who]['total_tokens']
        left=[{'question_id':r['question_id'],'correct':boolean(r['legacy_correct'])} for r in paired]
        right=[{'question_id':r['question_id'],'correct':boolean(r['candidate_correct'])} for r in paired]
        comparison=stats.paired_binary_comparison(left_rows=left,right_rows=right,left_name='legacy',right_name='candidate',bootstrap_resamples=10000,seed=20260718)
        expected=next(r for r in original_comparisons if r['pack']==pack and r['left_arm']=='L_legacy_full_tools_equal_concurrency')
        for k in ['paired_n','left_correct','right_correct','both_correct','both_wrong','baseline_only','candidate_only','delta_pp','mcnemar_exact_two_sided_p','paired_bootstrap_ci_low_pp','paired_bootstrap_ci_high_pp']:
            assert abs(float(comparison[k])-float(expected[k]))<1e-10,(pack,k)
        candidate=read(path/'candidate_run_manifest.json')
        assert candidate['model_calls_incremental']==0 and candidate['incremental_tokens']==0 and not candidate['answer_intervention_enabled']
        audit=read(path/'equal_execution_contract_audit.json');assert audit['passed'] and all(audit['checks'].values())
        ratios={key:1-shared['usage'][key]/legacy['usage'][key] for key in ['prompt_tokens','completion_tokens','total_tokens']}
        ratios['model_calls']=1-shared['model_calls']/legacy['model_calls']
        result['packs'][pack]={'same_unique_ordered_questions':len(ids),'empty_legacy_answers':sum(not r['legacy_answer'] for r in paired),
                              'paired_comparison':comparison,'legacy_resources':legacy,'shared_resources':shared,
                              'legacy_turn_distribution':dict(sorted(collections.Counter(int(r['turn_count']) for r in legacy_table).items())),
                              'resource_reduction_fractions':ratios,'matches_original_numerical_reports':True,
                              'unchanged_c0_confirmed':True,'incremental_revision_calls':0}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({pack:{'n':p['same_unique_ordered_questions'],'legacy_correct':p['paired_comparison']['left_correct'],'candidate_correct':p['paired_comparison']['right_correct'],'legacy_calls':p['legacy_resources']['model_calls'],'candidate_calls':p['shared_resources']['model_calls'],'source_reports_matched':True} for pack,p in result['packs'].items()},indent=2))


if __name__=='__main__':main()
