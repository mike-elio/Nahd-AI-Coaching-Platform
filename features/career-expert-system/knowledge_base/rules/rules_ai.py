"""
GPES Expert System — AIE Domain Rules.

Derived from:
  - knowledge_base/goals/goals_aie.json  (eligibility_rules + disqualifiers)
  - app/models.py                        (Universal + AIE Facts)
  - gpes_plan.md                         (tiers, forward chaining, conflict resolution)

Exports:
  RULES : list[dict]

Priority scheme — same as SE:
  Profile  300–399 | Goal  200–299 | Sanity  100–199
"""

RULES: list = [

    #  NORMALIZATION / FOUNDATION LAYER  (391–399)

    {
        "rule_id": "AIE_NORMALIZE_001",
        "domain": "AIE",
        "tier": "profile",
        "priority": 399,
        "conditions": [
            {"fact": "prefers_ml", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "aie_applied_direction",
                "value": True,
            },
        ],
    },

    #  PROFILE TIER  (300–390)
    

    {
        "rule_id": "AIE_PROFILE_000",
        "domain": "AIE",
        "tier": "profile",
        "priority": 398,
        "conditions": [
            {"fact": "python_skill_basic", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "aie_foundation_candidate",
                "value": True,
            },
            {
                "type": "add_reason",
                "category": "weakness",
                "text": "Python readiness is still limited - an AI foundations track is the safer entry point",
            },
        ],
    },

    {
        "rule_id": "AIE_PROFILE_000B",
        "domain": "AIE",
        "tier": "profile",
        "priority": 397,
        "conditions": [
            {"fact": "any_programming_experience", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "aie_foundation_candidate",
                "value": True,
            },
        ],
    },

    {
        "rule_id": "AIE_PROFILE_000C",
        "domain": "AIE",
        "tier": "profile",
        "priority": 396,
        "conditions": [
            {"fact": "pretrack_readiness", "op": ">=", "value": 2},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "aie_foundation_candidate",
                "value": True,
            },
            {
                "type": "add_reason",
                "category": "strength",
                "text": "Motivated beginner with enough readiness to start an AI foundations path",
            },
        ],
    },

    {
        "rule_id": "AIE_PROFILE_000D",
        "domain": "AIE",
        "tier": "profile",
        "priority": 395,
        "conditions": [
            {"fact": "python_skill", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "aie_foundation_candidate",
                "value": True,
            },
        ],
    },

    {
        "rule_id": "AIE_PROFILE_000E",
        "domain": "AIE",
        "tier": "profile",
        "priority": 394,
        "conditions": [
            {"fact": "math_skill", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "aie_foundation_candidate",
                "value": True,
            },
        ],
    },

    {
        "rule_id": "AIE_PROFILE_000F",
        "domain": "AIE",
        "tier": "profile",
        "priority": 393,
        "conditions": [
            {"fact": "ml_exposure", "op": "<", "value": 1},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "aie_foundation_candidate",
                "value": True,
            },
        ],
    },

    #  PROFILE TIER  (300–399)

    {
        "rule_id": "AIE_PROFILE_001",
        "domain": "AIE",
        "tier": "profile",
        "priority": 390,
        "conditions": [
            {"fact": "math_skill", "op": ">=", "value": 3},
            {"fact": "python_skill", "op": ">=", "value": 3},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "strength",
                "text": "Strong math and Python foundation — well-suited for AI tracks",
            },
        ],
    },

    {
        "rule_id": "AIE_PROFILE_002",
        "domain": "AIE",
        "tier": "profile",
        "priority": 380,
        "conditions": [
            {"fact": "math_skill", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "weakness",
                "text": "Weak math background — ML/CV/NLP tracks will be challenging",
            },
        ],
    },

    {
        "rule_id": "AIE_PROFILE_003",
        "domain": "AIE",
        "tier": "profile",
        "priority": 370,
        "conditions": [
            {"fact": "hours_per_week", "op": "<", "value": 10},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "Less than 10 hours/week — most AI tracks require substantial time",
            },
        ],
    },

    {
        "rule_id": "AIE_PROFILE_004",
        "domain": "AIE",
        "tier": "profile",
        "priority": 360,
        "conditions": [
            {"fact": "weak_device", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "Weak device — model training tracks require cloud or GPU resources",
            },
        ],
    },

    {
        "rule_id": "AIE_PROFILE_005",
        "domain": "AIE",
        "tier": "profile",
        "priority": 350,
        "conditions": [
            {"fact": "user_type", "op": "==", "value": "graduate"},
            {"fact": "research_interest", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "strength",
                "text": "Graduate with research interest — AI Research track may be ideal",
            },
        ],
    },

    #  GOAL TIER — QUALIFY  (250–299)

    # --- AIE_GOAL_01  Machine Learning Engineering Track ----------------

    {
        "rule_id": "AIE_GOAL_Q_001",
        "domain": "AIE",
        "tier": "goal",
        "priority": 290,
        "conditions": [
            {"fact": "prefers_ml", "op": "==", "value": True},
            {"fact": "python_skill", "op": ">=", "value": 2},
            {"fact": "math_skill", "op": ">=", "value": 2},
            {"fact": "hours_per_week", "op": ">=", "value": 10},
            {"fact": "target_outcome", "op": "in",
             "value": ["job", "internship", "freelance"]},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "AIE_GOAL_01",
                "reason": "Meets ML preference, Python, math, and time requirements",
            },
        ],
    },

    # --- AIE_GOAL_02  Computer Vision Track ----------------------------

    {
        "rule_id": "AIE_GOAL_Q_002",
        "domain": "AIE",
        "tier": "goal",
        "priority": 280,
        "conditions": [
            {"fact": "prefers_cv", "op": "==", "value": True},
            {"fact": "python_skill", "op": ">=", "value": 3},
            {"fact": "math_skill", "op": ">=", "value": 2},
            {"fact": "ml_exposure", "op": ">=", "value": 2},
            {"fact": "weak_device", "op": "==", "value": False},
            {"fact": "hours_per_week", "op": ">=", "value": 10},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "AIE_GOAL_02",
                "reason": "Meets CV preference, Python, math, ML exposure, device, and time requirements",
            },
        ],
    },

    # --- AIE_GOAL_03  Natural Language Processing Track -----------------

    {
        "rule_id": "AIE_GOAL_Q_003",
        "domain": "AIE",
        "tier": "goal",
        "priority": 270,
        "conditions": [
            {"fact": "prefers_nlp", "op": "==", "value": True},
            {"fact": "python_skill", "op": ">=", "value": 3},
            {"fact": "math_skill", "op": ">=", "value": 2},
            {"fact": "english_level", "op": "in",
             "value": ["intermediate", "advanced"]},
            {"fact": "hours_per_week", "op": ">=", "value": 10},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "AIE_GOAL_03",
                "reason": "Meets NLP preference, Python, math, English, and time requirements",
            },
        ],
    },

    # --- AIE_GOAL_04  AI Data Engineering Track ------------------------

    {
        "rule_id": "AIE_GOAL_Q_004",
        "domain": "AIE",
        "tier": "goal",
        "priority": 260,
        "conditions": [
            {"fact": "prefers_data_eng", "op": "==", "value": True},
            {"fact": "python_skill", "op": ">=", "value": 2},
            {"fact": "data_handling", "op": ">=", "value": 2},
            {"fact": "hours_per_week", "op": ">=", "value": 8},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "AIE_GOAL_04",
                "reason": "Meets data engineering preference, Python, data handling, and time requirements",
            },
        ],
    },

    # --- AIE_GOAL_05  AI Research Track --------------------------------

    {
        "rule_id": "AIE_GOAL_Q_005",
        "domain": "AIE",
        "tier": "goal",
        "priority": 250,
        "conditions": [
            {"fact": "research_interest", "op": "==", "value": True},
            {"fact": "user_type", "op": "==", "value": "graduate"},
            {"fact": "python_skill", "op": ">=", "value": 3},
            {"fact": "math_skill", "op": ">=", "value": 3},
            {"fact": "target_outcome", "op": "==", "value": "research"},
            {"fact": "english_level", "op": "in",
             "value": ["intermediate", "advanced"]},
            {"fact": "hours_per_week", "op": ">=", "value": 12},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "AIE_GOAL_05",
                "reason": "Graduate researcher with strong Python, math, English, and dedicated time",
            },
        ],
    },

    # --- AIE_GOAL_06  AI Foundations Track ----------------------------

    {
        "rule_id": "AIE_GOAL_Q_006",
        "domain": "AIE",
        "tier": "goal",
        "priority": 246,
        "conditions": [
            {"fact": "aie_foundation_candidate", "op": "==", "value": True},
            {"fact": "hours_per_week", "op": ">=", "value": 1},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "AIE_GOAL_06",
                "reason": "Your interest in AI is clear, and the strongest next step is to build foundations before choosing a deeper specialization",
            },
        ],
    },

    # ===================================================================
    #  GOAL TIER — EXCLUDE  (200–249)
    # ===================================================================

    # --- AIE_GOAL_01  exclusions ---------------------------------------

    {
        "rule_id": "AIE_GOAL_X_001",
        "domain": "AIE",
        "tier": "goal",
        "priority": 249,
        "conditions": [
            {"fact": "prefers_cv", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_01",
                "reason": "User prefers Computer Vision — redirect to AIE_GOAL_02",
            },
        ],
    },

    {
        "rule_id": "AIE_GOAL_X_002",
        "domain": "AIE",
        "tier": "goal",
        "priority": 248,
        "conditions": [
            {"fact": "math_skill", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_01",
                "reason": "Math skill below minimum for ML (requires >= 2)",
            },
        ],
    },

    {
        "rule_id": "AIE_GOAL_X_003",
        "domain": "AIE",
        "tier": "goal",
        "priority": 247,
        "conditions": [
            {"fact": "weak_device", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_01",
                "reason": "Weak device — model training requires computational resources",
            },
        ],
    },

    # --- AIE_GOAL_02  exclusions ---------------------------------------

    {
        "rule_id": "AIE_GOAL_X_004",
        "domain": "AIE",
        "tier": "goal",
        "priority": 246,
        "conditions": [
            {"fact": "prefers_ml", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_02",
                "reason": "User prefers general ML — redirect to AIE_GOAL_01",
            },
        ],
    },

    {
        "rule_id": "AIE_GOAL_X_005",
        "domain": "AIE",
        "tier": "goal",
        "priority": 245,
        "conditions": [
            {"fact": "ml_exposure", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_02",
                "reason": "ML foundation required before CV (ml_exposure requires >= 2)",
            },
        ],
    },

    {
        "rule_id": "AIE_GOAL_X_006",
        "domain": "AIE",
        "tier": "goal",
        "priority": 244,
        "conditions": [
            {"fact": "weak_device", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_02",
                "reason": "GPU or cloud compute required for CV training",
            },
        ],
    },

    # --- AIE_GOAL_03  exclusions ---------------------------------------

    {
        "rule_id": "AIE_GOAL_X_007",
        "domain": "AIE",
        "tier": "goal",
        "priority": 243,
        "conditions": [
            {"fact": "english_level", "op": "==", "value": "basic"},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_03",
                "reason": "Most NLP resources and models are in English (requires intermediate+)",
            },
        ],
    },

    {
        "rule_id": "AIE_GOAL_X_008",
        "domain": "AIE",
        "tier": "goal",
        "priority": 242,
        "conditions": [
            {"fact": "prefers_data_eng", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_03",
                "reason": "User prefers data engineering — redirect to AIE_GOAL_04",
            },
        ],
    },

    # --- AIE_GOAL_04  exclusions ---------------------------------------

    {
        "rule_id": "AIE_GOAL_X_009",
        "domain": "AIE",
        "tier": "goal",
        "priority": 241,
        "conditions": [
            {"fact": "data_handling", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_04",
                "reason": "Data handling foundation required (requires >= 2)",
            },
        ],
    },

    # --- AIE_GOAL_05  exclusions ---------------------------------------

    {
        "rule_id": "AIE_GOAL_X_010",
        "domain": "AIE",
        "tier": "goal",
        "priority": 240,
        "conditions": [
            {"fact": "user_type", "op": "==", "value": "student"},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_05",
                "reason": "Research track requires graduate-level background",
            },
        ],
    },

    {
        "rule_id": "AIE_GOAL_X_011",
        "domain": "AIE",
        "tier": "goal",
        "priority": 239,
        "conditions": [
            {"fact": "english_level", "op": "==", "value": "basic"},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_05",
                "reason": "Research papers are in English (requires intermediate+)",
            },
        ],
    },

    {
        "rule_id": "AIE_GOAL_X_012",
        "domain": "AIE",
        "tier": "goal",
        "priority": 238,
        "conditions": [
            {"fact": "hours_per_week", "op": "<", "value": 10},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_01",
                "reason": "Insufficient weekly hours for ML track (requires >= 10)",
            },
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_02",
                "reason": "Insufficient weekly hours for CV track (requires >= 10)",
            },
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_03",
                "reason": "Insufficient weekly hours for NLP track (requires >= 10)",
            },
        ],
    },

    # ===================================================================
    #  SANITY TIER  (100–199)
    # ===================================================================

    {
        "rule_id": "AIE_SANITY_001",
        "domain": "AIE",
        "tier": "sanity",
        "priority": 190,
        "conditions": [
            {"fact": "weak_device", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_01",
                "reason": "Weak device — cannot run ML training locally",
            },
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_02",
                "reason": "Weak device — cannot run CNN training locally",
            },
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "Weak device limits AI tracks to Data Engineering or lightweight NLP",
            },
        ],
    },

    {
        "rule_id": "AIE_SANITY_002",
        "domain": "AIE",
        "tier": "sanity",
        "priority": 180,
        "conditions": [
            {"fact": "english_level", "op": "==", "value": "basic"},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_03",
                "reason": "NLP track requires intermediate+ English",
            },
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_05",
                "reason": "Research track requires intermediate+ English",
            },
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "Basic English limits access to NLP and Research tracks",
            },
        ],
    },

    {
        "rule_id": "AIE_SANITY_003",
        "domain": "AIE",
        "tier": "sanity",
        "priority": 170,
        "conditions": [
            {"fact": "hours_per_week", "op": "<", "value": 12},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "AIE_GOAL_05",
                "reason": "Research track requires >= 12 hrs/week — time insufficient",
            },
        ],
    },

    {
        "rule_id": "AIE_SANITY_004",
        "domain": "AIE",
        "tier": "sanity",
        "priority": 160,
        "conditions": [
            {"fact": "current_level", "op": "==", "value": "beginner"},
            {"fact": "ml_exposure", "op": "<", "value": 1},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "Beginner with no ML exposure — consider foundational ML coursework first",
            },
        ],
    },

    {
        "rule_id": "AIE_SANITY_005",
        "domain": "AIE",
        "tier": "sanity",
        "priority": 150,
        "conditions": [
            {"fact": "pressure_load", "op": "==", "value": "high"},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "High pressure load — AI tracks are intensive; consider lighter workload",
            },
        ],
    },

    {
        "rule_id": "AIE_SANITY_006",
        "domain": "AIE",
        "tier": "sanity",
        "priority": 140,
        "conditions": [
            {"fact": "hours_per_week", "op": ">=", "value": 1},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "AIE_GOAL_06",
                "reason": "Safety-net fallback: every valid AIE interview can start from an AI foundations track",
            },
        ],
    },
]
