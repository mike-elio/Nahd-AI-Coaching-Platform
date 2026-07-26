"""Build concise GPES gap resolution output."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BANK_PATH = _PROJECT_ROOT / "knowledge_base" / "gap_resolution_bank.json"

_FACT_TO_BANK_GAP = {
    fact: gap
    for gap, facts in {
        "limited_hours": ("hours_per_week", "pressure_load"),
        "weak_device": ("weak_device", "weak_internet"),
        "weak_programming_basics": ("programming_basic", "basics_control_flow", "problem_solving"),
        "weak_python_skill": ("python_skill", "python_skill_basic", "any_programming_experience"),
        "weak_math_skill": ("math_skill",),
        "weak_ai_readiness": ("ml_exposure", "data_handling"),
        "weak_frontend_readiness": (
            "js_skill",
            "web_basics",
            "dom_events",
            "http_client_basics",
            "ui_accessibility",
        ),
        "weak_backend_readiness": (
            "api_concepts",
            "backend_testing",
            "sql_skill",
            "db_modeling_skill",
            "input_validation",
            "data_pipeline_basics",
            "data_quality_awareness",
            "containers_basics",
            "ci_basics",
            "cloud_basics",
            "security_mindset",
            "owasp_awareness",
            "secure_coding",
            "networking_theory",
            "networking_basic",
            "osi_layers_basic",
            "ip_subnetting_basic",
            "lab_access",
            "cisco_tools",
            "linux_skill",
            "linux_cli_net_tools_skill",
            "scripting_skill",
        ),
    }.items()
    for fact in facts
}

_GOAL_TRACK_ALIASES = {
    "Backend Development Foundations": "Backend Development",
    "Frontend Development Foundations": "Frontend Development",
    "DevOps & Cloud Engineering": "DevOps Foundations",
    "Application Security": "Cybersecurity Foundations",
    "Data Engineering": "Database Foundations",
    "CCNA Network Operations": "Networking Foundations",
    "Network Security": "Cybersecurity Foundations",
    "Wireless & RF Engineering": "Networking Foundations",
    "Cloud Networking": "Cloud Foundations",
    "IoT & Edge Networking": "Networking Foundations",
    "Computer Vision": "Machine Learning Engineering",
    "Natural Language Processing": "Machine Learning Engineering",
    "AI Data Engineering": "Machine Learning Engineering",
    "AI Research": "Machine Learning Engineering",
}


_FACT_TITLES = {
    fact: title
    for title, facts in {
        "Weekly study time": ("hours_per_week", "pressure_load"),
        "Tooling setup": ("weak_device", "weak_internet"),
        "Programming basics": ("programming_basic", "basics_control_flow", "problem_solving"),
        "Python basics": ("python_skill_basic", "any_programming_experience", "python_skill"),
        "API practice": ("api_concepts", "backend_testing", "db_modeling_skill", "input_validation"),
        "Git workflow": ("version_control_git",),
        "Frontend basics": ("web_basics", "js_skill", "dom_events", "http_client_basics", "ui_accessibility"),
        "Math foundations": ("math_skill",),
        "Lightweight AI practice": ("ml_exposure", "data_handling"),
        "Networking basics": ("networking_basic", "networking_theory", "osi_layers_basic", "ip_subnetting_basic"),
        "Lab practice": ("lab_access", "cisco_tools"),
        "Linux tools": ("linux_cli_net_tools_skill", "linux_skill", "scripting_skill"),
    }.items()
    for fact in facts
}


# يحول صفوف الإجراءات الاحتياطية إلى عناصر خطة.
def _fallback_items(*rows: tuple[str, str]) -> list[dict[str, str]]:
    return [{"title": title, "action": action} for title, action in rows]


_FALLBACK_ACTIONS = {
    "software": _fallback_items(
        ("Programming basics", "Practice variables, conditions, loops, functions, and small coding tasks."),
        ("API practice", "Build a small CRUD API with validation and database storage."),
        ("Git workflow", "Save each exercise or small project in a Git repository."),
    ),
    "ai": _fallback_items(
        ("Python basics", "Practice Python fundamentals with small coding exercises."),
        ("Math foundations", "Review algebra, probability, and basic statistics."),
        ("Lightweight AI practice", "Start with simple notebooks before advanced model training."),
    ),
    "networking": _fallback_items(
        ("Networking basics", "Review OSI, TCP/IP, subnetting, and basic troubleshooting."),
        ("Lab practice", "Use simulators or guided labs to practice network scenarios."),
        ("Linux tools", "Practice basic terminal and network diagnostic commands."),
    ),
}

_DEFAULT_BANK_FACTS = {
    "software": ("programming_basic", "api_concepts", "version_control_git"),
    "ai": ("python_skill", "math_skill", "ml_exposure"),
    "networking": ("networking_theory", "lab_access", "linux_cli_net_tools_skill"),
}


# يبني خطة قصيرة لمعالجة الفجوات للهدف المختار.
def build_gap_resolution_plan(
    gaps: list[dict[str, Any]] | list[Any],
    top_goal: dict[str, Any] | None,
    normalized_facts: dict[str, Any],
) -> list[dict[str, str]]:
    selected_track = normalize_selected_track(top_goal)
    plan: list[dict[str, str]] = []
    seen_titles: set[str] = set()
    seen_actions: set[str] = set()
    seen_facts: set[str] = set()

    for gap in gaps:
        if not isinstance(gap, dict) or not gap.get("fact"):
            continue
        fact = str(gap["fact"])
        title = _title_for_gap(fact, top_goal)
        if fact in seen_facts or title.casefold() in seen_titles:
            continue
        action = _action_for_gap(selected_track, fact, gap, normalized_facts)
        if action.casefold() in seen_actions:
            action = str(gap.get("step_text") or _fallback_action_for_title(title))
        _append_item(plan, seen_titles, seen_actions, {"title": title, "action": action})
        seen_facts.add(fact)
        if len(plan) >= 4:
            return plan[:4]

    _append_default_bank_items(plan, seen_titles, seen_actions, selected_track, top_goal, normalized_facts)

    for fallback in _fallback_actions_for_goal(top_goal):
        if len(plan) >= 2:
            break
        _append_item(plan, seen_titles, seen_actions, fallback)

    return plan[:4]


@lru_cache(maxsize=1)
# يحمل بنك الإجراءات من JSON ويخزنه مؤقتًا.
def load_gap_resolution_bank() -> list[dict[str, Any]]:
    data = json.loads(_BANK_PATH.read_text(encoding="utf-8"))
    return list(data.get("actions", []))


# يصنف وقت الدراسة الأسبوعي لاختيار إجراء مناسب.
def infer_time_profile(hours_per_week: int | float | None) -> str:
    if hours_per_week is None:
        return "normal"
    try:
        hours = float(hours_per_week)
    except (TypeError, ValueError):
        return "normal"
    if hours < 8:
        return "limited"
    if hours <= 20:
        return "normal"
    return "intensive"


# يصنف حالة الجهاز لاختيار إجراء مناسب.
def infer_device_profile(facts: dict[str, Any]) -> str:
    return "weak" if facts.get("weak_device") is True else "normal"


# يحسب مدى مناسبة إجراء من البنك للسياق الحالي.
def score_action_match(action: dict[str, Any], context: dict[str, Any]) -> int:
    score = 0

    if action.get("track") == context["selected_track"]:
        score -= 100
    elif action.get("track") == "any":
        score -= 20
    else:
        score += 1000

    if action.get("gap") == context["detected_gap"]:
        score -= 100
    else:
        score += 1000

    score += _field_score(action.get("level"), context.get("user_level"), exact_bonus=20)
    score += _field_score(action.get("time_profile"), context.get("time_profile"), exact_bonus=16)
    score += _field_score(action.get("device_profile"), context.get("device_profile"), exact_bonus=16)
    score += _field_score(action.get("target_outcome"), context.get("target_outcome"), exact_bonus=18)
    score += int(action.get("priority", 99)) * 10
    return score


# يختار إجراءات عملية من البنك للفجوات المكتشفة.
def select_gap_resolution_actions(
    selected_track: str,
    detected_gaps: list[str],
    facts: dict[str, Any],
    max_items: int = 3,
    allow_generated_fallback: bool = True,
) -> list[dict[str, str]]:
    bank = load_gap_resolution_bank()
    user_level = _normalize_level(facts.get("current_level") or facts.get("user_level"))
    time_profile = infer_time_profile(facts.get("hours_per_week"))
    device_profile = infer_device_profile(facts)
    target_outcome = _normalize_target_outcome(facts.get("target_outcome"))
    normalized_gaps = _normalize_detected_gaps(detected_gaps)

    if not normalized_gaps:
        normalized_gaps = ["internship_goal"]
        selected_track = "any"

    selected: list[dict[str, str]] = []
    used_actions: set[str] = set()

    for gap in normalized_gaps:
        if len(selected) >= max_items:
            break

        context = {
            "selected_track": selected_track,
            "detected_gap": gap,
            "user_level": user_level,
            "time_profile": time_profile,
            "device_profile": device_profile,
            "target_outcome": target_outcome,
        }
        action = _best_action_for_gap(bank, context, used_actions)
        if not action and not allow_generated_fallback:
            continue
        item = _action_item(action) if action else _generated_fallback(selected_track, gap)
        if item["action"] in used_actions:
            continue
        selected.append(item)
        used_actions.add(item["action"])

    return selected[:max_items]


# يوحد اسم الهدف ليتوافق مع أسماء المسارات في البنك.
def normalize_selected_track(top_goal: dict[str, Any] | None) -> str:
    if not top_goal:
        return "any"
    goal_name = str(top_goal.get("goal_name") or top_goal.get("track") or "").strip()
    if goal_name.endswith(" Track"):
        goal_name = goal_name.removesuffix(" Track")
    return _GOAL_TRACK_ALIASES.get(goal_name, goal_name or "any")


# يختار عنوان الفجوة الذي سيظهر للمستخدم.
def _title_for_gap(fact: str, top_goal: dict[str, Any] | None) -> str:
    if fact == "python_skill_basic" and _goal_family(top_goal) != "ai":
        return "Programming basics"
    return _FACT_TITLES.get(fact, "Focused practice")


# يحول فجوة واحدة إلى جملة إجراء عملية.
def _action_for_gap(
    selected_track: str,
    fact: str,
    gap: dict[str, Any],
    normalized_facts: dict[str, Any],
) -> str:
    selected = select_gap_resolution_actions(
        selected_track,
        [fact],
        normalized_facts,
        max_items=1,
    )
    if selected:
        return selected[0]["action"]
    return str(gap.get("step_text") or "Complete one focused practice task for this gap.")


# يرجع الإجراءات الاحتياطية الداخلية حسب مجال الهدف.
def _fallback_actions_for_goal(top_goal: dict[str, Any] | None) -> list[dict[str, str]]:
    return _FALLBACK_ACTIONS[_goal_family(top_goal)]


# يملأ الخطة بإجراءات افتراضية من البنك عند نقص العناصر.
def _append_default_bank_items(
    plan: list[dict[str, str]],
    seen_titles: set[str],
    seen_actions: set[str],
    selected_track: str,
    top_goal: dict[str, Any] | None,
    normalized_facts: dict[str, Any],
) -> None:
    for fact in _DEFAULT_BANK_FACTS[_goal_family(top_goal)]:
        if len(plan) >= 2:
            return
        selected = select_gap_resolution_actions(
            selected_track,
            [fact],
            normalized_facts,
            max_items=1,
            allow_generated_fallback=False,
        )
        if selected:
            _append_item(
                plan,
                seen_titles,
                seen_actions,
                {"title": _title_for_gap(fact, top_goal), "action": selected[0]["action"]},
            )


# يبحث عن إجراء احتياطي يطابق عنوانًا موجودًا.
def _fallback_action_for_title(title: str) -> str:
    for actions in _FALLBACK_ACTIONS.values():
        for item in actions:
            if item["title"].casefold() == title.casefold():
                return item["action"]
    return "Complete one focused practice task for this gap."


# يستنتج المجال العام للهدف لاختيار الاحتياط المناسب.
def _goal_family(top_goal: dict[str, Any] | None) -> str:
    text = " ".join(
        str((top_goal or {}).get(key, ""))
        for key in ("goal_id", "goal_name", "domain")
    ).casefold()
    if any(token in text for token in ("aie", " ai", "machine learning", "computer vision", "natural language")):
        return "ai"
    if any(token in text for token in ("cne", "network", "ccna", "wireless")):
        return "networking"
    return "software"


# يضيف عنصرًا للخطة مع منع تكرار العناوين والإجراءات.
def _append_item(
    plan: list[dict[str, str]],
    seen_titles: set[str],
    seen_actions: set[str],
    item: dict[str, str],
) -> None:
    title = item["title"].strip()
    action = item["action"].strip()
    action_key = action.casefold()
    if not title or not action or title.casefold() in seen_titles or action_key in seen_actions:
        return
    plan.append({"title": title, "action": action})
    seen_titles.add(title.casefold())
    seen_actions.add(action_key)


# يقيّم حقلًا اختياريًا من البنك مقابل قيمة السياق.
def _field_score(value: Any, target: str, *, exact_bonus: int) -> int:
    if value == target:
        return -exact_bonus
    if value == "any":
        return 0
    return 8


# يختار أفضل إجراء متاح من البنك لفجوة موحدة.
def _best_action_for_gap(
    bank: list[dict[str, Any]],
    context: dict[str, Any],
    used_actions: set[str],
) -> dict[str, Any] | None:
    gap_matches = [
        action
        for action in bank
        if action.get("gap") == context["detected_gap"]
        and action.get("action") not in used_actions
    ]
    if not gap_matches:
        return None

    exact_track_matches = [
        action for action in gap_matches if action.get("track") == context["selected_track"]
    ]
    if exact_track_matches:
        candidates = exact_track_matches
    else:
        candidates = [action for action in gap_matches if action.get("track") == "any"]

    if not candidates:
        candidates = gap_matches
    return min(candidates, key=lambda action: score_action_match(action, context))


# يحول سجل إجراء من البنك إلى شكل عنصر الخطة النهائي.
def _action_item(action: dict[str, Any]) -> dict[str, str]:
    return {
        "action": str(action["action"]),
        "reason": str(action["reason"]),
    }


# ينشئ إجراءً أخيرًا عند عدم وجود تطابق في البنك.
def _generated_fallback(selected_track: str, gap: str) -> dict[str, str]:
    track = selected_track if selected_track != "any" else "the selected track"
    readable_gap = gap.replace("_", " ")
    return {
        "action": f"Complete one small {track} mini project focused on {readable_gap}.",
        "reason": f"This targets {readable_gap} with one practical deliverable.",
    }


# يحول أسماء الحقائق الخام إلى أسماء الفجوات في البنك.
def _normalize_detected_gaps(detected_gaps: list[str]) -> list[str]:
    first_pass: list[str] = []
    repeats: list[str] = []
    seen: set[str] = set()
    for gap in detected_gaps:
        bank_gap = _FACT_TO_BANK_GAP.get(gap, gap)
        if bank_gap in seen:
            repeats.append(bank_gap)
            continue
        first_pass.append(bank_gap)
        seen.add(bank_gap)
    return first_pass + repeats


# يوحد قيمة نصية إلى خيار معروف ومسموح.
def _normalize_choice(value: Any, default: str, allowed: set[str]) -> str:
    normalized = str(value or default).strip().lower()
    return normalized if normalized in allowed else default


# يوحد مستوى المستخدم لاستخدامه في مطابقة البنك.
def _normalize_level(value: Any) -> str:
    return _normalize_choice(value, "beginner", {"beginner", "intermediate", "advanced"})


# يوحد الهدف النهائي لاستخدامه في مطابقة البنك.
def _normalize_target_outcome(value: Any) -> str:
    return _normalize_choice(value, "any", {"internship", "job", "freelance"})
