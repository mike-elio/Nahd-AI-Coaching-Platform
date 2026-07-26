"""Static output formatting specs for GPES recommendation summaries."""

from __future__ import annotations

from typing import Any


GENERIC_PHRASES = (
    "fits your direction",
    "strong alignment",
    "this path is suitable",
    "matches the direction and readiness",
    "balance of interests",
    "start making structured progress",
    "you show",
    "you seem",
)
SUMMARY_SECTIONS = (
    ("WHY THIS TRACK:", "why_selected", "No rule-backed explanation was generated."),
    ("CORE STRENGTHS:", "strengths", "No positive fact reached the strength threshold."),
    ("GAP RESOLUTION PLAN:", "gap_resolution_plan", "No gap resolution plan was generated."),
)
GOAL_COMPARISON_ORDER: dict[str, list[str]] = {
    "SE_GOAL_01": ["SE_GOAL_05", "SE_GOAL_02"],
    "SE_GOAL_02": ["SE_GOAL_01", "SE_GOAL_05"],
    "SE_GOAL_03": ["SE_GOAL_01", "SE_GOAL_04"],
    "SE_GOAL_04": ["SE_GOAL_01", "SE_GOAL_03"],
    "SE_GOAL_05": ["SE_GOAL_01", "SE_GOAL_02"],
    "SE_GOAL_06": ["SE_GOAL_01", "SE_GOAL_07"],
    "SE_GOAL_07": ["SE_GOAL_01", "SE_GOAL_02", "SE_GOAL_03", "SE_GOAL_04", "SE_GOAL_05"],
    "SE_GOAL_08": ["SE_GOAL_02", "SE_GOAL_07"],
    "AIE_GOAL_01": ["AIE_GOAL_02", "AIE_GOAL_04"],
    "AIE_GOAL_02": ["AIE_GOAL_01", "AIE_GOAL_03"],
    "AIE_GOAL_03": ["AIE_GOAL_01", "AIE_GOAL_02"],
    "AIE_GOAL_04": ["AIE_GOAL_01", "AIE_GOAL_05"],
    "AIE_GOAL_05": ["AIE_GOAL_01", "AIE_GOAL_04"],
    "AIE_GOAL_06": ["AIE_GOAL_01", "AIE_GOAL_02", "AIE_GOAL_03", "AIE_GOAL_04", "AIE_GOAL_05"],
    "CNE_GOAL_01": ["CNE_GOAL_02", "CNE_GOAL_04"],
    "CNE_GOAL_02": ["CNE_GOAL_01", "CNE_GOAL_04"],
    "CNE_GOAL_03": ["CNE_GOAL_01", "CNE_GOAL_04"],
    "CNE_GOAL_04": ["CNE_GOAL_01", "CNE_GOAL_02"],
    "CNE_GOAL_05": ["CNE_GOAL_01", "CNE_GOAL_03"],
    "CNE_GOAL_06": ["CNE_GOAL_01", "CNE_GOAL_02", "CNE_GOAL_03", "CNE_GOAL_04", "CNE_GOAL_05"],
}
GOAL_GAP_SPECS: dict[str, list[dict[str, Any]]] = {
    "SE_GOAL_01": [
        {"fact": "python_skill", "kind": "lt", "value": 3, "priority": 95},
        {"fact": "sql_skill", "kind": "lt", "value": 3, "priority": 85},
        {"fact": "api_concepts", "kind": "false", "priority": 80},
        {"fact": "backend_testing", "kind": "false", "priority": 75},
    ],
    "SE_GOAL_02": [
        {"fact": "js_skill", "kind": "lt", "value": 3, "priority": 95},
        {"fact": "web_basics", "kind": "lt", "value": 3, "priority": 90},
        {"fact": "dom_events", "kind": "false", "priority": 85},
        {"fact": "http_client_basics", "kind": "false", "priority": 80},
    ],
    "SE_GOAL_03": [
        {"fact": "linux_skill", "kind": "lt", "value": 3, "priority": 95},
        {"fact": "containers_basics", "kind": "false", "priority": 85},
        {"fact": "ci_basics", "kind": "false", "priority": 80},
        {"fact": "cloud_basics", "kind": "false", "priority": 75},
    ],
    "SE_GOAL_04": [
        {"fact": "python_skill", "kind": "lt", "value": 3, "priority": 95},
        {"fact": "security_mindset", "kind": "false", "priority": 85},
        {"fact": "owasp_awareness", "kind": "false", "priority": 80},
        {"fact": "secure_coding", "kind": "false", "priority": 75},
    ],
    "SE_GOAL_05": [
        {"fact": "sql_skill", "kind": "lt", "value": 3, "priority": 95},
        {"fact": "python_skill", "kind": "lt", "value": 3, "priority": 85},
        {"fact": "data_pipeline_basics", "kind": "false", "priority": 80},
        {"fact": "data_quality_awareness", "kind": "false", "priority": 75},
    ],
    "SE_GOAL_06": [
        {"fact": "programming_basic", "kind": "false", "priority": 100},
        {"fact": "basics_control_flow", "kind": "false", "priority": 95},
        {"fact": "api_concepts", "kind": "false", "priority": 90},
        {"fact": "db_modeling_skill", "kind": "lt", "value": 2, "priority": 85},
        {"fact": "input_validation", "kind": "false", "priority": 80},
        {"fact": "backend_testing", "kind": "false", "priority": 75},
    ],
    "SE_GOAL_07": [
        {"fact": "programming_basic", "kind": "false", "priority": 100},
        {"fact": "basics_control_flow", "kind": "false", "priority": 95},
        {"fact": "problem_solving", "kind": "lt", "value": 3, "priority": 90},
        {"fact": "web_basics", "kind": "lt", "value": 3, "priority": 85},
        {"fact": "js_skill", "kind": "lt", "value": 2, "priority": 82},
        {"fact": "version_control_git", "kind": "false", "priority": 80},
        {"fact": "dom_events", "kind": "false", "priority": 78},
        {"fact": "http_client_basics", "kind": "false", "priority": 75},
    ],
    "SE_GOAL_08": [
        {"fact": "web_basics", "kind": "lt", "value": 2, "priority": 100},
        {"fact": "js_skill", "kind": "lt", "value": 1, "priority": 95},
        {"fact": "dom_events", "kind": "false", "priority": 90},
        {"fact": "http_client_basics", "kind": "false", "priority": 85},
        {"fact": "ui_accessibility", "kind": "false", "priority": 75},
    ],
    "AIE_GOAL_01": [
        {"fact": "python_skill", "kind": "lt", "value": 3, "priority": 95},
        {"fact": "math_skill", "kind": "lt", "value": 3, "priority": 90},
        {"fact": "ml_exposure", "kind": "lt", "value": 2, "priority": 85},
        {"fact": "data_handling", "kind": "lt", "value": 2, "priority": 80},
    ],
    "AIE_GOAL_02": [
        {"fact": "python_skill", "kind": "lt", "value": 3, "priority": 95},
        {"fact": "math_skill", "kind": "lt", "value": 3, "priority": 90},
        {"fact": "ml_exposure", "kind": "lt", "value": 2, "priority": 85},
        {"fact": "weak_device", "kind": "true", "priority": 80},
    ],
    "AIE_GOAL_03": [
        {"fact": "python_skill", "kind": "lt", "value": 3, "priority": 95},
        {"fact": "math_skill", "kind": "lt", "value": 2, "priority": 90},
        {"fact": "ml_exposure", "kind": "lt", "value": 2, "priority": 85},
        {"fact": "english_level", "kind": "enum", "value": {"intermediate", "advanced"}, "priority": 80},
    ],
    "AIE_GOAL_04": [
        {"fact": "python_skill", "kind": "lt", "value": 3, "priority": 95},
        {"fact": "data_handling", "kind": "lt", "value": 3, "priority": 90},
        {"fact": "sql_skill", "kind": "lt", "value": 2, "priority": 85},
    ],
    "AIE_GOAL_05": [
        {"fact": "python_skill", "kind": "lt", "value": 4, "priority": 95},
        {"fact": "math_skill", "kind": "lt", "value": 3, "priority": 90},
        {"fact": "english_level", "kind": "enum", "value": {"advanced"}, "priority": 85},
    ],
    "AIE_GOAL_06": [
        {"fact": "python_skill_basic", "kind": "false", "priority": 100},
        {"fact": "any_programming_experience", "kind": "false", "priority": 95},
        {"fact": "python_skill", "kind": "lt", "value": 2, "priority": 90},
        {"fact": "math_skill", "kind": "lt", "value": 2, "priority": 85},
        {"fact": "ml_exposure", "kind": "lt", "value": 1, "priority": 80},
        {"fact": "data_handling", "kind": "lt", "value": 1, "priority": 75},
    ],
    "CNE_GOAL_01": [
        {"fact": "networking_theory", "kind": "lt", "value": 2, "priority": 95},
        {"fact": "lab_access", "kind": "false", "priority": 90},
        {"fact": "cisco_tools", "kind": "lt", "value": 2, "priority": 85},
    ],
    "CNE_GOAL_02": [
        {"fact": "networking_theory", "kind": "lt", "value": 3, "priority": 95},
        {"fact": "lab_access", "kind": "false", "priority": 90},
        {"fact": "linux_skill", "kind": "lt", "value": 2, "priority": 85},
    ],
    "CNE_GOAL_03": [
        {"fact": "networking_theory", "kind": "lt", "value": 3, "priority": 95},
        {"fact": "lab_access", "kind": "false", "priority": 90},
        {"fact": "weak_internet", "kind": "true", "priority": 85},
    ],
    "CNE_GOAL_04": [
        {"fact": "networking_theory", "kind": "lt", "value": 2, "priority": 95},
        {"fact": "linux_skill", "kind": "lt", "value": 2, "priority": 90},
        {"fact": "weak_internet", "kind": "true", "priority": 85},
    ],
    "CNE_GOAL_05": [
        {"fact": "networking_theory", "kind": "lt", "value": 2, "priority": 95},
        {"fact": "scripting_skill", "kind": "lt", "value": 2, "priority": 90},
    ],
    "CNE_GOAL_06": [
        {"fact": "networking_basic", "kind": "false", "priority": 100},
        {"fact": "osi_layers_basic", "kind": "false", "priority": 95},
        {"fact": "ip_subnetting_basic", "kind": "false", "priority": 90},
        {"fact": "linux_cli_net_tools_skill", "kind": "lt", "value": 2, "priority": 85},
        {"fact": "lab_access", "kind": "false", "priority": 75},
    ],
}
FACT_LABEL_OVERRIDES = {
    "prefers_backend": "backend direction",
    "prefers_frontend": "frontend direction",
    "prefers_devops": "DevOps direction",
    "prefers_security": "security direction",
    "prefers_ml": "ML direction",
    "prefers_cv": "computer vision direction",
    "prefers_nlp": "NLP direction",
    "prefers_data_eng": "data engineering direction",
    "prefers_netsec": "network security direction",
    "prefers_wireless": "wireless networking direction",
    "prefers_cloud_net": "cloud networking direction",
    "prefers_projects": "hands-on learning preference",
    "prefers_building_apps": "application-building preference",
    "pretrack_readiness": "readiness score",
}
