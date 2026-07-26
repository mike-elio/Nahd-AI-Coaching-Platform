from typing import Any

from app.rules.checklist_selection import (
    _build_alternative_path_summaries,
    _build_context,
    _build_primary_path_summary,
    _candidate_pool,
    _compute_target_step_count,
    _format_selected_steps,
    _select_phase_sequence,
    _select_steps,
    _validate_selected_steps,
    validate_diagnostic_checklist_output,
)
from app.rules.text_processing import collapse_whitespace


def _resolve_reasoning_stage(case_summary: dict, reasoning_input: Any) -> dict:
    if isinstance(reasoning_input, dict) and reasoning_input.get("primary_path"):
        return reasoning_input

    # Compatibility fallback for older callers that still pass only the hypotheses list.
    hypotheses = reasoning_input if isinstance(reasoning_input, list) else []
    top_hypothesis = collapse_whitespace(hypotheses[0].get("title", "")) if hypotheses else "Validate the dominant failure path"
    return {
        "case_summary": case_summary,
        "primary_path": top_hypothesis or "Validate the dominant failure path",
        "alternative_paths": [],
        "possible_causes": [collapse_whitespace(item.get("title", "")) for item in hypotheses[:6] if collapse_whitespace(item.get("title", ""))],
        "primary_issue_family": case_summary.get("primary_issue_family") or case_summary.get("issue_family") or "authentication",
        "selected_reasoning_cluster": case_summary.get("selected_reasoning_cluster", "no_cluster_alignment"),
        "ranked_hypotheses": hypotheses,
        "reasoning_trace_internal": {},
        "top_signal_tags": case_summary.get("tag_signals", []),
    }


def _build_checklist_trace_internal(ctx: dict, selected_steps: list[dict], candidate_pool: list[dict], selected_phases: list[str], target_count: int) -> dict:
    return {
        "target_step_count": target_count,
        "selected_phases": selected_phases,
        "candidate_pool_size": len(candidate_pool),
        "selected_semantic_keys": [step["semantic_key"] for step in selected_steps],
        "selected_step_families": [step["step_family"] for step in selected_steps],
        "top_candidate_keys": [candidate["semantic_key"] for candidate in candidate_pool[:12]],
        "independent_count_rule": "diagnostic_checklist length is computed independently from possible_causes length",
    }


def _build_checklist_generation_metadata(ctx: dict, target_count: int, selected_phases: list[str]) -> dict:
    return {
        "active_domain": ctx["reasoning_domain"],
        "primary_issue_family": ctx["primary_issue_family"],
        "selected_reasoning_cluster": ctx["selected_reasoning_cluster"],
        "target_step_count": target_count,
        "selected_phase_count": len(selected_phases),
        "trusted_tag_count": len(ctx["trusted_tags"]),
        "supporting_tag_count": len(ctx["supporting_tags"]),
        "boundary_hint_count": len(ctx["boundary_hints"]),
        "alternative_path_count": len(ctx["alternative_paths"]),
    }


def build_rule_based_checklist(problem_text: str, case_summary: dict, reasoning_input: Any) -> dict:
    reasoning_stage = _resolve_reasoning_stage(case_summary, reasoning_input)
    ctx = _build_context(problem_text, case_summary, reasoning_stage)
    target_count = _compute_target_step_count(ctx)
    selected_phases = _select_phase_sequence(ctx, target_count)
    candidates = _candidate_pool(ctx, selected_phases)
    selected_steps = _select_steps(ctx, target_count, selected_phases, candidates)
    selected_steps = _validate_selected_steps(ctx, selected_steps, candidates, target_count, selected_phases)
    selected_step_family_sequence = [step["step_family"] for step in selected_steps]
    diagnostic_checklist = _format_selected_steps(selected_steps, ctx)

    return {
        "diagnostic_checklist": diagnostic_checklist,
        "target_display_count": target_count,
        "top_signal_tags": ctx["tag_signals"],
        "primary_diagnostic_path": _build_primary_path_summary(ctx),
        "alternative_paths": _build_alternative_path_summaries(ctx),
        "selected_step_family_sequence": selected_step_family_sequence,
        "checklist_trace_internal": _build_checklist_trace_internal(ctx, selected_steps, candidates, selected_phases, target_count),
        "checklist_generation_metadata": _build_checklist_generation_metadata(ctx, target_count, selected_phases),
        "reasoning_summary": collapse_whitespace(
            f"Checklist synthesis prioritized the {ctx['primary_issue_family'].replace('_', ' ')} direction and converted the reasoning outputs into a short workflow with {target_count} discriminative steps."
        ),
    }


def generate_diagnostic_checklist(problem_text: str, case_summary: dict, reasoning_input: Any) -> dict:
    data = build_rule_based_checklist(problem_text, case_summary, reasoning_input)
    return validate_diagnostic_checklist_output(data, case_summary)


__all__ = [
    "build_rule_based_checklist",
    "generate_diagnostic_checklist",
]
