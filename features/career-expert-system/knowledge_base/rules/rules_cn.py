"""
GPES Expert System — CNE Domain Rules.

Derived from:
  - knowledge_base/goals/goals_cne.json  (eligibility_rules + disqualifiers)
  - app/models.py                        (Universal + CNE Facts)
  - gpes_plan.md                         (tiers, forward chaining, conflict resolution)

Exports:
  RULES : list[dict]

Priority scheme — same as SE / AIE:
  Profile  300–399 | Goal  200–299 | Sanity  100–199
"""

RULES: list = [

    # ===================================================================
    #  NORMALIZATION / FOUNDATION LAYER  (391–399)
    # ===================================================================

    {
        "rule_id": "CNE_PROFILE_000",
        "domain": "CNE",
        "tier": "profile",
        "priority": 399,
        "conditions": [
            {"fact": "networking_basic", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "cne_foundation_candidate",
                "value": True,
            },
            {
                "type": "add_reason",
                "category": "weakness",
                "text": "Networking fundamentals are still forming - a foundations-first networking path is recommended",
            },
        ],
    },

    {
        "rule_id": "CNE_PROFILE_000B",
        "domain": "CNE",
        "tier": "profile",
        "priority": 398,
        "conditions": [
            {"fact": "osi_layers_basic", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "cne_foundation_candidate",
                "value": True,
            },
        ],
    },

    {
        "rule_id": "CNE_PROFILE_000C",
        "domain": "CNE",
        "tier": "profile",
        "priority": 397,
        "conditions": [
            {"fact": "ip_subnetting_basic", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "cne_foundation_candidate",
                "value": True,
            },
        ],
    },

    {
        "rule_id": "CNE_PROFILE_000D",
        "domain": "CNE",
        "tier": "profile",
        "priority": 396,
        "conditions": [
            {"fact": "linux_cli_net_tools_skill", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "assert_fact",
                "key": "cne_foundation_candidate",
                "value": True,
            },
        ],
    },

    # ===================================================================
    #  PROFILE TIER  (300–399)
    # ===================================================================

    {
        "rule_id": "CNE_PROFILE_001",
        "domain": "CNE",
        "tier": "profile",
        "priority": 390,
        "conditions": [
            {"fact": "networking_theory", "op": ">=", "value": 3},
            {"fact": "cisco_tools", "op": ">=", "value": 2},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "strength",
                "text": "Solid networking theory and Cisco tool experience",
            },
        ],
    },

    {
        "rule_id": "CNE_PROFILE_002",
        "domain": "CNE",
        "tier": "profile",
        "priority": 380,
        "conditions": [
            {"fact": "networking_theory", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "weakness",
                "text": "Limited networking theory — most tracks require at least level 2",
            },
        ],
    },

    {
        "rule_id": "CNE_PROFILE_003",
        "domain": "CNE",
        "tier": "profile",
        "priority": 370,
        "conditions": [
            {"fact": "lab_access", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "No lab or simulator access — certification and hands-on tracks limited",
            },
        ],
    },

    {
        "rule_id": "CNE_PROFILE_004",
        "domain": "CNE",
        "tier": "profile",
        "priority": 360,
        "conditions": [
            {"fact": "hours_per_week", "op": "<", "value": 8},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "Less than 8 hours/week — only lightweight CNE tracks feasible",
            },
        ],
    },

    {
        "rule_id": "CNE_PROFILE_005",
        "domain": "CNE",
        "tier": "profile",
        "priority": 350,
        "conditions": [
            {"fact": "weak_internet", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "Weak internet connection — cloud-dependent tracks not recommended",
            },
        ],
    },

    # ===================================================================
    #  GOAL TIER — QUALIFY  (250–299)
    # ===================================================================

    # --- CNE_GOAL_01  CCNA Network Operations Track --------------------

    {
        "rule_id": "CNE_GOAL_Q_001",
        "domain": "CNE",
        "tier": "goal",
        "priority": 290,
        "conditions": [
            {"fact": "networking_theory", "op": ">=", "value": 1},
            {"fact": "lab_access", "op": "==", "value": True},
            {"fact": "hours_per_week", "op": ">=", "value": 8},
            {"fact": "target_outcome", "op": "in",
             "value": ["job", "internship", "freelance"]},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "CNE_GOAL_01",
                "reason": "Meets networking theory, lab access, and time requirements for CCNA",
            },
        ],
    },

    # --- CNE_GOAL_02  Network Security Track ---------------------------

    {
        "rule_id": "CNE_GOAL_Q_002",
        "domain": "CNE",
        "tier": "goal",
        "priority": 280,
        "conditions": [
            {"fact": "prefers_netsec", "op": "==", "value": True},
            {"fact": "networking_theory", "op": ">=", "value": 2},
            {"fact": "lab_access", "op": "==", "value": True},
            {"fact": "hours_per_week", "op": ">=", "value": 10},
            {"fact": "target_outcome", "op": "in",
             "value": ["job", "internship", "freelance"]},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "CNE_GOAL_02",
                "reason": "Meets netsec preference, networking theory, lab, and time requirements",
            },
        ],
    },

    # --- CNE_GOAL_03  Wireless & RF Engineering Track ------------------

    {
        "rule_id": "CNE_GOAL_Q_003",
        "domain": "CNE",
        "tier": "goal",
        "priority": 270,
        "conditions": [
            {"fact": "prefers_wireless", "op": "==", "value": True},
            {"fact": "networking_theory", "op": ">=", "value": 2},
            {"fact": "lab_access", "op": "==", "value": True},
            {"fact": "hours_per_week", "op": ">=", "value": 8},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "CNE_GOAL_03",
                "reason": "Meets wireless preference, networking theory, lab, and time requirements",
            },
        ],
    },

    # --- CNE_GOAL_04  Cloud Networking Track ---------------------------

    {
        "rule_id": "CNE_GOAL_Q_004",
        "domain": "CNE",
        "tier": "goal",
        "priority": 260,
        "conditions": [
            {"fact": "prefers_cloud_net", "op": "==", "value": True},
            {"fact": "networking_theory", "op": ">=", "value": 2},
            {"fact": "linux_skill", "op": ">=", "value": 1},
            {"fact": "weak_internet", "op": "==", "value": False},
            {"fact": "hours_per_week", "op": ">=", "value": 10},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "CNE_GOAL_04",
                "reason": "Meets cloud networking preference, theory, Linux, internet, and time requirements",
            },
        ],
    },

    # --- CNE_GOAL_05  IoT & Edge Networking Track ----------------------

    {
        "rule_id": "CNE_GOAL_Q_005",
        "domain": "CNE",
        "tier": "goal",
        "priority": 250,
        "conditions": [
            {"fact": "prefers_iot", "op": "==", "value": True},
            {"fact": "networking_theory", "op": ">=", "value": 2},
            {"fact": "scripting_skill", "op": ">=", "value": 1},
            {"fact": "hours_per_week", "op": ">=", "value": 8},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "CNE_GOAL_05",
                "reason": "Meets IoT preference, networking theory, scripting, and time requirements",
            },
        ],
    },

    # --- CNE_GOAL_06  Networking Foundations Track --------------------

    {
        "rule_id": "CNE_GOAL_Q_006",
        "domain": "CNE",
        "tier": "goal",
        "priority": 246,
        "conditions": [
            {"fact": "cne_foundation_candidate", "op": "==", "value": True},
            {"fact": "hours_per_week", "op": ">=", "value": 1},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "CNE_GOAL_06",
                "reason": "Your networking direction is valid, and the strongest next step is to build foundations before specializing further",
            },
        ],
    },

    # ===================================================================
    #  GOAL TIER — EXCLUDE  (200–249)
    # ===================================================================

    # --- CNE_GOAL_01  exclusions ---------------------------------------

    {
        "rule_id": "CNE_GOAL_X_001",
        "domain": "CNE",
        "tier": "goal",
        "priority": 249,
        "conditions": [
            {"fact": "prefers_netsec", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_01",
                "reason": "User prefers network security — redirect to CNE_GOAL_02",
            },
        ],
    },

    {
        "rule_id": "CNE_GOAL_X_002",
        "domain": "CNE",
        "tier": "goal",
        "priority": 248,
        "conditions": [
            {"fact": "lab_access", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_01",
                "reason": "Lab or simulator access required for CCNA certification",
            },
        ],
    },

    # --- CNE_GOAL_02  exclusions ---------------------------------------

    {
        "rule_id": "CNE_GOAL_X_003",
        "domain": "CNE",
        "tier": "goal",
        "priority": 247,
        "conditions": [
            {"fact": "prefers_wireless", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_02",
                "reason": "User prefers wireless — redirect to CNE_GOAL_03",
            },
        ],
    },

    {
        "rule_id": "CNE_GOAL_X_004",
        "domain": "CNE",
        "tier": "goal",
        "priority": 246,
        "conditions": [
            {"fact": "networking_theory", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_02",
                "reason": "Network security requires solid networking foundation (requires >= 2)",
            },
        ],
    },

    {
        "rule_id": "CNE_GOAL_X_005",
        "domain": "CNE",
        "tier": "goal",
        "priority": 245,
        "conditions": [
            {"fact": "lab_access", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_02",
                "reason": "Hands-on lab practice mandatory for network security",
            },
        ],
    },

    # --- CNE_GOAL_03  exclusions ---------------------------------------

    {
        "rule_id": "CNE_GOAL_X_006",
        "domain": "CNE",
        "tier": "goal",
        "priority": 244,
        "conditions": [
            {"fact": "networking_theory", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_03",
                "reason": "Insufficient networking foundation for wireless track (requires >= 2)",
            },
        ],
    },

    {
        "rule_id": "CNE_GOAL_X_007",
        "domain": "CNE",
        "tier": "goal",
        "priority": 243,
        "conditions": [
            {"fact": "lab_access", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_03",
                "reason": "RF/Wi-Fi equipment requires lab access",
            },
        ],
    },

    # --- CNE_GOAL_04  exclusions ---------------------------------------

    {
        "rule_id": "CNE_GOAL_X_008",
        "domain": "CNE",
        "tier": "goal",
        "priority": 242,
        "conditions": [
            {"fact": "weak_internet", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_04",
                "reason": "Cloud networking requires a reliable internet connection",
            },
        ],
    },

    {
        "rule_id": "CNE_GOAL_X_009",
        "domain": "CNE",
        "tier": "goal",
        "priority": 241,
        "conditions": [
            {"fact": "linux_skill", "op": "<", "value": 1},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_04",
                "reason": "Linux fundamentals required for cloud networking (requires >= 1)",
            },
        ],
    },

    # --- CNE_GOAL_05  exclusions ---------------------------------------

    {
        "rule_id": "CNE_GOAL_X_010",
        "domain": "CNE",
        "tier": "goal",
        "priority": 240,
        "conditions": [
            {"fact": "scripting_skill", "op": "<", "value": 1},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_05",
                "reason": "IoT requires some scripting for device control (requires >= 1)",
            },
        ],
    },

    {
        "rule_id": "CNE_GOAL_X_011",
        "domain": "CNE",
        "tier": "goal",
        "priority": 239,
        "conditions": [
            {"fact": "hours_per_week", "op": "<", "value": 8},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_01",
                "reason": "Insufficient weekly hours for CCNA track (requires >= 8)",
            },
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_03",
                "reason": "Insufficient weekly hours for Wireless track (requires >= 8)",
            },
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_05",
                "reason": "Insufficient weekly hours for IoT track (requires >= 8)",
            },
        ],
    },

    # ===================================================================
    #  SANITY TIER  (100–199)
    # ===================================================================

    {
        "rule_id": "CNE_SANITY_001",
        "domain": "CNE",
        "tier": "sanity",
        "priority": 190,
        "conditions": [
            {"fact": "lab_access", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_01",
                "reason": "No lab access — CCNA certification requires hands-on practice",
            },
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_02",
                "reason": "No lab access — network security requires hands-on practice",
            },
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_03",
                "reason": "No lab access — wireless engineering requires RF equipment",
            },
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "No lab access — only Cloud Networking and IoT remain viable",
            },
        ],
    },

    {
        "rule_id": "CNE_SANITY_002",
        "domain": "CNE",
        "tier": "sanity",
        "priority": 180,
        "conditions": [
            {"fact": "weak_internet", "op": "==", "value": True},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_04",
                "reason": "Weak internet — cloud networking track not feasible",
            },
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "Weak internet limits cloud-dependent networking tracks",
            },
        ],
    },

    {
        "rule_id": "CNE_SANITY_003",
        "domain": "CNE",
        "tier": "sanity",
        "priority": 170,
        "conditions": [
            {"fact": "hours_per_week", "op": "<", "value": 10},
        ],
        "actions": [
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_02",
                "reason": "Network security track requires >= 10 hrs/week — time insufficient",
            },
            {
                "type": "exclude_goal",
                "goal_id": "CNE_GOAL_04",
                "reason": "Cloud networking track requires >= 10 hrs/week — time insufficient",
            },
        ],
    },

    {
        "rule_id": "CNE_SANITY_004",
        "domain": "CNE",
        "tier": "sanity",
        "priority": 160,
        "conditions": [
            {"fact": "current_level", "op": "==", "value": "beginner"},
            {"fact": "networking_theory", "op": "<", "value": 2},
        ],
        "actions": [
            {
                "type": "add_reason",
                "category": "constraint",
                "text": "Beginner with limited theory — start with CCNA fundamentals first",
            },
        ],
    },

    {
        "rule_id": "CNE_SANITY_005",
        "domain": "CNE",
        "tier": "sanity",
        "priority": 150,
        "conditions": [
            {"fact": "prefers_netsec", "op": "==", "value": False},
            {"fact": "prefers_wireless", "op": "==", "value": False},
            {"fact": "prefers_cloud_net", "op": "==", "value": False},
            {"fact": "prefers_iot", "op": "==", "value": False},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "CNE_GOAL_06",
                "reason": "No specific CNE preference - start with the networking foundations track",
            },
            {
                "type": "add_reason",
                "category": "info",
                "text": "No CNE sub-domain preference detected - using the networking foundations fallback",
            },
        ],
    },

    {
        "rule_id": "CNE_SANITY_006",
        "domain": "CNE",
        "tier": "sanity",
        "priority": 140,
        "conditions": [
            {"fact": "hours_per_week", "op": ">=", "value": 1},
        ],
        "actions": [
            {
                "type": "qualify_goal",
                "goal_id": "CNE_GOAL_06",
                "reason": "Safety-net fallback: every valid CNE interview can start from a networking foundations track",
            },
        ],
    },
]
