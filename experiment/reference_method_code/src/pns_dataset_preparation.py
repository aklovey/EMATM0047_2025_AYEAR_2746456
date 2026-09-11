from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .dataset_profiles import pns_segmentation_from_sample
from .datasets.base import PnsExplicitFallback


@dataclass(frozen=True)
class PreparedPnsSegment:
    step_index: int
    source_field: str
    char_start: int
    char_end: int
    text: str
    answer_exposed_prefix: bool


@dataclass(frozen=True)
class PreparedDatasetPnsItem:
    dataset_name: str
    config_id: str
    question_id: str
    parent_reasoning: str
    segments: tuple[PreparedPnsSegment, ...]
    eligible_step_indexes: tuple[int, ...]
    segmentation_source: str
    semantic_reference_source: str
    semantic_reference_fields: tuple[str, ...]
    parent_source: str
    segment_source: str
    used_fallback: bool
    fallback_policy: str | None
    contract: dict[str, Any]


def prepare_dataset_pns_item(
    raw_sample: dict[str, Any],
    *,
    dataset_name: str,
    canonical_context_authorization: str | None,
    explicit_fallback: PnsExplicitFallback | None = None,
    fallback_name: str | None = None,
) -> PreparedDatasetPnsItem:
    """Prepare one dataset-routed PNS parent from its frozen Qwen boundaries.

    Dataset programmatic steps are semantic-reference metadata only.  They do
    not replace, split, align one-to-one with, or otherwise rewrite the frozen
    latest-Qwen parent and its already-materialized source-preserving segments.
    """

    if canonical_context_authorization != "pns_intervention_only":
        raise PermissionError(
            "canonical reasoning context requires pns_intervention_only authorization"
        )

    def guarded_fallback(sample: dict[str, Any]):
        if not isinstance(fallback_name, str) or not fallback_name.strip():
            raise ValueError("fallback_name is required when explicit fallback runs")
        assert explicit_fallback is not None
        return explicit_fallback(sample)

    segmentation = pns_segmentation_from_sample(
        raw_sample,
        dataset_name=dataset_name,
        explicit_fallback=(
            guarded_fallback if explicit_fallback is not None else None
        ),
    )
    used_fallback = segmentation.source == "explicit_fallback"
    semantic_steps = tuple(segmentation.steps)
    if not semantic_steps:
        raise ValueError("dataset PNS semantic reference returned no steps")

    parent = raw_sample.get("parent_reasoning")
    if not isinstance(parent, str) or not parent:
        raise ValueError("frozen Qwen parent_reasoning must be nonempty text")
    raw_segments = raw_sample.get("segments")
    if not isinstance(raw_segments, (list, tuple)) or not raw_segments:
        raise ValueError("frozen Qwen parent segments are required")

    prepared: list[PreparedPnsSegment] = []
    cursor = 0
    exposure_started = False
    for position, raw_segment in enumerate(raw_segments, 1):
        if not isinstance(raw_segment, dict):
            raise ValueError(f"frozen Qwen segment {position} is not a mapping")
        step_index = raw_segment.get("step_index")
        char_start = raw_segment.get("char_start")
        char_end = raw_segment.get("char_end")
        text = raw_segment.get("text")
        answer_exposed = raw_segment.get("answer_exposed_prefix")
        if type(step_index) is not int or step_index != position:
            raise ValueError("frozen Qwen segment indexes must be contiguous from 1")
        if type(char_start) is not int or char_start != cursor:
            raise ValueError("frozen Qwen segment char_start is not contiguous")
        if type(char_end) is not int or not cursor < char_end <= len(parent):
            raise ValueError("frozen Qwen segment char_end is not strictly increasing")
        if not isinstance(text, str) or text != parent[char_start:char_end]:
            raise ValueError("frozen Qwen segment text is not an exact parent slice")
        if not isinstance(answer_exposed, bool):
            raise ValueError("frozen Qwen segment answer exposure must be boolean")
        if answer_exposed:
            exposure_started = True
        elif exposure_started:
            raise ValueError("answer exposure must be a cumulative terminal suffix")
        prepared.append(
            PreparedPnsSegment(
                step_index=step_index,
                source_field=f"qwen_parent_segment_{step_index}",
                char_start=char_start,
                char_end=char_end,
                text=text,
                answer_exposed_prefix=exposure_started,
            )
        )
        cursor = char_end

    if cursor != len(parent):
        raise ValueError("frozen Qwen segments do not cover the complete parent")
    if "".join(segment.text for segment in prepared) != parent:
        raise ValueError("frozen Qwen segments do not exactly reconstruct the parent")
    eligible = tuple(
        segment.step_index
        for segment in prepared
        if not segment.answer_exposed_prefix
    )
    if not eligible:
        raise ValueError("dataset PNS item has no intervention-eligible steps")
    safe_step_count = raw_sample.get("safe_step_count")
    if type(safe_step_count) is not int or safe_step_count != len(eligible):
        raise ValueError("frozen Qwen safe_step_count does not match its segments")
    resolved_fallback = str(fallback_name) if used_fallback else None
    semantic_reference_fields = tuple(
        step.source_field for step in semantic_steps
    )
    return PreparedDatasetPnsItem(
        dataset_name=segmentation.dataset_name,
        config_id=segmentation.config_id,
        question_id=str(
            raw_sample.get("question_id")
            or raw_sample.get("id")
            or raw_sample.get("uid")
            or "unknown"
        ),
        parent_reasoning=parent,
        segments=tuple(prepared),
        eligible_step_indexes=eligible,
        segmentation_source="frozen_qwen_parent_segments",
        semantic_reference_source=segmentation.source,
        semantic_reference_fields=semantic_reference_fields,
        parent_source="parent_reasoning",
        segment_source="segments",
        used_fallback=used_fallback,
        fallback_policy=resolved_fallback,
        contract={
            "dataset_scope": segmentation.dataset_scope,
            "dataset_config_id": segmentation.config_id,
            "segmentation_source": "frozen_qwen_parent_segments",
            "parent_source": "parent_reasoning",
            "segment_source": "segments",
            "boundary_authority": "frozen_qwen_parent_segments",
            "source_preserving": True,
            "semantic_reference_source": segmentation.source,
            "semantic_reference_fields": list(semantic_reference_fields),
            "programmatic_role": "semantic_reference_alignment_anchor_only",
            "one_to_one_required": False,
            "same_path_required": False,
            "canonical_text_generation_visible": False,
            "canonical_text_judge_visible": True,
            "canonical_text_judge_scope": "advisory_non_answer_steps_only",
            "canonical_context_authorization": canonical_context_authorization,
            "model_context_scope": "pns_intervention_only",
            "planner_visible": False,
            "test_prompt_visible": False,
            "fallback_used": used_fallback,
            "fallback_policy": resolved_fallback,
            "omitted_empty_source_fields": list(
                segmentation.omitted_empty_source_fields
            ),
        },
    )
