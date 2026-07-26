from typing import Any, Dict, List, Optional

from app.rules.command_selection import select_commands_for_step
from app.rules.tag_interpretation import interpret_prediction_output
from app.rules.text_processing import to_reasoning_domain
from app.schemas.requests import DiagnoseRequest
from app.schemas.responses import ChecklistStepModel, DiagnosticResultModel, ReferenceModel
from app.services.checklist import generate_diagnostic_checklist
from app.services.references import attach_step_references
from app.services.root_cause import generate_root_cause_hypotheses
from app.services.tag_prediction import predict_top_3_tags


REPORT_TITLE = "Evidence-Backed Diagnostic Checklist Engine"


def _normalize_text_key(value: Any) -> str:
    return " ".join(str(value).split()).strip().lower()


def _append_unique_text(target: List[str], values: List[Any], skip: Optional[set] = None) -> None:
    skip = skip or set()
    existing_keys = {_normalize_text_key(item) for item in target}
    skip_keys = {_normalize_text_key(item) for item in skip}

    for raw_value in values:
        cleaned = " ".join(str(raw_value).split()).strip()
        key = cleaned.lower()
        if not cleaned or key in existing_keys or key in skip_keys:
            continue
        target.append(cleaned)
        existing_keys.add(key)


def build_enriched_problem_text(problem_text: str, preferred_domain: Optional[str], preferred_stack: Optional[str]) -> str:
    lines = [problem_text.strip()]
    if preferred_domain:
        lines.append(f"Preferred diagnostic domain: {preferred_domain}")
    if preferred_stack:
        lines.append(f"Preferred technology stack: {preferred_stack}")
    return "\n".join(lines)


def extract_primary_path(checklist_stage: dict, root_stage: dict) -> str:
    explicit_primary_path = " ".join(str(root_stage.get("primary_path", "")).split()).strip()
    if explicit_primary_path:
        return explicit_primary_path

    primary_path = checklist_stage.get("primary_diagnostic_path") or {}
    title = " ".join(str(primary_path.get("title", "")).split()).strip()
    if title:
        return title

    for step in checklist_stage.get("diagnostic_checklist", []):
        if str(step.get("path_kind", "")).strip().lower() != "primary":
            continue
        title = " ".join(str(step.get("path_title", "")).split()).strip()
        if title:
            return title

    for step in checklist_stage.get("diagnostic_checklist", []):
        if not isinstance(step, dict):
            continue
        action = " ".join(str(step.get("action", "")).split()).strip()
        title = " ".join(str(step.get("title", "")).split()).strip()
        if action or title:
            return action or title

    issue_family = " ".join(
        str(
            root_stage.get("primary_issue_family")
            or root_stage.get("case_summary", {}).get("primary_issue_family")
            or root_stage.get("case_summary", {}).get("issue_family", "")
        ).split()
    ).strip()
    if issue_family:
        return issue_family.replace("_", " ").title()
    return "Collect exact failure evidence from the affected component"


def extract_alternative_paths(root_stage: dict, checklist_stage: dict) -> List[str]:
    primary_path = extract_primary_path(checklist_stage, root_stage)
    alternatives: List[str] = []

    _append_unique_text(alternatives, root_stage.get("alternative_paths", []), skip={primary_path})

    checklist_alternatives = []
    for item in checklist_stage.get("alternative_paths", []):
        checklist_alternatives.append(item.get("title", "") if isinstance(item, dict) else item)
    _append_unique_text(alternatives, checklist_alternatives, skip={primary_path})

    return alternatives[:4]


GENERIC_CAUSE_TEXTS = {
    "primary diagnostic path",
    "diagnostic path",
    "possible cause",
    "root cause",
    "runtime issue",
    "configuration issue",
    "network issue",
    "authentication problem",
}


def _is_generic_cause(value: Any) -> bool:
    text = _normalize_text_key(value)
    return not text or text in GENERIC_CAUSE_TEXTS


