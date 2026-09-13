# Preserved multi-turn history control flow

These are source excerpts for inspection, not a standalone runner. They preserve the displayed lines without changing control flow. The retained checkout date does not establish byte identity with an earlier runtime.

## Original lines 754-802

```python
def run_one_request(*, request: dict[str, Any], repair_retry: int, store_model_content: bool) -> dict[str, Any]:
    item: AblationItem = request["_item"]
    frame = item.frame
    arm_config = request["arm_config"]
    native_tool_protocol = bool(arm_config.get("native_tool_protocol"))
    max_tokens = request["max_tokens"]
    hard_turn_limit = int(request["max_turns"])
    adaptive_turns = bool(request.get("adaptive_turns"))
    initial_turn_budget = int(request.get("initial_turn_budget") or hard_turn_limit)
    turn_budget = AdaptiveTurnBudget(
        hard_limit=hard_turn_limit,
        initial_budget=initial_turn_budget,
        enabled=adaptive_turns,
        no_progress_patience=int(request.get("turn_no_progress_patience") or 0),
    )
    max_tokens_for_repair = int(max_tokens if max_tokens is not None else arm_config.get("repair_max_tokens") or 4000)
    messages = build_initial_messages(
        item,
        max_turns=hard_turn_limit,
        arm_config=arm_config,
        experiment_skill_context=request.get("_experiment_skill_context"),
        adaptive_turns=adaptive_turns,
        initial_turn_budget=initial_turn_budget,
    )
    messages = apply_prompt_think_floor(messages, arm_config)
    turns: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    usage = zero_usage()
    final_content = ""
    final_response: dict[str, Any] | None = None
    api_errors: list[str] = []
    semantic_revision_count = 0

    for turn_index in range(1, hard_turn_limit + 1):
        turn_arm_config = (
            native_turn_arm_config(
                arm_config,
                tool_results,
                available_operations=list(frame.available_operations),
            )
            if native_tool_protocol
            else arm_config
        )
        response = call_deepseek_chat(
            messages,
            turn_arm_config,
            max_tokens=max_tokens,
            user_id=f"{frame.task_id}:turn{turn_index}",
        )
```

## Original lines 956-1040

```python
            turns[-1]["validation_error"] = evidence["error"]
            messages.append({"role": "assistant", "content": content})
            auto_tool = auto_numeric_tool_for_query_type(str(evidence.get("query_type") or ""))
            if auto_tool and evidence.get("error", "").startswith("final_before_numeric_"):
                result = execute_cladder_tool(item, auto_tool, {})
                result["turn"] = turn_index
                result["auto_injected_by_runtime_gate"] = True
                tool_results.append(result)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Runtime-required numeric evidence tool observation JSON:\n"
                            f"{json.dumps(result, ensure_ascii=False, sort_keys=True)}\n\n"
                            "Revise the final DecisionTrace using this numeric evidence. "
                            "Return final JSON as {'action':'final','decision_trace':{...}}."
                        ),
                    }
                )
                if turn_budget.allow_next_turn(
                    completed_turn=turn_index,
                    progress=result.get("status") == "executed",
                    signature=f"auto_tool:{auto_tool}",
                    reason="auto_numeric_evidence",
                ):
                    continue
                break
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Final answer rejected: {evidence['message']} Before finalizing, call at least one graph evidence tool "
                        f"from {sorted(GRAPH_EVIDENCE_TOOLS)} and at least one probability/numeric evidence tool from {sorted(PROBABILITY_EVIDENCE_TOOLS)}. "
                        "Then return final DecisionTrace JSON with tool_calls, causal_checks, graph_state.path_evidence, and numeric probability evidence."
                    ),
                }
            )
            if turn_budget.allow_next_turn(
                completed_turn=turn_index,
                progress=True,
                signature=f"final_rejected:{evidence['error']}",
                reason="repairable_final_rejection",
            ):
                continue
            break

        if action.get("action") == "tool":
            result = execute_cladder_tool(item, action.get("tool_name"), action.get("arguments"))
            result["turn"] = turn_index
            tool_results.append(result)
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Tool observation JSON:\n"
                        f"{json.dumps(result, ensure_ascii=False, sort_keys=True)}\n\n"
                        "Continue. You may call another tool if needed, or return final DecisionTrace JSON. "
                        "You must base the final answer on the observations and the original question."
                    ),
                }
            )
            tool_signature = json.dumps(
                {
                    "tool_name": action.get("tool_name"),
                    "arguments": action.get("arguments") or {},
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            if turn_budget.allow_next_turn(
                completed_turn=turn_index,
                progress=result.get("status") == "executed",
                signature=f"tool:{tool_signature}",
                reason="tool_result",
            ):
                continue
            break

        messages.append({"role": "assistant", "content": content})
        messages.append(
            {
                "role": "user",
                "content": (
                    "Invalid protocol or final answer before any tool observation. "
```
