"""
GPES Expert System — SE Domain Rules.

Derived from:
  - knowledge_base/goals/goals_se.json  (eligibility_rules + disqualifiers)
  - app/models.py                       (Universal + SE Facts)
  - gpes_plan.md                        (tiers, forward chaining, conflict resolution)

Exports:
  RULES : list[dict]   — every element follows the unified rule structure.

Priority scheme:
  Profile  300–399   (fires first — characterize the user)
  Goal     200–299   (fires second — qualify / exclude goals)
  Sanity   100–199   (fires last — final overrides & scope reduction)
  Within the same tier higher number = higher priority = fires first.
"""

RULES: list = [

    # ===================================================================
    #  NORMALIZATION / DIRECTION LAYER  (391–399)
    #  Derive stable routing facts from interview output before goal rules.
    # ===================================================================

    {
        "rule_id": "SE_NORMALIZE_001",
        "domain": "SE",
        "tier": "profile",
        "priority": 399,
        "conditions": [
            {"fact": "prefers_backend", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "se_backend_direction",
                "value": True,
            },
        ],
    },

    {
        "rule_id": "SE_NORMALIZE_002",
        "domain": "SE",
        "tier": "profile",
        "priority": 398,
        "conditions": [
            {"fact": "prefers_building_apps", "op": "==", "value": True},
            {"fact": "prefers_frontend", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "se_frontend_direction",
                "value": True,
            },
        ],
    },

    # ===================================================================
    #  PROFILE TIER  (300–390)
    #  Characterize readiness and identify foundation-stage candidates.
    # ===================================================================

    {
        "rule_id": "SE_PROFILE_000",
        "domain": "SE",
        "tier": "profile",
        "priority": 397,
        "conditions": [
            {"fact": "programming_basic", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "se_foundation_candidate",
                "value": True,
            },
            {
                "type": "add_reason",
                "category": "weakness",
                "text": "No prior coding background yet - a foundations-first path is the safest start",
            },
        ],
    },

    {
        "rule_id": "SE_PROFILE_000B",
        "domain": "SE",
        "tier": "profile",
        "priority": 396,
        "conditions": [
            {"fact": "basics_control_flow", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "se_foundation_candidate",
                "value": True,
            },
            {
                "type": "add_reason",
                "category": "weakness",
                "text": "Programming fundamentals still need reinforcement before specialization",
            },
        ],
    },

    {
        "rule_id": "SE_PROFILE_000C",
        "domain": "SE",
        "tier": "profile",
        "priority": 395,
        "conditions": [
            {"fact": "pretrack_readiness", "op": ">=", "value": 2},
            {"fact": "current_level", "op": "==", "value": "beginner"},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "se_foundation_candidate",
                "value": True,
            },
            {
                "type": "add_reason",
                "category": "strength",
                "text": "Motivated beginner with enough readiness to start a guided foundation track",
            },
        ],
    },

    {
        "rule_id": "SE_PROFILE_000D",
        "domain": "SE",
        "tier": "profile",
        "priority": 394,
        "conditions": [
            {"fact": "prefers_backend", "op": "==", "value": True},
            {"fact": "api_concepts", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "se_foundation_candidate",
                "value": True,
            },
        ],
    },

    {
        "rule_id": "SE_PROFILE_000E",
        "domain": "SE",
        "tier": "profile",
        "priority": 393,
        "conditions": [
            {"fact": "prefers_frontend", "op": "==", "value": True},
            {"fact": "web_basics", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "se_foundation_candidate",
                "value": True,
            },
        ],
    },

    {
        "rule_id": "SE_PROFILE_001",
        "domain": "SE",
        "tier": "profile",
        "priority": 390,
        "conditions": [
            {"fact": "python_skill", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "weakness",
                "text": "Limited Python experience — foundational content recommended",
            },
        ],
    },

    {
        "rule_id": "SE_PROFILE_002",
        "domain": "SE",
        "tier": "profile",
        "priority": 380,
        "conditions": [
            {"fact": "python_skill", "op": ">=", "value": 3},
            {"fact": "problem_solving", "op": ">=", "value": 3},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "strength",
                "text": "Strong programming and problem-solving foundation",
            },
        ],
    },

    {
        "rule_id": "SE_PROFILE_003",
        "domain": "SE",
        "tier": "profile",
        "priority": 370,
        "conditions": [
            {"fact": "hours_per_week", "op": "<", "value": 8},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "Less than 8 hours/week — only lightweight tracks feasible",
            },
        ],
    },

    {
        "rule_id": "SE_PROFILE_004",
        "domain": "SE",
        "tier": "profile",
        "priority": 360,
        "conditions": [
            {"fact": "weak_device", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "Weak device — hardware-intensive tracks not recommended",
            },
        ],
    },

    {
        "rule_id": "SE_PROFILE_005",
        "domain": "SE",
        "tier": "profile",
        "priority": 350,
        "conditions": [
            {"fact": "user_type", "op": "==", "value": "graduate"},
            {"fact": "target_outcome", "op": "in", "value": ["job", "internship"]},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "strength",
                "text": "Graduate with career focus — ready for professional tracks",
            },
        ],
    },

    # ===================================================================
    #  GOAL TIER — QUALIFY  (250–299)
    #  Strong specialization rules stay first; foundation/fallback rules
    #  are intentionally lower priority to preserve existing paths.
    # ===================================================================

    # --- SE_GOAL_01  Backend Development Track -------------------------

    {
        "rule_id": "SE_GOAL_Q_001",
        "domain": "SE",
        "tier": "goal",
        "priority": 290,
        "conditions": [
            {"fact": "prefers_backend", "op": "==", "value": True},
            {"fact": "python_skill", "op": ">=", "value": 2},
            {"fact": "hours_per_week", "op": ">=", "value": 8},
            {"fact": "target_outcome", "op": "in",
             "value": ["internship", "job", "freelance"]},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "SE_GOAL_01",
                "reason": "Meets Python skill, weekly hours, and backend preference",
            },
        ],
    },

    # --- SE_GOAL_02  Frontend Development Track ------------------------

    {
        "rule_id": "SE_GOAL_Q_002",
        "domain": "SE",
        "tier": "goal",
        "priority": 280,
        "conditions": [
            {"fact": "prefers_frontend", "op": "==", "value": True},
            {"fact": "js_skill", "op": ">=", "value": 1},
            {"fact": "hours_per_week", "op": ">=", "value": 8},
            {"fact": "target_outcome", "op": "in",
             "value": ["internship", "job", "freelance"]},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "SE_GOAL_02",
                "reason": "Meets JavaScript skill, weekly hours, and frontend preference",
            },
        ],
    },

    # --- SE_GOAL_03  DevOps & Cloud Engineering Track ------------------

    {
        "rule_id": "SE_GOAL_Q_003",
        "domain": "SE",
        "tier": "goal",
        "priority": 270,
        "conditions": [
            {"fact": "prefers_devops", "op": "==", "value": True},
            {"fact": "linux_skill", "op": ">=", "value": 1},
            {"fact": "hours_per_week", "op": ">=", "value": 10},
            {"fact": "weak_device", "op": "==", "value": False},
            {"fact": "target_outcome", "op": "in",
             "value": ["job", "freelance", "internship"]},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "SE_GOAL_03",
                "reason": "Meets Linux skill, weekly hours, device requirement, and DevOps preference",
            },
        ],
    },

    # --- SE_GOAL_04  Application Security Track ------------------------

    {
        "rule_id": "SE_GOAL_Q_004",
        "domain": "SE",
        "tier": "goal",
        "priority": 260,
        "conditions": [
            {"fact": "prefers_security", "op": "==", "value": True},
            {"fact": "python_skill", "op": ">=", "value": 2},
            {"fact": "hours_per_week", "op": ">=", "value": 10},
            {"fact": "target_outcome", "op": "in",
             "value": ["job", "freelance", "internship"]},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "SE_GOAL_04",
                "reason": "Meets Python skill, weekly hours, and security preference",
            },
        ],
    },

    # --- SE_GOAL_05  Data Engineering Track ----------------------------

    {
        "rule_id": "SE_GOAL_Q_005",
        "domain": "SE",
        "tier": "goal",
        "priority": 250,
        "conditions": [
            {"fact": "sql_skill", "op": ">=", "value": 2},
            {"fact": "python_skill", "op": ">=", "value": 2},
            {"fact": "hours_per_week", "op": ">=", "value": 8},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "SE_GOAL_05",
                "reason": "Meets SQL, Python, and weekly hours requirements (fallback track)",
            },
        ],
    },

    # --- SE_GOAL_06  Backend Development Foundations Track ------------

    {
        "rule_id": "SE_GOAL_Q_006",
        "domain": "SE",
        "tier": "goal",
        "priority": 249,
        "conditions": [
            {"fact": "se_foundation_candidate", "op": "==", "value": True},
            {"fact": "prefers_backend", "op": "==", "value": True},
            {"fact": "hours_per_week", "op": ">=", "value": 1},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "SE_GOAL_06",
                "reason": "Backend interest is clear, but current fundamentals point to a backend foundations track first",
            },
        ],
    },

    # --- SE_GOAL_08  Frontend Development Foundations Track ----------

    {
        "rule_id": "SE_GOAL_Q_008",
        "domain": "SE",
        "tier": "goal",
        "priority": 248,
        "conditions": [
            {"fact": "se_foundation_candidate", "op": "==", "value": True},
            {"fact": "prefers_frontend", "op": "==", "value": True},
            {"fact": "hours_per_week", "op": ">=", "value": 1},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "SE_GOAL_08",
                "reason": "Your direction is clearly frontend-oriented, but the next best step is to strengthen frontend foundations first",
            },
        ],
    },

    # --- SE_GOAL_07  Software Engineering Foundations Track ----------

    {
        "rule_id": "SE_GOAL_Q_007",
        "domain": "SE",
        "tier": "goal",
        "priority": 246,
        "conditions": [
            {"fact": "se_foundation_candidate", "op": "==", "value": True},
            {"fact": "hours_per_week", "op": ">=", "value": 1},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "SE_GOAL_07",
                "reason": "A general software-engineering foundations track is recommended before committing to a deeper specialization",
            },
        ],
    },

    # ===================================================================
    #  GOAL TIER — EXCLUDE  (200–249)
    # ===================================================================

    # --- SE_GOAL_01  exclusions ----------------------------------------

    {
        "rule_id": "SE_GOAL_X_001",
        "domain": "SE",
        "tier": "goal",
        "priority": 249,
        "conditions": [
            {"fact": "prefers_frontend", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_01",
                "reason": "User prefers frontend — redirect to SE_GOAL_02",
            },
        ],
    },

    {
        "rule_id": "SE_GOAL_X_002",
        "domain": "SE",
        "tier": "goal",
        "priority": 248,
        "conditions": [
            {"fact": "python_skill", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_01",
                "reason": "Python skill below minimum threshold (requires >= 2)",
            },
        ],
    },

    # --- SE_GOAL_02  exclusions ----------------------------------------

    {
        "rule_id": "SE_GOAL_X_003",
        "domain": "SE",
        "tier": "goal",
        "priority": 247,
        "conditions": [
            {"fact": "prefers_backend", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_02",
                "reason": "User prefers backend — redirect to SE_GOAL_01",
            },
        ],
    },

    {
        "rule_id": "SE_GOAL_X_004",
        "domain": "SE",
        "tier": "goal",
        "priority": 246,
        "conditions": [
            {"fact": "js_skill", "op": "<", "value": 1},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_02",
                "reason": "No JavaScript background (requires >= 1)",
            },
        ],
    },

    # --- SE_GOAL_03  exclusions ----------------------------------------

    {
        "rule_id": "SE_GOAL_X_005",
        "domain": "SE",
        "tier": "goal",
        "priority": 245,
        "conditions": [
            {"fact": "weak_device", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_03",
                "reason": "Weak device — Docker/K8s require adequate hardware",
            },
        ],
    },

    {
        "rule_id": "SE_GOAL_X_006",
        "domain": "SE",
        "tier": "goal",
        "priority": 244,
        "conditions": [
            {"fact": "linux_skill", "op": "<", "value": 1},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_03",
                "reason": "Linux is fundamental to DevOps (requires >= 1)",
            },
        ],
    },

    # --- SE_GOAL_04  exclusions ----------------------------------------

    {
        "rule_id": "SE_GOAL_X_007",
        "domain": "SE",
        "tier": "goal",
        "priority": 243,
        "conditions": [
            {"fact": "prefers_backend", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_04",
                "reason": "User prefers backend — redirect to SE_GOAL_01",
            },
        ],
    },

    # --- SE_GOAL_05  exclusions ----------------------------------------

    {
        "rule_id": "SE_GOAL_X_008",
        "domain": "SE",
        "tier": "goal",
        "priority": 242,
        "conditions": [
            {"fact": "prefers_backend", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_05",
                "reason": "User prefers backend — redirect to SE_GOAL_01",
            },
        ],
    },

    {
        "rule_id": "SE_GOAL_X_009",
        "domain": "SE",
        "tier": "goal",
        "priority": 241,
        "conditions": [
            {"fact": "sql_skill", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_05",
                "reason": "SQL skill below minimum for Data Engineering (requires >= 2)",
            },
        ],
    },

    {
        "rule_id": "SE_GOAL_X_010",
        "domain": "SE",
        "tier": "goal",
        "priority": 240,
        "conditions": [
            {"fact": "hours_per_week", "op": "<", "value": 8},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_01",
                "reason": "Insufficient weekly hours for Backend track (requires >= 8)",
            },
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_02",
                "reason": "Insufficient weekly hours for Frontend track (requires >= 8)",
            },
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_05",
                "reason": "Insufficient weekly hours for Data Engineering track (requires >= 8)",
            },
        ],
    },

    # ===================================================================
    #  SANITY TIER  (100–199)
    # ===================================================================

    {
        "rule_id": "SE_SANITY_001",
        "domain": "SE",
        "tier": "sanity",
        "priority": 190,
        "conditions": [
            {"fact": "hours_per_week", "op": "<", "value": 10},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_03",
                "reason": "DevOps track requires >= 10 hrs/week — time insufficient",
            },
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_04",
                "reason": "AppSec track requires >= 10 hrs/week — time insufficient",
            },
        ],
    },

    {
        "rule_id": "SE_SANITY_002",
        "domain": "SE",
        "tier": "sanity",
        "priority": 180,
        "conditions": [
            {"fact": "weak_device", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "SE_GOAL_03",
                "reason": "Weak device incompatible with DevOps containerisation tooling",
            },
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "Weak device limits available SE tracks to Backend/Frontend/DataEng",
            },
        ],
    },

    {
        "rule_id": "SE_SANITY_003",
        "domain": "SE",
        "tier": "sanity",
        "priority": 170,
        "conditions": [
            {"fact": "prefers_backend", "op": "==", "value": False},
            {"fact": "prefers_frontend", "op": "==", "value": False},
            {"fact": "prefers_devops", "op": "==", "value": False},
            {"fact": "prefers_security", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "SE_GOAL_07",
                "reason": "No specific SE preference - start with a general software engineering foundations track",
            },
            {
                "type": "add_reason",
                "category": "info",
                "text": "No clear SE specialization preference detected - using the general foundations fallback",
            },
        ],
    },

    {
        "rule_id": "SE_SANITY_004",
        "domain": "SE",
        "tier": "sanity",
        "priority": 160,
        "conditions": [
            {"fact": "current_level", "op": "==", "value": "beginner"},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "Beginner level — advanced tracks may require prerequisite study",
            },
        ],
    },

    {
        "rule_id": "SE_SANITY_005",
        "domain": "SE",
        "tier": "sanity",
        "priority": 150,
        "conditions": [
            {"fact": "pressure_load", "op": "==", "value": "high"},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "High pressure load — consider reducing track intensity or extending timeline",
            },
        ],
    },

    {
        "rule_id": "SE_SANITY_006",
        "domain": "SE",
        "tier": "sanity",
        "priority": 140,
        "conditions": [
            {"fact": "hours_per_week", "op": ">=", "value": 1},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "SE_GOAL_07",
                "reason": "Safety-net fallback: every valid SE interview can start from a software engineering foundations track",
            },
        ],
    },
]