def extract_possible_causes(root_stage: dict, checklist_stage: dict) -> List[str]:
    causes: List[str] = []
    _append_unique_text(causes, [item for item in root_stage.get("possible_causes", []) if not _is_generic_cause(item)])

    ranked_items = root_stage.get("ranked_hypotheses", []) or root_stage.get("root_cause_hypotheses", [])
    hypothesis_titles = []
    for item in ranked_items:
        if not isinstance(item, dict):
            continue
        try:
            confidence = float(item.get("confidence", 1.0))
        except Exception:
            confidence = 1.0
        title = item.get("title", "")
        if confidence >= 0.25 and not _is_generic_cause(title):
            hypothesis_titles.append(title)
    _append_unique_text(causes, hypothesis_titles)

    primary_path = checklist_stage.get("primary_diagnostic_path") or {}
    supporting_titles = [
        item.get("title", "")
        for item in primary_path.get("supporting_hypotheses", [])
        if isinstance(item, dict) and not _is_generic_cause(item.get("title", ""))
    ]
    _append_unique_text(causes, supporting_titles)
    return causes[:6]


def normalize_checklist(enriched_stage: dict) -> List[ChecklistStepModel]:
    normalized: List[ChecklistStepModel] = []
    seen_titles = set()

    for raw_item in enriched_stage.get("diagnostic_checklist", []):
        if not isinstance(raw_item, dict):
            continue

        title = " ".join(str(raw_item.get("title", "")).split()).strip()
        action = " ".join(str(raw_item.get("action", "")).split()).strip()
        expected = " ".join(str(raw_item.get("expected_result", raw_item.get("expected", ""))).split()).strip()
        if_this_fails = " ".join(str(raw_item.get("if_failed", raw_item.get("if_this_fails", ""))).split()).strip()
        reference_title = " ".join(str(raw_item.get("reference_label", "")).split()).strip()
        reference_url = " ".join(str(raw_item.get("reference_url", "")).split()).strip()
        reference_source_type = " ".join(str(raw_item.get("reference_source_type", "official_docs")).split()).strip() or "official_docs"

        if not all([title, action, expected, if_this_fails, reference_title, reference_url]):
            continue

        title_key = title.lower()
        if title_key in seen_titles:
            continue

        normalized.append(
            ChecklistStepModel(
                step_number=int(raw_item.get("step", raw_item.get("step_number", len(normalized) + 1))),
                title=title,
                action=action,
                expected=expected,
                reference=ReferenceModel(
                    title=reference_title,
                    url=reference_url,
                    source_type=reference_source_type,
                ),
                if_this_fails=if_this_fails,
            )
        )
        seen_titles.add(title_key)

        if len(normalized) >= 6:
            break

    return normalized


def normalize_references_summary(enriched_stage: dict, checklist: Optional[List[ChecklistStepModel]] = None) -> List[ReferenceModel]:
    normalized: List[ReferenceModel] = []
    seen_urls = set()

    for item in enriched_stage.get("references_summary", []):
        if not isinstance(item, dict):
            continue
        title = " ".join(str(item.get("title", "")).split()).strip()
        url = " ".join(str(item.get("url", "")).split()).strip()
        source_type = " ".join(str(item.get("source_type", "")).split()).strip() or "official_docs"
        if not title or not url or url in seen_urls:
            continue
        normalized.append(ReferenceModel(title=title, url=url, source_type=source_type))
        seen_urls.add(url)

    if normalized or not checklist:
        return normalized[:5]

    for step in checklist:
        url = step.reference.url.strip()
        if not url or url in seen_urls:
            continue
        normalized.append(
            ReferenceModel(
                title=step.reference.title.strip(),
                url=url,
                source_type=step.reference.source_type.strip() or "official_docs",
            )
        )
        seen_urls.add(url)
        if len(normalized) >= 5:
            break

    return normalized


def should_include_expert_output(payload: DiagnoseRequest) -> bool:
    return payload.display_level == "expert"


def _clean_text(value: Any) -> str:
    return " ".join(str(value).split()).strip()


