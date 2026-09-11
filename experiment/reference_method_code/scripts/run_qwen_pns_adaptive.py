from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.qwen_pns_adaptive import AdaptiveRolloutConfig  # noqa: E402
from src.experiments.cladder_pns_mvp.config import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    load_config as load_cladder_pns_config,
    resolve_judge_provider_profile,
)
from src.experiments.cladder_pns_mvp.storage import load_secret  # noqa: E402
from src.pns_judge_ledger import SemanticJudgeLedger  # noqa: E402
from src.pns_judge_overlay import JudgeLedgerOverlay  # noqa: E402
from src.pns_future_judge import (  # noqa: E402
    FUTURE_JUDGE_PROTOCOL_REVISION,
    build_future_semantic_judge,
    future_judge_audit_fields,
    run_future_judge_live_canary,
    validate_future_judge_preflight,
    verify_future_judge_canary_artifact,
)
from src.pns_future_judge_ledger import open_future_judge_ledger  # noqa: E402
from src.qwen_pns_request_recovery import (  # noqa: E402
    QwenRequestRecovery,
    RecoveryDispatchResult,
    load_g1_manifest,
)
from src.qwen_pns_max7_recovery import (  # noqa: E402
    build_max7_recovery_report_payload,
    load_max7_recovery_config,
    read_request_rows_read_only,
    verify_recovery_workspace,
)
from src.qwen_pns_test100_protocol import (  # noqa: E402
    build_phase56_completion_manifest_payload,
)
from src.qwen_pns_judge_gate import (  # noqa: E402
    build_deepseek_semantic_judge,
    build_execution_binding,
    build_judge_contract,
    load_frozen_phase56_contract,
    rebind_live_judge_canary,
    run_offline_judge_preflight,
    run_until_first_future_accepted_gate,
    run_with_first_accepted_gate,
    verify_live_judge_canary,
    write_offline_judge_preflight,
)
from src.qwen_pns_batch56_adapter import (  # noqa: E402
    AdaptiveEndpointConcurrencyConfig,
    Batch56AdaptiveAdapter,
    DatasetPnsExecutionConfig,
    acquire_adaptive_run_lock,
    install_qid_affinity_request_pool,
    load_batch56_runtime,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the frozen adaptive 3-to-5-trial PNS policy through the Qwen batch56 runtime."
    )
    parser.add_argument("--runtime-runner", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument(
        "--phase-config",
        type=Path,
        required=True,
        help="single frozen phase56 protocol/config source",
    )
    parser.add_argument(
        "--base-url",
        dest="base_urls",
        action="append",
        help=(
            "vLLM base URL; repeat to enable qid-affinity generation routing "
            "across replicas (default: http://127.0.0.1:8000)"
        ),
    )
    parser.add_argument(
        "--item-workers",
        type=int,
        default=0,
        help="outer item scheduler only; 0 expands all items in the frozen batch",
    )
    parser.add_argument(
        "--step-workers-per-item",
        type=int,
        default=0,
        help="0 expands all eligible frozen Qwen segments; endpoint gates control generation",
    )
    parser.add_argument(
        "--adaptive-endpoint-concurrency",
        action="store_true",
        help=(
            "adapt each vLLM endpoint independently from its own metrics; "
            "no aggregate generation limit is created"
        ),
    )
    parser.add_argument("--endpoint-initial-inflight", type=int, default=48)
    parser.add_argument("--endpoint-min-inflight", type=int, default=16)
    parser.add_argument("--endpoint-max-inflight", type=int, default=64)
    parser.add_argument("--endpoint-increase-step", type=int, default=4)
    parser.add_argument("--endpoint-samples-per-window", type=int, default=6)
    parser.add_argument("--endpoint-metrics-interval-seconds", type=float, default=10.0)
    parser.add_argument("--initial-valid-rounds", type=int, default=3)
    parser.add_argument("--max-valid-rounds", type=int, default=5)
    parser.add_argument("--max-raw-attempts-per-lineage", type=int, default=5)
    parser.add_argument(
        "--judge-config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="CLADDER config that resolves the frozen DeepSeek Judge profile",
    )
    parser.add_argument(
        "--judge-canary-artifact",
        type=Path,
        help="live DeepSeek Judge canary evidence bound to this exact run",
    )
    parser.add_argument(
        "--offline-preflight-artifact",
        type=Path,
        help="safe final-payload preflight evidence (default: inside run-dir)",
    )
    parser.add_argument(
        "--judge-ledger",
        type=Path,
        help="formal reserve-before-call Judge ledger (default: inside run-dir)",
    )
    parser.add_argument(
        "--future-judge-resume-config",
        type=Path,
        help=(
            "frozen current-resume contract that routes only new Judge evidence "
            "to local CLI-Proxy GPT-5.5"
        ),
    )
    parser.add_argument(
        "--recovery-amendment-config",
        type=Path,
        help=(
            "isolated 18+3 recovery workspace contract; keeps the copied base "
            "journal at max5 and extends only q19407/q24494/q30257 to r6-r7"
        ),
    )
    parser.add_argument(
        "--future-judge-ledger",
        type=Path,
        help="isolated writable ledger for future CLI-Proxy Judge evidence",
    )
    parser.add_argument(
        "--future-judge-canary-artifact",
        type=Path,
        help="one-call live CLI-Proxy GPT-5.5 canary artifact",
    )
    parser.add_argument(
        "--future-judge-offline-preflight-artifact",
        type=Path,
        help="prompt-free audit of the final future Judge Responses payload",
    )
    parser.add_argument(
        "--judge-recovery-manifest",
        type=Path,
        help="exact user-authorized 113-record GPT-5.5 recovery manifest",
    )
    parser.add_argument(
        "--judge-recovery-sidecar",
        type=Path,
        help="completed GPT-5.5 recovery ledger paired with the manifest",
    )
    parser.add_argument(
        "--qwen-recovery-manifest",
        type=Path,
        help="exact frozen manifest for the 128 interrupted Qwen postings",
    )
    parser.add_argument(
        "--qwen-recovery-sidecar",
        type=Path,
        help="g1 Qwen response/encoding sidecar paired with the manifest",
    )
    parser.add_argument(
        "--first-accepted-gate-artifact",
        type=Path,
        help="first formal accepted PNS-CoT gate evidence (default: inside run-dir)",
    )
    parser.add_argument(
        "--first-future-accepted-gate-artifact",
        type=Path,
        help=(
            "first strict future CLI-Proxy Judge accepted PNS-CoT gate "
            "(default: inside run-dir)"
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--prepare-only",
        action="store_true",
        help="create/verify only the input snapshot and SQLite contract; make no API calls",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="explicitly authorize tokenizer and Qwen generation requests",
    )
    mode.add_argument(
        "--judge-canary",
        action="store_true",
        help="dispatch only one bounded synthetic DeepSeek Judge canary; no Qwen calls",
    )
    mode.add_argument(
        "--future-judge-canary",
        action="store_true",
        help="dispatch one bounded CLI-Proxy GPT-5.5 future-Judge canary; no Qwen calls",
    )
    mode.add_argument(
        "--rebind-judge-canary-from",
        type=Path,
        metavar="V1_CANARY",
        help=(
            "offline-only reuse of an accepted v1 DeepSeek canary for the exact "
            "v2 Qwen-source-segments binding"
        ),
    )
    return parser


def _resolve_project_path(value: Any) -> Path:
    path = Path(str(value))
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def load_future_judge_resume_contract(path: str | Path) -> dict[str, Any]:
    """Resolve the one frozen future-Judge profile and its isolated artifacts."""

    source = Path(path).resolve()
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("future Judge resume config must be an object")
    if payload.get("contract_id") != (
        "qwen_pns_phase56_v2_cli_proxy_future_judge_resume_20260826"
    ):
        raise ValueError("future Judge resume contract_id differs")
    authorization = payload.get("authorization")
    future = payload.get("future_judge")
    historical = payload.get("historical_judge_view")
    qwen_recovery = payload.get("qwen_request_recovery")
    if not all(
        isinstance(value, dict)
        for value in (authorization, future, historical, qwen_recovery)
    ):
        raise ValueError("future Judge resume contract sections are missing")
    strict_fields = {
        "scope": "future_new_evidence",
        "provider": "cli_proxy",
        "transport": "responses",
        "base_url": "http://127.0.0.1:8317/v1",
        "requested_model": "gpt-5.5",
        "resolved_model": "gpt-5.5",
        "required_response_model": "gpt-5.5",
        "reasoning_effort": "xhigh",
        "protocol_revision": FUTURE_JUDGE_PROTOCOL_REVISION,
        "stream": False,
        "store": False,
        "scientific_raw_attempt_delta": 0,
        "app_max_retries": 0,
        "fallback_allowed": False,
        "default_pass_allowed": False,
    }
    for key, expected in strict_fields.items():
        if future.get(key) != expected:
            raise ValueError(f"future Judge resume field differs: {key}")
    if future.get("thinking") != {"type": "enabled"}:
        raise ValueError("future Judge thinking profile differs")
    if future.get("structured_output") != {
        "type": "json_schema",
        "strict": True,
    }:
        raise ValueError("future Judge structured output profile differs")
    if authorization.get("switch_reason") != "user_authorized_future_judge":
        raise ValueError("future Judge switch reason differs")
    if authorization.get("historical_evidence_rewrite_forbidden") is not True:
        raise ValueError("historical Judge evidence must remain read-only")
    overlay = historical.get("gpt55_recovery_overlay")
    if not isinstance(overlay, dict) or overlay.get("exact_count") != 113:
        raise ValueError("future Judge recovery overlay contract differs")
    if qwen_recovery.get("exact_count") != 128 or qwen_recovery.get(
        "generation"
    ) != "g1":
        raise ValueError("Qwen request recovery contract differs")

    return {
        "contract_id": payload["contract_id"],
        "source_config": source,
        "audit": future_judge_audit_fields(),
        "historical_source_ledger": _resolve_project_path(
            historical["source_ledger"]
        ),
        "recovery_manifest": _resolve_project_path(overlay["manifest"]),
        "recovery_sidecar": _resolve_project_path(overlay["sidecar"]),
        "future_ledger": _resolve_project_path(future["ledger"]),
        "future_canary": _resolve_project_path(future["live_canary"]),
        "qwen_recovery_manifest": _resolve_project_path(qwen_recovery["manifest"]),
        "qwen_recovery_sidecar": _resolve_project_path(qwen_recovery["sidecar"]),
    }


def _bind_frozen_path(
    supplied: str | Path | None,
    expected: Path,
    *,
    label: str,
) -> Path:
    if supplied is None:
        return expected
    resolved = Path(supplied).resolve()
    if resolved != expected:
        raise ValueError(f"{label} differs from the frozen future Judge contract")
    return resolved


def build_future_judge_offline_preflight(semantic_judge: Any) -> dict[str, Any]:
    """Build and validate one prompt-free audit of the final future wire payload."""

    raw = semantic_judge.preflight_chain(
        {
            "question_id": "future-judge-offline-preflight-v1",
            "given_info": "A is a direct cause of B in the stated SCM.",
            "question": "Does intervening on A have a causal effect on B?",
            "meta": {"rung": 1, "query_type": "ate"},
        },
        {
            "steps": [
                {
                    "step_id": "complete_chain",
                    "text": "A directly causes B, so an intervention on A affects B.",
                }
            ],
            "final_answer": "yes",
        },
    )
    return validate_future_judge_preflight(raw)


def _write_or_verify_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if target.exists():
        if target.read_text(encoding="utf-8") != serialized:
            raise RuntimeError(f"refusing to overwrite different artifact: {target}")
        return
    with target.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(serialized)


def configure_deepseek_credential(resolved_config: dict) -> None:
    """Make the configured credential available to the DeepSeek client, silently."""

    env_name = str(resolved_config.get("api_key_env") or "DEEPSEEK_API_KEY")
    if env_name != "DEEPSEEK_API_KEY":
        raise RuntimeError("formal Judge credential env must be DEEPSEEK_API_KEY")
    secret = load_secret(env_name, resolved_config.get("api_key_file"))
    os.environ["DEEPSEEK_API_KEY"] = secret


def open_judge_ledger(
    source_path: str | Path,
    *,
    recovery_manifest: str | Path | None = None,
    recovery_sidecar: str | Path | None = None,
) -> SemanticJudgeLedger | JudgeLedgerOverlay:
    """Open the formal ledger, optionally overlaying the exact recovered 113."""

    if (recovery_manifest is None) != (recovery_sidecar is None):
        raise ValueError(
            "Judge recovery manifest and sidecar must be supplied together"
        )
    source = SemanticJudgeLedger(source_path)
    if recovery_manifest is None:
        return source
    try:
        return JudgeLedgerOverlay(
            source,
            recovery_manifest,
            recovery_sidecar,
            expected_count=113,
        )
    except Exception:
        source.close()
        raise


def build_qwen_recovery_dispatch(
    *,
    runtime: object,
    request_pool: object | None,
    base_urls: list[str],
):
    """Build the one-generation recovery transport over the live Qwen route."""

    if not base_urls:
        raise ValueError("Qwen recovery requires at least one base URL")
    direct_api = None if request_pool is not None else runtime.HttpJsonApi(base_urls[0])

    def dispatch(request, dispatch_id: str) -> RecoveryDispatchResult:
        body = json.loads(request.request_json)
        try:
            if request_pool is not None:
                status, _raw_text, response = request_pool.post_json_for_qid_step(
                    qid=request.qid,
                    step=request.step_index,
                    path=request.endpoint,
                    body=body,
                    request_id=dispatch_id,
                    timeout=1_800.0,
                )
            else:
                status, _raw_text, response = direct_api.post_json(
                    request.endpoint,
                    body,
                    request_id=dispatch_id,
                    timeout=1_800.0,
                )
        except Exception as exc:
            http_status = getattr(exc, "http_status", None)
            if type(http_status) is int:
                return RecoveryDispatchResult(
                    http_status=http_status,
                    response={},
                )
            raise
        return RecoveryDispatchResult(
            http_status=int(status),
            response=response,
        )

    return dispatch


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    recovery_amendment = (
        load_max7_recovery_config(
            args.recovery_amendment_config,
            project_root=ROOT,
        )
        if args.recovery_amendment_config is not None
        else None
    )
    future_resume = (
        load_future_judge_resume_contract(args.future_judge_resume_config)
        if args.future_judge_resume_config is not None
        else None
    )
    if recovery_amendment is not None and future_resume is None:
        raise ValueError(
            "max7 recovery requires the frozen CLI-Proxy future-Judge profile"
        )
    future_specific = (
        args.future_judge_ledger,
        args.future_judge_canary_artifact,
        args.future_judge_offline_preflight_artifact,
    )
    if future_resume is None and (
        any(value is not None for value in future_specific)
        or args.future_judge_canary
    ):
        raise ValueError(
            "future Judge paths/mode require --future-judge-resume-config"
        )
    if future_resume is not None and (
        args.judge_canary or args.rebind_judge_canary_from is not None
    ):
        raise ValueError(
            "future Judge resume cannot use the historical DeepSeek canary modes"
        )
    if future_resume is not None:
        args.future_judge_ledger = _bind_frozen_path(
            args.future_judge_ledger,
            future_resume["future_ledger"],
            label="future Judge ledger",
        )
        args.future_judge_canary_artifact = _bind_frozen_path(
            args.future_judge_canary_artifact,
            future_resume["future_canary"],
            label="future Judge canary",
        )
        if args.execute:
            args.judge_recovery_manifest = _bind_frozen_path(
                args.judge_recovery_manifest,
                future_resume["recovery_manifest"],
                label="historical Judge recovery manifest",
            )
            args.judge_recovery_sidecar = _bind_frozen_path(
                args.judge_recovery_sidecar,
                future_resume["recovery_sidecar"],
                label="historical Judge recovery sidecar",
            )
            args.qwen_recovery_manifest = _bind_frozen_path(
                args.qwen_recovery_manifest,
                future_resume["qwen_recovery_manifest"],
                label="Qwen recovery manifest",
            )
            args.qwen_recovery_sidecar = _bind_frozen_path(
                args.qwen_recovery_sidecar,
                future_resume["qwen_recovery_sidecar"],
                label="Qwen recovery sidecar",
            )
    recovery_workspace_evidence = None
    if recovery_amendment is not None:
        if args.run_dir.resolve() != recovery_amendment.target_journal.parent:
            raise ValueError(
                "max7 recovery --run-dir must be the isolated shared recovery root"
            )
        if Path(future_resume["future_ledger"]).resolve() != (
            recovery_amendment.target_future_judge_ledger
        ):
            raise ValueError(
                "max7 recovery future Judge ledger must be the shared copied ledger"
            )
        recovery_workspace_evidence = verify_recovery_workspace(
            recovery_amendment,
            require_execution_ready=bool(args.execute),
        )
    for label, left, right in (
        (
            "Judge recovery",
            args.judge_recovery_manifest,
            args.judge_recovery_sidecar,
        ),
        (
            "Qwen recovery",
            args.qwen_recovery_manifest,
            args.qwen_recovery_sidecar,
        ),
    ):
        if (left is None) != (right is None):
            raise ValueError(f"{label} manifest and sidecar must be supplied together")
        if left is not None and not args.execute:
            raise ValueError(f"{label} is only valid with --execute")
    if (
        args.initial_valid_rounds != 3
        or args.max_valid_rounds != 5
        or args.max_raw_attempts_per_lineage != 5
    ):
        raise ValueError(
            "formal batch56 rollout policy is frozen to 3 then 5, with five raw attempts"
        )
    base_urls = args.base_urls or ["http://127.0.0.1:8000"]
    if args.adaptive_endpoint_concurrency and len(base_urls) < 2:
        raise ValueError(
            "adaptive endpoint concurrency requires at least two --base-url values"
        )

    artifact = args.artifact or (
        args.run_dir / "qwentest100_demo56_pns_cot_artifact_adaptive.jsonl"
    )
    canary_artifact = args.judge_canary_artifact or (
        args.run_dir / "deepseek_judge_canary.json"
    )
    offline_preflight_artifact = args.offline_preflight_artifact or (
        args.run_dir / "deepseek_judge_offline_preflight.json"
    )
    judge_ledger_path = args.judge_ledger or (
        args.run_dir / "deepseek_semantic_judge.sqlite3"
    )
    if future_resume is not None:
        judge_ledger_path = _bind_frozen_path(
            args.judge_ledger,
            future_resume["historical_source_ledger"],
            label="historical Judge source ledger",
        )
    future_judge_ledger_path = (
        args.future_judge_ledger if future_resume is not None else None
    )
    future_canary_artifact = (
        args.future_judge_canary_artifact if future_resume is not None else None
    )
    future_offline_preflight_artifact = (
        args.future_judge_offline_preflight_artifact
        or (args.run_dir / "cli_proxy_future_judge_offline_preflight.json")
        if future_resume is not None
        else None
    )
    first_accepted_gate_path = args.first_accepted_gate_artifact or (
        args.run_dir / "first_accepted_judge_gate.json"
    )
    first_future_accepted_gate_path = (
        args.first_future_accepted_gate_artifact
        or (args.run_dir / "first_future_accepted_judge_gate.json")
    )
    judge_config = load_cladder_pns_config(args.judge_config)
    resolved_judge = resolve_judge_provider_profile(judge_config)
    historical_semantic_judge = build_deepseek_semantic_judge(
        resolved_judge,
        min_confidence=float(judge_config["judge"]["min_confidence"]),
    )
    semantic_judge = (
        build_future_semantic_judge(
            min_confidence=float(judge_config["judge"]["min_confidence"]),
        )
        if future_resume is not None
        else historical_semantic_judge
    )
    judge_contract = build_judge_contract(resolved_judge)
    phase_contract = load_frozen_phase56_contract(
        args.phase_config,
        input_manifest=args.input,
        judge_contract=judge_contract,
        execution_options={
            "base_urls": list(base_urls),
            "adaptive_endpoint_concurrency": args.adaptive_endpoint_concurrency,
            "endpoint_initial_inflight": args.endpoint_initial_inflight,
            "item_workers": args.item_workers,
            "step_workers_per_item": args.step_workers_per_item,
            "initial_valid_rounds": args.initial_valid_rounds,
            "max_valid_rounds": args.max_valid_rounds,
            "max_raw_attempts_per_lineage": args.max_raw_attempts_per_lineage,
        },
    )
    offline_preflight = run_offline_judge_preflight(
        historical_semantic_judge,
        judge_contract=judge_contract,
    )
    future_offline_preflight = (
        build_future_judge_offline_preflight(semantic_judge)
        if future_resume is not None
        else None
    )
    execution_binding = build_execution_binding(
        runtime_runner=args.runtime_runner,
        input_manifest=args.input,
        run_dir=args.run_dir,
        output_artifact=artifact,
        rollout_contract={
            "initial_valid_rounds": args.initial_valid_rounds,
            "max_valid_rounds": args.max_valid_rounds,
            "terminal_majority": "3:2",
            "max_raw_attempts_per_lineage": args.max_raw_attempts_per_lineage,
            "additional_recovery": False,
            "expected_accepted_items": 56,
            "require_optimized_shorter": True,
            "generation_base_urls": list(base_urls),
        },
        phase_contract=phase_contract,
    )
    args.run_dir.mkdir(parents=True, exist_ok=True)
    write_offline_judge_preflight(
        offline_preflight_artifact,
        offline_preflight,
    )
    if future_offline_preflight_artifact is not None:
        _write_or_verify_json(
            future_offline_preflight_artifact,
            future_offline_preflight,
        )
    if args.future_judge_canary:
        live = run_future_judge_live_canary(future_canary_artifact)
        verified = verify_future_judge_canary_artifact(live)
        print(json.dumps(verified, ensure_ascii=False))
        return 0
    if args.rebind_judge_canary_from is not None:
        attestation = rebind_live_judge_canary(
            args.rebind_judge_canary_from,
            output_path=canary_artifact,
            expected_judge_contract=judge_contract,
            new_execution_binding=execution_binding,
        )
        print(json.dumps(attestation, ensure_ascii=False))
        return 0
    if args.judge_canary:
        raise RuntimeError(
            "v2 forbids a repeat paid Judge canary; use --rebind-judge-canary-from"
        )
    if args.execute:
        if future_resume is not None:
            verify_future_judge_canary_artifact(future_canary_artifact)
        else:
            verify_live_judge_canary(
                canary_artifact,
                expected_judge_contract=judge_contract,
                expected_execution_binding=execution_binding,
            )
            configure_deepseek_credential(resolved_judge)

    runtime = load_batch56_runtime(args.runtime_runner)
    lock = acquire_adaptive_run_lock(args.run_dir / "adaptive_runner.lock")
    runner = None
    request_pool = None
    judge_ledger = None
    qwen_recovery = None
    try:
        runner = runtime.BatchRunner(
            input_path=args.input,
            run_dir=args.run_dir,
            api=runtime.HttpJsonApi(base_urls[0]),
        )
        outer_item_workers = args.item_workers or len(runner.items)
        if len(base_urls) > 1:
            endpoint_config = None
            if args.adaptive_endpoint_concurrency:
                endpoint_config = AdaptiveEndpointConcurrencyConfig(
                    initial_inflight=args.endpoint_initial_inflight,
                    min_inflight=args.endpoint_min_inflight,
                    max_inflight=args.endpoint_max_inflight,
                    increase_step=args.endpoint_increase_step,
                    samples_per_window=args.endpoint_samples_per_window,
                )
            request_pool = install_qid_affinity_request_pool(
                runtime,
                runner,
                base_urls=base_urls,
                item_workers=outer_item_workers,
                adaptive_config=endpoint_config,
                metrics_interval_seconds=args.endpoint_metrics_interval_seconds,
            )
        if args.execute and args.qwen_recovery_manifest is not None:
            g1_manifest = load_g1_manifest(args.qwen_recovery_manifest)
            qwen_recovery = QwenRequestRecovery(
                manifest=g1_manifest,
                sidecar_ledger=args.qwen_recovery_sidecar,
                dispatch=build_qwen_recovery_dispatch(
                    runtime=runtime,
                    request_pool=request_pool,
                    base_urls=list(base_urls),
                ),
                read_only_cache=recovery_amendment is not None,
            )
            if recovery_amendment is not None:
                cached_g1 = qwen_recovery.verify_cached_dispatches(
                    qids=recovery_amendment.target_qids
                )
                runner.journal.set_meta(
                    "max7_recovery_cached_g1_gate_v1",
                    {
                        "schema_version": "max7_recovery_cached_g1_gate_v1",
                        **cached_g1,
                        "source_sidecar_mutated": False,
                    },
                    require_same=True,
                )
            runner.journal.set_meta(
                "qwen_request_recovery_contract_v1",
                {
                    "version": "exact_128_posting_g1_no_g2_v1",
                    "authorized_source_request_count": 128,
                    "manifest": str(args.qwen_recovery_manifest.resolve()),
                    "sidecar": str(args.qwen_recovery_sidecar.resolve()),
                    "source_request_rows_mutated": False,
                    "recovery_generation": "g1",
                    "additional_recovery": False,
                },
                require_same=True,
            )
        config = AdaptiveRolloutConfig(
            initial_valid_rounds=args.initial_valid_rounds,
            max_valid_rounds=args.max_valid_rounds,
            max_raw_attempts_per_lineage=args.max_raw_attempts_per_lineage,
        )
        if args.execute:
            if future_resume is not None:
                judge_ledger = open_future_judge_ledger(
                    judge_ledger_path,
                    future_judge_ledger_path,
                    recovery_manifest=args.judge_recovery_manifest,
                    recovery_sidecar=args.judge_recovery_sidecar,
                    expected_recovery_count=113,
                )
            else:
                judge_ledger = open_judge_ledger(
                    judge_ledger_path,
                    recovery_manifest=args.judge_recovery_manifest,
                    recovery_sidecar=args.judge_recovery_sidecar,
                )
            semantic_contract = {
                "version": "deepseek_semantic_judge_v1",
                **judge_contract,
                "ledger": str(Path(judge_ledger_path).name),
                "canary_artifact": str(Path(canary_artifact).resolve()),
                "offline_preflight_artifact": str(
                    Path(offline_preflight_artifact).resolve()
                ),
                "no_openai_fallback": True,
                "phase_protocol_id": phase_contract["protocol_id"],
                "phase_config": phase_contract["phase_config"],
            }
            if recovery_amendment is None:
                runner.journal.set_meta(
                    "semantic_judge_contract_v1",
                    semantic_contract,
                    require_same=True,
                )
            else:
                historical_contract = runner.journal.get_meta(
                    "semantic_judge_contract_v1", None
                )
                if not isinstance(historical_contract, dict) or not (
                    historical_contract.get("provider") == "deepseek"
                    and historical_contract.get("requested_model")
                    == "deepseek-v4-pro"
                    and historical_contract.get("thinking_type") == "enabled"
                    and historical_contract.get("reasoning_effort") == "max"
                    and historical_contract.get("fallback_allowed") is False
                ):
                    raise RuntimeError(
                        "copied historical semantic Judge contract is invalid"
                    )
                runner.journal.set_meta(
                    "semantic_judge_recovery_source_contract_v1",
                    {
                        "schema_version": (
                            "semantic_judge_recovery_source_contract_v1"
                        ),
                        "historical_contract_preserved": True,
                        "historical_source_ledger": str(
                            Path(judge_ledger_path).resolve()
                        ),
                        "historical_source_read_only": True,
                        "deepseek_new_calls_allowed": False,
                        "future_actual_judge_model": "gpt-5.5",
                        "future_reasoning_effort": "xhigh",
                        "target_qids": list(recovery_amendment.target_qids),
                    },
                    require_same=True,
                )
            if future_resume is not None:
                future_contract = {
                    "version": "cli_proxy_gpt55_future_evidence_v1",
                    **future_resume["audit"],
                    "resume_config": str(
                        future_resume["source_config"].resolve()
                    ),
                    "historical_source_ledger": str(
                        Path(judge_ledger_path).resolve()
                    ),
                    "future_ledger": str(
                        Path(future_judge_ledger_path).resolve()
                    ),
                    "live_canary_artifact": str(
                        Path(future_canary_artifact).resolve()
                    ),
                    "offline_preflight_artifact": str(
                        Path(future_offline_preflight_artifact).resolve()
                    ),
                    "first_future_accepted_gate_artifact": str(
                        Path(first_future_accepted_gate_path).resolve()
                    ),
                    "historical_evidence_read_only": True,
                    "deepseek_future_calls_allowed": False,
                }
                if recovery_amendment is None:
                    runner.journal.set_meta(
                        "future_semantic_judge_contract_v1",
                        future_contract,
                        require_same=True,
                    )
                else:
                    runner.journal.set_meta(
                        "future_semantic_judge_recovery_amendment_v1",
                        {
                            **future_contract,
                            "schema_version": (
                                "future_semantic_judge_recovery_amendment_v1"
                            ),
                            "workspace_manifest": str(
                                recovery_amendment.workspace_manifest
                            ),
                            "source_future_ledger_mutated": False,
                            "target_qids": list(
                                recovery_amendment.target_qids
                            ),
                        },
                        require_same=True,
                    )
            if args.judge_recovery_manifest is not None:
                runner.journal.set_meta(
                    "judge_recovery_overlay_contract_v1",
                    {
                        "version": "exact_113_gpt55_responses_xhigh_strict_v1",
                        "authorized_source_evidence_count": 113,
                        "manifest": str(args.judge_recovery_manifest.resolve()),
                        "sidecar": str(args.judge_recovery_sidecar.resolve()),
                        "actual_judge_model": "gpt-5.5",
                        "switch_reason": "user_specified_backup_judge",
                        "fallback_used": False,
                        "scientific_raw_attempt_delta": 0,
                    },
                    require_same=True,
                )
        adapter = Batch56AdaptiveAdapter(
            runtime=runtime,
            runner=runner,
            config=config,
            item_workers=args.item_workers,
            step_workers_per_item=args.step_workers_per_item,
            dataset_pns=DatasetPnsExecutionConfig(),
            semantic_judge=semantic_judge if args.execute else None,
            judge_ledger=judge_ledger,
            request_recovery=qwen_recovery,
            recovery_amendment=(
                recovery_amendment.amendment()
                if recovery_amendment is not None
                else None
            ),
        )
        if args.prepare_only:
            adapter.initialize()
            print(
                json.dumps(
                    {
                        "status": "PREPARED_NO_API_CALLS",
                        "run_dir": str(args.run_dir.resolve()),
                        "journal": str(runner.journal.path),
                        **(
                            {"recovery_workspace": recovery_workspace_evidence}
                            if recovery_workspace_evidence is not None
                            else {}
                        ),
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if future_resume is not None and recovery_amendment is None:
            first_future = run_until_first_future_accepted_gate(
                adapter,
                gate_path=first_future_accepted_gate_path,
                expected_items=56,
            )
            print(
                json.dumps(
                    {
                        "status": "FIRST_FUTURE_ACCEPTED_GATE_PASSED",
                        "question_id": first_future["question_id"],
                        "actual_judge_model": first_future[
                            "judge_acceptance"
                        ].get("actual_judge_model"),
                        "gate": str(first_future_accepted_gate_path.resolve()),
                    },
                    ensure_ascii=False,
                )
            )
        elif recovery_amendment is not None:
            runner.journal.set_meta(
                "max7_recovery_future_judge_start_gate_v1",
                {
                    "schema_version": "max7_recovery_future_judge_start_gate_v1",
                    "passed": True,
                    "live_canary_artifact": str(
                        Path(future_canary_artifact).resolve()
                    ),
                    "actual_judge_model": "gpt-5.5",
                    "thinking_type": "enabled",
                    "reasoning_effort": "xhigh",
                    "fallback_allowed": False,
                    "target_qids": list(recovery_amendment.target_qids),
                    "historical_first_future_gate_replay_required": False,
                },
                require_same=True,
            )
        rows = run_with_first_accepted_gate(
            adapter,
            output_path=artifact,
            gate_path=first_accepted_gate_path,
            expected_items=56,
        )
        recovery_report_path = None
        completion_manifest_path = None
        if recovery_amendment is not None:
            final_workspace_evidence = verify_recovery_workspace(
                recovery_amendment,
                require_execution_ready=True,
            )
            recovery_report_path = (
                args.run_dir / "max7_raw_attempt_recovery_report.json"
            )
            recovery_report = build_max7_recovery_report_payload(
                recovery_amendment.amendment(),
                artifacts=rows,
                item_rows=runner.journal.item_rows(),
                source_request_rows=read_request_rows_read_only(
                    recovery_amendment.source_journal
                ),
                request_rows=runner.journal.request_rows(),
                judge_records=judge_ledger.completed_records(),
                workspace_evidence=final_workspace_evidence,
            )
            _write_or_verify_json(recovery_report_path, recovery_report)

            source_root = recovery_amendment.source_journal.parent
            review_root = args.run_dir / "existing_candidate_review18"
            completion_manifest = build_phase56_completion_manifest_payload(
                phase56_config_path=args.phase_config,
                phase56_resume_config_path=args.future_judge_resume_config,
                original_phase56_journal_path=(
                    recovery_amendment.source_journal
                ),
                frozen_subset_manifest_path=(
                    source_root / "pns_frozen_subset_manifest_56.json"
                ),
                demo_source_path=(source_root / "batch_input_56_adaptive.jsonl"),
                accepted_pnscot_path=artifact,
                evidence_paths_by_source_class={
                    "original_frozen": [
                        recovery_amendment.source_journal,
                        args.phase_config,
                    ],
                    "existing_candidate_recovery": [
                        review_root / "batch_manifest.json",
                        review_root / "terminal_report.json",
                        ROOT
                        / "configs/experiments/"
                        "qwen_pns_existing_candidate_review18_20260826_v1.yaml",
                    ],
                    "max7_raw_attempt_amendment": [
                        recovery_report_path,
                        recovery_amendment.source_path,
                        recovery_amendment.target_journal,
                    ],
                },
            )
            completion_manifest_path = (
                args.run_dir / "phase56_completion_manifest.json"
            )
            _write_or_verify_json(
                completion_manifest_path,
                completion_manifest,
            )
        lifecycle = adapter.journal_lifecycle_accounting()
        print(
            json.dumps(
                {
                    "status": "COMPLETE",
                    "items": len(rows),
                    "optimized": sum(row["optimized"] is True for row in rows),
                    "fallback": sum(row["fallback"] is True for row in rows),
                    "journal_lifecycle": lifecycle,
                    "artifact": str(artifact.resolve()),
                    "journal": str(runner.journal.path),
                    **(
                        {
                            "max7_recovery_report": str(
                                recovery_report_path.resolve()
                            ),
                            "phase56_completion_manifest": str(
                                completion_manifest_path.resolve()
                            ),
                        }
                        if recovery_report_path is not None
                        and completion_manifest_path is not None
                        else {}
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        if request_pool is not None:
            request_pool.close()
        if qwen_recovery is not None:
            qwen_recovery.close()
        if judge_ledger is not None:
            judge_ledger.close()
        if runner is not None:
            runner.journal.close()
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
