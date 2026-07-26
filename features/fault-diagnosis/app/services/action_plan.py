from typing import Any, Dict, List


DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
VALUE_ORDER = {"high": 0, "medium": 1, "low": 2}

ACTION_PLAN_LIMITS = {
    "basic": {"low": 2, "medium": 3, "high": 3},
    "standard": {"low": 3, "medium": 4, "high": 5},
    "expert": {"low": 4, "medium": 5, "high": 7},
}

EASY_TERMS = {
    "check",
    "compare",
    "confirm",
    "inspect",
    "log",
    "replay",
    "resolve",
    "review",
    "trace",
}
HARD_TERMS = {
    "change",
    "correct",
    "deploy",
    "fix",
    "migrate",
    "restart",
    "rewrite",
    "rotate",
    "rollback",
}
LOW_RISK_TERMS = {
    "check",
    "compare",
    "confirm",
    "inspect",
    "log",
    "replay",
    "resolve",
    "review",
    "trace",
}
HIGH_RISK_TERMS = {
    "change",
    "correct",
    "delete",
    "deploy",
    "drop",
    "fix",
    "migrate",
    "restart",
    "rotate",
    "rollback",
}
DIRECT_CHECK_TERMS = {
    "api base url",
    "authorization",
    "browser request",
    "cors",
    "cuda",
    "dns",
    "embedding",
    "environment variable",
    "endpoint",
    "hostname",
    "jwt",
    "origin",
    "preflight",
    "service",
    "shape",
    "tensor",
}
CLOSURE_TERMS = {
    "after correcting",
    "broadening",
    "closure",
    "deployment change",
    "fix that",
    "no longer reproduces",
    "retest",
    "rollback",
    "unrelated",
}


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


def _clean_step(step: dict, fallback_rank: int) -> Dict[str, Any]:
    step_dict = _to_dict(step)
    return {
        "source_rank": int(step_dict.get("step_number") or step_dict.get("step") or fallback_rank),
        "semantic_key": _safe_text(step_dict.get("semantic_key")),
        "title": _safe_text(step_dict.get("title")),
        "action": _safe_text(step_dict.get("action")),
        "expected": _safe_text(step_dict.get("expected") or step_dict.get("expected_result")),
        "if_this_fails": _safe_text(step_dict.get("if_this_fails") or step_dict.get("if_failed")),
        "path_kind": _safe_text(step_dict.get("path_kind")).lower(),
        "phase": _safe_text(step_dict.get("phase")).lower(),
    }


def _step_text(step: dict) -> str:
    step_dict = _to_dict(step)
    return " ".join(
        _safe_text(step_dict.get(key))
        for key in ("title", "action", "expected", "if_this_fails", "if_failed", "semantic_key", "phase")
    ).lower()


def _step_action_text(step: dict) -> str:
    step_dict = _to_dict(step)
    return " ".join(
        _safe_text(step_dict.get(key))
        for key in ("title", "action", "semantic_key", "phase")
    ).lower()


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def classify_action_difficulty(step: dict) -> str:
    text = _step_action_text(step)
    if _contains_any(text, HARD_TERMS):
        return "hard"
    if _contains_any(text, EASY_TERMS):
        return "easy"
    if any(term in text for term in ("validate", "verify", "test", "walk")):
        return "medium"
    return "medium"


def classify_action_risk(step: dict) -> str:
    text = _step_action_text(step)
    if _contains_any(text, HIGH_RISK_TERMS):
        return "high"
    if _contains_any(text, LOW_RISK_TERMS):
        return "low"
    if any(term in text for term in ("update", "configure", "policy", "secret")):
        return "medium"
    return "medium"