def _confidence_label(value: Any) -> str:
    try:
        confidence = float(value)
    except Exception:
        confidence = 0.0
    if confidence >= 0.82:
        return "high"
    if confidence >= 0.62:
        return "medium"
    return "low"


def _evidence_focus_from_hypothesis(hypothesis: dict) -> List[str]:
    focus_items: List[str] = []
    families = [_clean_text(item).replace("_", " ") for item in hypothesis.get("families", []) if _clean_text(item)]
    boundaries = [_clean_text(item).replace("_", " ") for item in hypothesis.get("boundaries", []) if _clean_text(item)]
    tags = [_clean_text(item) for item in hypothesis.get("tags", []) if _clean_text(item)]

    _append_unique_text(focus_items, [f"Family signal: {item}" for item in families[:2]])
    _append_unique_text(focus_items, [f"Boundary signal: {item}" for item in boundaries[:2]])
    _append_unique_text(focus_items, [f"Stack signal: {item}" for item in tags[:3]])

    if not focus_items:
        focus_items.append("Collect runtime evidence tied to the exact failing transaction before broadening the search.")
    return focus_items[:5]


def build_hypothesis_details(root_stage: dict, checklist_stage: dict) -> List[Dict[str, Any]]:
    checklist_steps = checklist_stage.get("diagnostic_checklist", [])
    fallback_next_check = ""
    if checklist_steps and isinstance(checklist_steps[0], dict):
        fallback_next_check = _clean_text(checklist_steps[0].get("action", ""))

    details: List[Dict[str, Any]] = []
    seen_titles = set()
    for item in root_stage.get("ranked_hypotheses", []) or root_stage.get("root_cause_hypotheses", []):
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title", ""))
        if not title:
            continue
        title_key = title.lower()
        if title_key in seen_titles:
            continue

        confidence = item.get("confidence", 0.0)
        selected_because = _clean_text(item.get("why_likely", ""))
        evidence_to_collect = _evidence_focus_from_hypothesis(item)
        next_best_check = fallback_next_check
        for step in checklist_steps:
            if not isinstance(step, dict):
                continue
            step_action = _clean_text(step.get("action", ""))
            step_key = _clean_text(step.get("semantic_key", "")).replace("_", " ")
            if step_action and any(token and token in title.lower() for token in step_key.split()):
                next_best_check = step_action
                break

        details.append(
            {
                "title": title,
                "confidence": confidence,
                "selected_because": selected_because
                or f"This hypothesis remained in the ranked set with {_confidence_label(confidence)} confidence after symptom and tag evidence were compared.",
                "evidence_to_collect": evidence_to_collect,
                "confirming_evidence": f"Evidence confirms this branch if the collected signals show the expected failure at the related {', '.join(evidence_to_collect[:2]).lower()}.",
                "disconfirming_evidence": "This branch weakens if the exact failing transaction passes the listed checks while the symptom still reproduces unchanged.",
                "next_best_check": next_best_check or "Run the highest-ranked checklist action against the captured failing transaction.",
            }
        )
        seen_titles.add(title_key)
        if len(details) >= 6:
            break
    return details


def build_evidence_plan(checklist_stage: dict, enriched_stage: dict) -> List[Dict[str, Any]]:
    stage_4_steps = enriched_stage.get("diagnostic_checklist", [])
    stage_3_steps = checklist_stage.get("diagnostic_checklist", [])
    source_steps = stage_4_steps if stage_4_steps else stage_3_steps
    evidence_plan: List[Dict[str, Any]] = []

    for raw_step in source_steps:
        if not isinstance(raw_step, dict):
            continue
        semantic_key = _clean_text(raw_step.get("semantic_key", ""))
        action = _clean_text(raw_step.get("action", ""))
        expected = _clean_text(raw_step.get("expected_result", raw_step.get("expected", "")))
        if_failed = _clean_text(raw_step.get("if_failed", raw_step.get("if_this_fails", "")))
        if not all([semantic_key, action, expected, if_failed]):
            continue
        evidence_plan.append(
            {
                "step_number": int(raw_step.get("step", raw_step.get("step_number", len(evidence_plan) + 1))),
                "semantic_key": semantic_key,
                "title": _clean_text(raw_step.get("title", "")),
                "selected_because": _clean_text(raw_step.get("why", ""))
                or "This step was selected because its semantic key matched the ranked symptom, tag, boundary, or issue-family evidence.",
                "action": action,
                "expected": expected,
                "if_failed": if_failed,
                "evidence_to_collect": action,
                "confirming_evidence": expected,
                "disconfirming_evidence": if_failed,
                "priority_score": raw_step.get("anchor_confidence", 0.0),
                "anchor_confidence": raw_step.get("anchor_confidence", 0.0),
                "evidence_type": _clean_text(raw_step.get("phase", "")) or "diagnostic_check",
            }
        )
    return evidence_plan[:6]


