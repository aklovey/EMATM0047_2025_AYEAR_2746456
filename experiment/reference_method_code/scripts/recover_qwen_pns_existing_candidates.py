from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_qwen_pns_adaptive import (  # noqa: E402
    load_future_judge_resume_contract,
)
from src.pns_future_judge import (  # noqa: E402
    build_future_semantic_judge,
    verify_future_judge_canary_artifact,
)
from src.pns_future_judge_ledger import open_future_judge_ledger  # noqa: E402
from src.qwen_pns_candidate_materialization_recovery import (  # noqa: E402
    ExistingCandidateRecoveryBatchConfig,
    discover_existing_candidates,
    freeze_existing_candidate_batch_manifest,
    freeze_existing_candidate_manifest,
    initialize_existing_candidate_recovery_workspace,
    load_existing_candidate_batch_manifest,
    load_existing_candidate_recovery_config,
    recover_existing_candidate_materialization_batch,
    recover_existing_candidate_materialization,
    validate_existing_candidate_recovery_workspace,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Review only frozen existing Qwen PNS candidates; this command has "
            "no Qwen runtime, tokenizer, base URL, or rollout option."
        )
    )
    parser.add_argument("--config", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_existing_candidate_recovery_config(
        args.config,
        project_root=ROOT,
    )
    if isinstance(config, ExistingCandidateRecoveryBatchConfig):
        return _run_batch(config, prepare=args.prepare)
    return _run_single(config, prepare=args.prepare)


def _open_frozen_future_ledger(config):
    future = load_future_judge_resume_contract(config.future_judge_resume_config)
    if isinstance(config, ExistingCandidateRecoveryBatchConfig):
        if Path(future["future_ledger"]).resolve() != (
            config.source_future_judge_ledger
        ):
            raise RuntimeError("batch source future Judge ledger binding differs")
        if Path(future["qwen_recovery_manifest"]).resolve() != (
            config.qwen_recovery_manifest
        ):
            raise RuntimeError("batch future Judge config Qwen manifest differs")
        if Path(future["qwen_recovery_sidecar"]).resolve() != (
            config.qwen_recovery_sidecar
        ):
            raise RuntimeError("batch future Judge config Qwen sidecar differs")
    verify_future_judge_canary_artifact(future["future_canary"])
    writable_future_ledger = (
        config.future_judge_ledger
        if isinstance(config, ExistingCandidateRecoveryBatchConfig)
        else future["future_ledger"]
    )
    ledger = open_future_judge_ledger(
        future["historical_source_ledger"],
        writable_future_ledger,
        recovery_manifest=future["recovery_manifest"],
        recovery_sidecar=future["recovery_sidecar"],
        expected_recovery_count=113,
    )
    return future, ledger


def _run_single(config, *, prepare: bool) -> int:
    _future, ledger = _open_frozen_future_ledger(config)
    try:
        if prepare:
            _item, parent_tokens, candidates = discover_existing_candidates(
                config,
                judge_records=ledger.completed_records(),
            )
            manifest = freeze_existing_candidate_manifest(
                config,
                parent_tokens=parent_tokens,
                candidates=candidates,
            )
            print(
                json.dumps(
                    {
                        "status": "FROZEN_NO_PROVIDER_CALLS",
                        "target_qid": config.target_qid,
                        "candidate_count": manifest["candidate_count"],
                        "new_qwen_rollouts": 0,
                        "qwen_tokenizer_calls": 0,
                        "qwen_base_url": None,
                        "candidate_manifest": str(config.candidate_manifest),
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        judge = build_future_semantic_judge()
        artifact = recover_existing_candidate_materialization(
            config,
            semantic_judge=judge,
            judge_ledger=ledger,
        )
        exact_output_materialized = config.output_artifact.is_file()
        print(
            json.dumps(
                {
                    "status": "RECOVERED_ACCEPTED_EXISTING_CANDIDATE",
                    "target_qid": artifact["question_id"],
                    "selected_request_key": artifact["selected_request_key"],
                    "original_qwen_tokens": artifact["original_qwen_tokens"],
                    "final_qwen_tokens": artifact["final_qwen_tokens"],
                    "actual_judge_model": artifact["judge_acceptance"].get(
                        "actual_judge_model"
                    ),
                    "new_qwen_rollouts": 0,
                    "exact_output_materialized": exact_output_materialized,
                    "output_artifact": (
                        str(config.output_artifact)
                        if exact_output_materialized
                        else None
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        ledger.close()


def _run_batch(
    config: ExistingCandidateRecoveryBatchConfig,
    *,
    prepare: bool,
) -> int:
    if prepare:
        workspace = initialize_existing_candidate_recovery_workspace(config)
        _future, ledger = _open_frozen_future_ledger(config)
        try:
            manifest = freeze_existing_candidate_batch_manifest(
                config,
                judge_records=ledger.completed_records(),
            )
        finally:
            ledger.close()
        print(
            json.dumps(
                {
                    "status": "FROZEN_18_NO_PROVIDER_CALLS",
                    "target_qids": list(config.target_qids),
                    "max7_qids_excluded": list(config.max7_qids),
                    "target_count": manifest["target_count"],
                    "candidate_counts": {
                        str(row["qid"]): row["candidate_count"]
                        for row in manifest["items"]
                    },
                    "workspace_contract": str(
                        config.workspace_contract_artifact
                    ),
                    "batch_manifest": str(config.batch_manifest),
                    "source_journal_mutated": workspace[
                        "source_journal_mutated"
                    ],
                    "copied_via_sqlite_backup": workspace[
                        "copied_via_sqlite_backup"
                    ],
                    "new_qwen_rollouts": 0,
                    "qwen_tokenizer_calls": 0,
                    "qwen_base_url": None,
                },
                ensure_ascii=False,
            )
        )
        return 0

    validate_existing_candidate_recovery_workspace(config)
    load_existing_candidate_batch_manifest(config)
    _future, ledger = _open_frozen_future_ledger(config)
    try:
        judge = build_future_semantic_judge()
        report = recover_existing_candidate_materialization_batch(
            config,
            semantic_judge=judge,
            judge_ledger=ledger,
        )
    finally:
        ledger.close()
    complete = report["status"] == "accepted_18_of_18_max7_gate_ready"
    print(
        json.dumps(
            {
                "status": report["status"],
                "accepted_count": report["accepted_count"],
                "failed_count": report["failed_count"],
                "failed_qids": report["failed_qids"],
                "actual_judge_models": report["actual_judge_models"],
                "materialization_provider_calls_confirmed": report[
                    "materialization_provider_calls_confirmed"
                ],
                "new_qwen_rollouts": 0,
                "journal_state": report["journal_state"],
                "terminal_report": str(config.terminal_report),
                "exact_output_materialized": report[
                    "exact_output_materialized"
                ],
                "output_artifact": report["output_artifact"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
