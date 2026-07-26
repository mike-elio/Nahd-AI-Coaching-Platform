from typing import Any, Dict, List

from app.services.action_plan import build_public_action_plan

DISPLAY_LEVEL_ALIASES = {
    "basic": "basic",
    "simple": "basic",
    "beginner": "basic",
    "standard": "standard",
    "guided": "standard",
    "intermediate": "standard",
    "expert": "expert",
    "professional": "expert",
}


PUBLIC_DOMAIN_ALIASES = {
    "sw": "software",
    "software": "software",
    "cn": "networking",
    "networking": "networking",
    "ai": "ai",
}


DISPLAY_LIMITS = {
    "basic": {
        "low": {"steps": 1, "causes": 1, "references": 0, "alternatives": 0},
        "medium": {"steps": 2, "causes": 1, "references": 0, "alternatives": 0},
        "high": {"steps": 3, "causes": 1, "references": 0, "alternatives": 0},
    },
    "standard": {
        "low": {"steps": 3, "causes": 2, "references": 1, "alternatives": 0},
        "medium": {"steps": 4, "causes": 3, "references": 2, "alternatives": 0},
        "high": {"steps": 5, "causes": 4, "references": 3, "alternatives": 0},
    },
    "expert": {
        "low": {"steps": 4, "causes": 3, "references": 2, "alternatives": 1},
        "medium": {"steps": 5, "causes": 4, "references": 3, "alternatives": 2},
        "high": {"steps": 7, "causes": 6, "references": 5, "alternatives": 4},
    },
}

DOMAIN_COMPLEXITY_TERMS = {
    "ai": {"gpu", "cuda", "model", "tensor", "rag", "embedding", "inference", "serving"},
    "networking": {"kubernetes", "ingress", "proxy", "dns", "tls", "routing"},
    "software": {"auth", "jwt", "cors", "database", "django", "fastapi", "postgresql"},
}


def normalize_display_level(value: str | None) -> str:
    cleaned = _safe_text(value).lower()
    return DISPLAY_LEVEL_ALIASES.get(cleaned, "standard")


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _to_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    if hasattr(value, "dict"):
        return value.dict()
    return {}


def _clean_list(values: object, limit: int | None = None) -> list:
    if values is None:
        return []

    if isinstance(values, (str, bytes)):
        raw_items = [values]
    elif isinstance(values, set):
        raw_items = sorted(values)
    elif isinstance(values, tuple):
        raw_items = list(values)
    elif isinstance(values, list):
        raw_items = values
    else:
        raw_items = []

    cleaned: List[Any] = []
    for item in raw_items:
        if isinstance(item, dict) or hasattr(item, "model_dump") or hasattr(item, "dict"):
            item_dict = {
                key: value
                for key, value in _to_dict(item).items()
                if value not in (None, "", [], {})
            }
            if item_dict:
                cleaned.append(item_dict)
            continue

        item_text = _safe_text(item)
        if item_text:
            cleaned.append(item_text)

        if limit is not None and len(cleaned) >= limit:
            break

    return cleaned[:limit] if limit is not None else cleaned


def _unique_items(values: object, limit: int | None = None) -> list:
    items = _clean_list(values)
    unique: List[Any] = []
    seen = set()
    for item in items:
        key = repr(item)
        if key in seen:
            continue
        unique.append(item)
        seen.add(key)
        if limit is not None and len(unique) >= limit:
            break
    return unique


def _reference(reference: Any) -> Dict[str, Any]:
    reference_dict = _to_dict(reference)
    return {
        key: _safe_text(reference_dict.get(key))
        for key in ("title", "url", "source_type")
        if _safe_text(reference_dict.get(key))
    }


def _compact_step(step: dict, rank: int) -> dict:
    step_dict = _to_dict(step)
    compact = {
        "step_number": step_dict.get("step_number") or step_dict.get("step") or rank,
        "title": _safe_text(step_dict.get("title")),
        "action": _safe_text(step_dict.get("action")),
        "expected": _safe_text(step_dict.get("expected") or step_dict.get("expected_result")),
        "if_this_fails": _safe_text(step_dict.get("if_this_fails") or step_dict.get("if_failed")),
    }
    reference = _reference(step_dict.get("reference"))
    if reference:
        compact["reference"] = reference
    return {key: value for key, value in compact.items() if value not in (None, "", [], {})}