def build_command_plan(case_summary: dict, evidence_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    domain = case_summary.get("domain", "")
    context_tags = []
    for key in ("top_tags", "trusted_tags", "supporting_tags", "weak_tags"):
        values = case_summary.get(key, [])
        if isinstance(values, list):
            context_tags.extend(values)
    command_plan: List[Dict[str, Any]] = []
    for item in evidence_plan:
        commands = select_commands_for_step(domain, item.get("semantic_key", ""), context_tags=context_tags)
        if not commands:
            continue
        command_plan.append(
            {
                "step_number": item.get("step_number"),
                "semantic_key": item.get("semantic_key", ""),
                "action": item.get("action", ""),
                "expected": item.get("expected", ""),
                "if_failed": item.get("if_failed", ""),
                "priority_score": item.get("priority_score", item.get("anchor_confidence", 0.0)),
                "selected_because": item.get("selected_because", ""),
                "commands": commands,
            }
        )
    return command_plan[:6]


def build_diagnostic_trace(stage_1: dict, interpretation: dict, root_stage: dict, checklist_stage: dict) -> Dict[str, Any]:
    trace = root_stage.get("reasoning_trace_internal", {})
    checklist_trace = checklist_stage.get("checklist_trace_internal", {})
    return {
        "active_domain": interpretation.get("active_domain"),
        "predicted_domain": stage_1.get("predicted_domain"),
        "top_tags": stage_1.get("top_tags", []),
        "trusted_tags": root_stage.get("case_summary", {}).get("trusted_tags", []),
        "supporting_tags": root_stage.get("case_summary", {}).get("supporting_tags", []),
        "weak_tags": root_stage.get("case_summary", {}).get("weak_tags", []),
        "primary_symptom": trace.get("primary_symptom", ""),
        "selected_reasoning_cluster": root_stage.get("selected_reasoning_cluster", ""),
        "primary_issue_family": root_stage.get("primary_issue_family", ""),
        "selected_semantic_keys": checklist_trace.get("selected_semantic_keys", []),
        "target_step_count": checklist_stage.get("target_display_count"),
        "independent_count_rule": checklist_trace.get("independent_count_rule", ""),
    }


def build_expert_analysis(root_stage: dict, checklist_stage: dict, hypothesis_details: List[Dict[str, Any]]) -> Dict[str, Any]:
    case_summary = root_stage.get("case_summary", {})
    symptom_names = case_summary.get("symptom_evidence", {}).get("symptom_names", [])
    if isinstance(symptom_names, set):
        symptom_names = sorted(symptom_names)
    return {
        "reasoning_summary": root_stage.get("reasoning_summary", ""),
        "checklist_summary": checklist_stage.get("reasoning_summary", ""),
        "primary_issue_family": root_stage.get("primary_issue_family", ""),
        "selected_reasoning_cluster": root_stage.get("selected_reasoning_cluster", ""),
        "top_hypothesis": hypothesis_details[0]["title"] if hypothesis_details else "",
        "confidence_band": _confidence_label(hypothesis_details[0]["confidence"]) if hypothesis_details else "low",
        "domain": case_summary.get("domain", ""),
        "symptom_names": symptom_names,
    }


def attach_expert_result_fields(
    result: DiagnosticResultModel,
    stage_1: dict,
    interpretation: dict,
    root_stage: dict,
    checklist_stage: dict,
    enriched_stage: dict,
) -> None:
    evidence_plan = build_evidence_plan(checklist_stage, enriched_stage)
    hypothesis_details = build_hypothesis_details(root_stage, checklist_stage)
    result.evidence_plan = evidence_plan
    result.command_plan = build_command_plan(root_stage.get("case_summary", {}), evidence_plan)
    result.hypothesis_details = hypothesis_details
    result.diagnostic_trace = build_diagnostic_trace(stage_1, interpretation, root_stage, checklist_stage)
    result.expert_analysis = build_expert_analysis(root_stage, checklist_stage, hypothesis_details)


def validate_integrated_result(result: DiagnosticResultModel) -> None:
    if not result.primary_path.strip():
        raise ValueError("primary_path must not be empty.")

    if len(result.alternative_paths) > 4:
        raise ValueError("alternative_paths must contain at most 4 items.")
    if not 1 <= len(result.possible_causes) <= 6:
        raise ValueError("possible_causes must contain between 1 and 6 items.")
    if not 1 <= len(result.diagnostic_checklist) <= 6:
        raise ValueError("diagnostic_checklist must contain between 1 and 6 steps.")
    if len(result.references_summary) > 5:
        raise ValueError("references_summary must contain at most 5 items.")

    checklist_titles = [step.title.strip().lower() for step in result.diagnostic_checklist]
    if len(checklist_titles) != len(set(checklist_titles)):
        raise ValueError("diagnostic_checklist contains duplicate step titles.")


def run_existing_pipeline(payload: DiagnoseRequest) -> Dict[str, Any]:
    enriched_problem_text = payload.problem_text.strip()

    stage_1 = predict_top_3_tags(enriched_problem_text)
    stage_1_interpretation = interpret_prediction_output(
        enriched_problem_text,
        stage_1["predicted_domain"],
        stage_1["top_tags"],
        stage_1["tag_confidences"],
    )

    stage_2 = generate_root_cause_hypotheses(
        enriched_problem_text,
        to_reasoning_domain(stage_1_interpretation["active_domain"]),
        stage_1["ranked_tags"],
        stage_1_interpretation,
    )
    stage_3 = generate_diagnostic_checklist(
        enriched_problem_text,
        stage_2["case_summary"],
        stage_2,
    )
    stage_4 = attach_step_references(
        stage_2,
        stage_3["diagnostic_checklist"],
    )

    normalized_checklist = normalize_checklist(stage_4)
    normalized_references_summary = normalize_references_summary(stage_4, normalized_checklist)

    result = DiagnosticResultModel(
        engine_title=REPORT_TITLE,
        primary_path=extract_primary_path(stage_3, stage_2),
        alternative_paths=extract_alternative_paths(stage_2, stage_3),
        possible_causes=extract_possible_causes(stage_2, stage_3),
        diagnostic_checklist=normalized_checklist,
        references_summary=normalized_references_summary,
    )
    if should_include_expert_output(payload):
        attach_expert_result_fields(result, stage_1, stage_1_interpretation, stage_2, stage_3, stage_4)
    validate_integrated_result(result)

    return {
        "stage_1": stage_1,
        "stage_1_interpretation": stage_1_interpretation,
        "stage_2": stage_2,
        "stage_3": stage_3,
        "stage_4": stage_4,
        "result": result,
    }

__all__ = [
    "build_enriched_problem_text",
    "extract_primary_path",
    "extract_alternative_paths",
    "extract_possible_causes",
    "normalize_checklist",
    "normalize_references_summary",
    "should_include_expert_output",
    "build_hypothesis_details",
    "build_evidence_plan",
    "build_command_plan",
    "build_diagnostic_trace",
    "build_expert_analysis",
    "attach_expert_result_fields",
    "validate_integrated_result",
    "run_existing_pipeline",
]
