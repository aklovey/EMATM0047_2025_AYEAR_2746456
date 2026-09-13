# Preserved multi-turn history control flow

These are source excerpts for inspection, not a standalone runner. They preserve the displayed lines without changing control flow. The retained checkout date does not establish byte identity with an earlier runtime.

## Original lines 778-808

```python
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
```

## Original lines 1014-1040

```python
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
```