def _basic_step(step: dict, rank: int) -> dict:
    step_dict = _to_dict(step)
    return {
        "rank": rank,
        "title": _safe_text(step_dict.get("title")),
        "action": _safe_text(step_dict.get("action")),
        "expected": _safe_text(step_dict.get("expected") or step_dict.get("expected_result")),
        "if_this_fails": _safe_text(step_dict.get("if_this_fails") or step_dict.get("if_failed")),
    }


def _expert_step(step: dict, rank: int) -> dict:
    step_dict = _to_dict(step)
    expert = _compact_step(step_dict, rank)
    expert["rank"] = rank
    return expert


def _result_dict(result: Any) -> Dict[str, Any]:
    return _to_dict(result)


def _summary(result_data: Dict[str, Any]) -> str:
    primary_path = _safe_text(result_data.get("primary_path")) or "Primary diagnostic path"
    checklist = _clean_list(result_data.get("diagnostic_checklist"), limit=1)
    if checklist and isinstance(checklist[0], dict):
        first_title = _safe_text(checklist[0].get("title"))
        primary_key = primary_path.lower()
        first_key = first_title.lower()
        if first_title and first_key not in primary_key and primary_key not in first_key:
            return f"The strongest evidence points to {primary_path.lower()}. Start with: {first_title}."
    return f"The strongest evidence points to {primary_path.lower()}."


def _combined_checklist_text(checklist: list) -> str:
    parts: List[str] = []
    for step in checklist:
        step_dict = _to_dict(step)
        parts.extend(
            [
                _safe_text(step_dict.get("title")),
                _safe_text(step_dict.get("action")),
                _safe_text(step_dict.get("expected") or step_dict.get("expected_result")),
                _safe_text(step_dict.get("if_this_fails") or step_dict.get("if_failed")),
            ]
        )
    return " ".join(item for item in parts if item).lower()


def _case_summary_from_context(context: dict) -> dict:
    stage_2 = context.get("stage_2") or {}
    interpretation = context.get("stage_1_interpretation") or {}
    case_summary = stage_2.get("case_summary", {}) if isinstance(stage_2, dict) else {}
    if case_summary:
        return case_summary
    interpretation_summary = interpretation.get("case_summary", {}) if isinstance(interpretation, dict) else {}
    return interpretation_summary if isinstance(interpretation_summary, dict) else {}


def _public_domain(context: dict) -> str:
    stage_1 = context.get("stage_1") or {}
    interpretation = context.get("stage_1_interpretation") or {}
    stage_2 = context.get("stage_2") or {}

    interpretation_summary = interpretation.get("case_summary", {}) if isinstance(interpretation, dict) else {}
    case_summary = stage_2.get("case_summary", {}) if isinstance(stage_2, dict) else {}
    raw_domain = _first_present(
        interpretation_summary.get("domain") if isinstance(interpretation_summary, dict) else None,
        case_summary.get("domain") if isinstance(case_summary, dict) else None,
        stage_1.get("domain") if isinstance(stage_1, dict) else None,
        stage_1.get("predicted_domain") if isinstance(stage_1, dict) else None,
        interpretation.get("active_domain") if isinstance(interpretation, dict) else None,
        interpretation.get("predicted_domain") if isinstance(interpretation, dict) else None,
    )
    return PUBLIC_DOMAIN_ALIASES.get(_safe_text(raw_domain).lower(), "software")