def estimate_action_expected_value(step: dict, result: dict, context: dict) -> str:
    step_dict = _to_dict(step)
    result_dict = _to_dict(result)
    text = _step_text(step_dict)
    primary_path = _safe_text(result_dict.get("primary_path")).lower()
    semantic_key = _safe_text(step_dict.get("semantic_key")).lower()

    if step_dict.get("path_kind") == "primary":
        return "high"
    if primary_path and any(token and token in text for token in primary_path.split()):
        return "high"
    if semantic_key and any(token and token in text for token in semantic_key.replace("_", " ").split()):
        return "high"
    if _contains_any(text, DIRECT_CHECK_TERMS):
        return "high"

    stage_2 = context.get("stage_2") or {}
    case_summary = stage_2.get("case_summary", {}) if isinstance(stage_2, dict) else {}
    tags = []
    if isinstance(case_summary, dict):
        for key in ("trusted_tags", "supporting_tags", "tag_signals"):
            raw_values = case_summary.get(key, [])
            if isinstance(raw_values, list):
                tags.extend(_safe_text(item).lower() for item in raw_values)
    if any(tag and tag in text for tag in tags):
        return "medium"
    if _contains_any(text, CLOSURE_TERMS):
        return "low"
    return "medium"


def _priority(rank: int, expected_value: str) -> str:
    if rank == 1 or expected_value == "high":
        return "start_here"
    if rank <= 3:
        return "next"
    return "deeper_check"


def _private_rank_key(item: dict) -> tuple:
    text = f"{item['title']} {item['action']} {item['expected']} {item['if_this_fails']}".lower()
    direct_bonus = -1 if _contains_any(text, DIRECT_CHECK_TERMS) else 0
    closure_penalty = 1 if _contains_any(text, CLOSURE_TERMS) else 0
    primary_bonus = -1 if item.get("path_kind") == "primary" else 0
    return (
        VALUE_ORDER[item["expected_value"]],
        DIFFICULTY_ORDER[item["difficulty"]],
        RISK_ORDER[item["risk"]],
        primary_bonus,
        direct_bonus,
        closure_penalty,
        item["source_rank"],
    )


def build_ranked_action_plan(result: dict, context: dict, level: str, complexity: str) -> List[dict]:
    result_dict = _to_dict(result)
    raw_steps = result_dict.get("diagnostic_checklist", [])
    if not isinstance(raw_steps, list):
        return []

    ranked_items: List[dict] = []
    seen = set()
    for index, raw_step in enumerate(raw_steps, start=1):
        step = _clean_step(raw_step, index)
        if not step["title"] or not step["action"]:
            continue
        dedupe_key = (step["title"].lower(), step["action"].lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        difficulty = classify_action_difficulty(step)
        risk = classify_action_risk(step)
        expected_value = estimate_action_expected_value(step, result_dict, context)
        ranked_items.append(
            {
                "source_rank": step["source_rank"],
                "path_kind": step["path_kind"],
                "difficulty": difficulty,
                "risk": risk,
                "expected_value": expected_value,
                "title": step["title"],
                "action": step["action"],
                "expected": step["expected"],
                "if_this_fails": step["if_this_fails"],
            }
        )

    ranked_items.sort(key=_private_rank_key)
    limit = ACTION_PLAN_LIMITS.get(level, {}).get(complexity, 0)
    selected = ranked_items[: min(limit, len(ranked_items))]

    action_plan: List[dict] = []
    for rank, item in enumerate(selected, start=1):
        action_plan.append(
            {
                "rank": rank,
                "priority": _priority(rank, item["expected_value"]),
                "difficulty": item["difficulty"],
                "risk": item["risk"],
                "expected_value": item["expected_value"],
                "title": item["title"],
                "action": item["action"],
                "expected": item["expected"],
                "if_this_fails": item["if_this_fails"],
            }
        )
    return action_plan


_PUBLIC_ACTION_KEYS = frozenset({"rank", "title", "action", "expected", "if_this_fails", "reference"})


def build_public_action_plan(result: dict, context: dict, level: str, complexity: str) -> List[dict]:
    """Build a public-safe action plan by stripping internal scoring fields.

    Keeps only: rank, title, action, expected, if_this_fails, reference.
    Strips: priority, difficulty, risk, expected_value, score, path_kind,
    source_rank, and any other internal metadata.
    """
    ranked = build_ranked_action_plan(result, context, level, complexity)
    public_items: List[dict] = []
    for item in ranked:
        public_item = {
            key: value
            for key, value in item.items()
            if key in _PUBLIC_ACTION_KEYS and value not in (None, "", [], {})
        }
        if public_item.get("title") and public_item.get("action"):
            public_items.append(public_item)
    return public_items


__all__ = [
    "classify_action_difficulty",
    "classify_action_risk",
    "estimate_action_expected_value",
    "build_ranked_action_plan",
    "build_public_action_plan",
]