def estimate_display_complexity(result: dict, context: dict) -> str:
    result_data = _result_dict(result)
    checklist = _unique_items(result_data.get("diagnostic_checklist"))
    possible_causes = _unique_items(result_data.get("possible_causes"))
    alternative_paths = _unique_items(result_data.get("alternative_paths"))
    domain = _public_domain(context)
    case_summary = _case_summary_from_context(context)
    symptom_evidence = case_summary.get("symptom_evidence", {}) if isinstance(case_summary, dict) else {}

    score = 0
    if len(possible_causes) >= 4:
        score += 1
    if len(alternative_paths) >= 3:
        score += 1
    if len(checklist) >= 5:
        score += 1

    combined_text = f"{_safe_text(result_data.get('primary_path'))} {_combined_checklist_text(checklist)}"
    if domain in DOMAIN_COMPLEXITY_TERMS and any(term in combined_text for term in DOMAIN_COMPLEXITY_TERMS[domain]):
        score += 1

    trusted_tags = _clean_list(case_summary.get("trusted_tags", []) if isinstance(case_summary, dict) else [])
    supporting_tags = _clean_list(case_summary.get("supporting_tags", []) if isinstance(case_summary, dict) else [])
    tag_signals = _clean_list(case_summary.get("tag_signals", []) if isinstance(case_summary, dict) else [])
    if len(trusted_tags) + len(supporting_tags) >= 3 or len(tag_signals) >= 3:
        score += 1

    symptom_names = []
    if isinstance(symptom_evidence, dict):
        symptom_names = _clean_list(symptom_evidence.get("symptom_names", []))
    if len(symptom_names) > 1:
        score += 1

    if not any([possible_causes, alternative_paths, checklist, combined_text.strip(), trusted_tags, supporting_tags, tag_signals, symptom_names]):
        return "medium"
    if score <= 2:
        return "low"
    if score <= 5:
        return "medium"
    return "high"


def get_display_limits(level: str, complexity: str, available: dict) -> dict:
    base_limits = DISPLAY_LIMITS.get(level, DISPLAY_LIMITS["standard"]).get(
        complexity,
        DISPLAY_LIMITS.get(level, DISPLAY_LIMITS["standard"])["medium"],
    )
    limits: Dict[str, int] = {}
    for key, value in base_limits.items():
        try:
            available_count = int(available.get(key, 0))
        except Exception:
            available_count = 0
        limits[key] = min(value, max(available_count, 0))
    return limits


def _available_counts(result_data: Dict[str, Any]) -> dict:
    return {
        "steps": len(_unique_items(result_data.get("diagnostic_checklist"))),
        "causes": len(_unique_items(result_data.get("possible_causes"))),
        "references": len(_unique_items(result_data.get("references_summary"))),
        "alternatives": len(_unique_items(result_data.get("alternative_paths"))),
    }


def build_basic_display(result: dict, context: dict) -> dict:
    result_data = _result_dict(result)
    complexity = estimate_display_complexity(result_data, context)
    limits = get_display_limits("basic", complexity, _available_counts(result_data))
    checklist = _unique_items(result_data.get("diagnostic_checklist"), limit=limits["steps"])
    possible_causes = _unique_items(result_data.get("possible_causes"), limit=limits["causes"])
    primary_path = _safe_text(result_data.get("primary_path"))
    display = {
        "domain": _public_domain(context),
        "summary": _summary(result_data),
        "most_likely_issue": possible_causes[0] if possible_causes else primary_path,
        "start_here": [
            _basic_step(step, index)
            for index, step in enumerate(checklist, start=1)
            if isinstance(step, dict)
        ],
    }
    action_plan = build_public_action_plan(result_data, context, "basic", complexity)
    if action_plan:
        display["action_plan"] = action_plan
    return display


def build_standard_display(result: dict, context: dict) -> dict:
    result_data = _result_dict(result)
    complexity = estimate_display_complexity(result_data, context)
    limits = get_display_limits("standard", complexity, _available_counts(result_data))
    checklist = _unique_items(result_data.get("diagnostic_checklist"), limit=limits["steps"])
    display = {
        "domain": _public_domain(context),
        "summary": _summary(result_data),
        "primary_path": _safe_text(result_data.get("primary_path")),
        "possible_causes": _unique_items(result_data.get("possible_causes"), limit=limits["causes"]),
        "diagnostic_checklist": [
            _compact_step(step, index)
            for index, step in enumerate(checklist, start=1)
            if isinstance(step, dict)
        ],
        "references_summary": _unique_items(result_data.get("references_summary"), limit=limits["references"]),
    }
    action_plan = build_public_action_plan(result_data, context, "standard", complexity)
    if action_plan:
        display["action_plan"] = action_plan
    return display


def build_expert_display(result: dict, context: dict) -> dict:
    result_data = _result_dict(result)
    complexity = estimate_display_complexity(result_data, context)
    limits = get_display_limits("expert", complexity, _available_counts(result_data))
    checklist = _unique_items(result_data.get("diagnostic_checklist"), limit=limits["steps"])
    display = {
        "domain": _public_domain(context),
        "summary": _summary(result_data),
        "primary_path": _safe_text(result_data.get("primary_path")),
        "alternative_paths": _unique_items(result_data.get("alternative_paths"), limit=limits["alternatives"]),
        "possible_causes": _unique_items(result_data.get("possible_causes"), limit=limits["causes"]),
        "diagnostic_checklist": [
            _expert_step(step, index)
            for index, step in enumerate(checklist, start=1)
            if isinstance(step, dict)
        ],
        "references_summary": _unique_items(result_data.get("references_summary"), limit=limits["references"]),
    }
    action_plan = build_public_action_plan(result_data, context, "expert", complexity)
    if action_plan:
        display["action_plan"] = action_plan
    return display


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def build_debug_diagnostics(context: dict) -> dict:
    interpretation = context.get("stage_1_interpretation") or {}
    stage_2 = context.get("stage_2") or {}
    stage_3 = context.get("stage_3") or {}
    case_summary = stage_2.get("case_summary", {}) if isinstance(stage_2, dict) else {}
    symptom_evidence = case_summary.get("symptom_evidence", {}) if isinstance(case_summary, dict) else {}
    reasoning_trace = stage_2.get("reasoning_trace_internal", {}) if isinstance(stage_2, dict) else {}

    diagnostics = {
        "selected_family": _first_present(
            stage_2.get("primary_issue_family"),
            case_summary.get("primary_issue_family"),
            case_summary.get("issue_family"),
        ),
        "selected_cluster": _first_present(
            stage_2.get("selected_reasoning_cluster"),
            interpretation.get("selected_cluster"),
            case_summary.get("selected_cluster"),
        ),
        "primary_symptom": _first_present(
            reasoning_trace.get("primary_symptom") if isinstance(reasoning_trace, dict) else None,
            symptom_evidence.get("primary_symptom") if isinstance(symptom_evidence, dict) else None,
        ),
        "trusted_tags": case_summary.get("trusted_tags", []),
        "supporting_tags": case_summary.get("supporting_tags", []),
        "boundary_confidence": _first_present(
            case_summary.get("boundary_confidence"),
            stage_3.get("boundary_confidence") if isinstance(stage_3, dict) else None,
        ),
        "stage_keys": [key for key in ("stage_1", "stage_1_interpretation", "stage_2", "stage_3", "stage_4") if key in context],
    }

    compact: Dict[str, Any] = {}
    for key, value in diagnostics.items():
        if key in {"trusted_tags", "supporting_tags", "stage_keys"}:
            compact[key] = _clean_list(value)
            continue
        cleaned_value = _safe_text(value)
        if cleaned_value:
            compact[key] = cleaned_value
    return compact


_PRIVATE_DISPLAY_KEYS = frozenset({"level", "complexity"})


def _strip_private_keys(display: dict) -> dict:
    return {key: value for key, value in display.items() if key not in _PRIVATE_DISPLAY_KEYS}


def adapt_result_for_display(
    result: Any,
    context: dict,
    display_level: str | None,
    debug_mode: bool,
) -> Any:
    level = normalize_display_level(display_level)
    builders = {
        "basic": build_basic_display,
        "standard": build_standard_display,
        "expert": build_expert_display,
    }
    raw_display = builders[level](result, context)
    display_result = _strip_private_keys(raw_display)
    if debug_mode:
        display_result["debug_diagnostics"] = build_debug_diagnostics(context)
    return display_result


__all__ = [
    "normalize_display_level",
    "_safe_text",
    "_clean_list",
    "_compact_step",
    "_basic_step",
    "_expert_step",
    "estimate_display_complexity",
    "get_display_limits",
    "build_basic_display",
    "build_standard_display",
    "build_expert_display",
    "build_debug_diagnostics",
    "adapt_result_for_display",
]
