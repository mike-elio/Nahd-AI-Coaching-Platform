# Rules Build Report

Generated: 2026-03-02  
Source of truth: `app/models.py` (Facts Schema) + `gpes_plan.md` (architecture)

---

## 1) Rule Count Summary

| Domain | Profile | Goal (Qualify) | Goal (Exclude) | Sanity | **Total** |
|--------|---------|----------------|----------------|--------|-----------|
| SE     | 5       | 5              | 10             | 5      | **25**    |
| AIE    | 5       | 5              | 12             | 5      | **27**    |
| CNE    | 5       | 5              | 11             | 5      | **26**    |
| **All**| **15**  | **15**         | **33**         | **15** | **78**    |

---

## 2) Facts Compatibility Check

All facts used in `goals_*.json` were checked against `app/models.py`.

| Fact | Found in models.py? |
|------|---------------------|
| `prefers_backend` | ✅ SE_FACTS |
| `prefers_frontend` | ✅ SE_FACTS |
| `prefers_devops` | ✅ SE_FACTS |
| `prefers_security` | ✅ SE_FACTS |
| `python_skill` | ✅ SE_FACTS / AIE_FACTS |
| `js_skill` | ✅ SE_FACTS |
| `sql_skill` | ✅ SE_FACTS |
| `problem_solving` | ✅ SE_FACTS |
| `linux_skill` | ✅ SE_FACTS / CNE_FACTS |
| `math_tolerance` | ✅ SE_FACTS |
| `prefers_ml` | ✅ AIE_FACTS |
| `prefers_cv` | ✅ AIE_FACTS |
| `prefers_nlp` | ✅ AIE_FACTS |
| `prefers_data_eng` | ✅ AIE_FACTS |
| `research_interest` | ✅ AIE_FACTS |
| `math_skill` | ✅ AIE_FACTS |
| `ml_exposure` | ✅ AIE_FACTS |
| `data_handling` | ✅ AIE_FACTS |
| `networking_theory` | ✅ CNE_FACTS |
| `cisco_tools` | ✅ CNE_FACTS |
| `scripting_skill` | ✅ CNE_FACTS |
| `prefers_netsec` | ✅ CNE_FACTS |
| `prefers_wireless` | ✅ CNE_FACTS |
| `prefers_cloud_net` | ✅ CNE_FACTS |
| `prefers_iot` | ✅ CNE_FACTS |
| `lab_access` | ✅ CNE_FACTS |
| `user_type` | ✅ UNIVERSAL_FACTS |
| `current_level` | ✅ UNIVERSAL_FACTS |
| `hours_per_week` | ✅ UNIVERSAL_FACTS |
| `target_outcome` | ✅ UNIVERSAL_FACTS |
| `weak_device` | ✅ UNIVERSAL_FACTS |
| `weak_internet` | ✅ UNIVERSAL_FACTS |
| `pressure_load` | ✅ UNIVERSAL_FACTS |
| `english_level` | ✅ UNIVERSAL_FACTS |

**Missing facts: 0** — All facts used in rules exist in `app/models.py`.

---

## 3) Rule → Goal Mapping

### SE Domain

| Rule ID | Tier | Goal(s) Affected | Action Type |
|---------|------|-------------------|-------------|
| SE_PROFILE_001 | profile | — | add_reason (weakness) |
| SE_PROFILE_002 | profile | — | add_reason (strength) |
| SE_PROFILE_003 | profile | — | add_reason (constraint) |
| SE_PROFILE_004 | profile | — | add_reason (constraint) |
| SE_PROFILE_005 | profile | — | add_reason (strength) |
| SE_GOAL_Q_001 | goal | SE_GOAL_01 | qualify_goal |
| SE_GOAL_Q_002 | goal | SE_GOAL_02 | qualify_goal |
| SE_GOAL_Q_003 | goal | SE_GOAL_03 | qualify_goal |
| SE_GOAL_Q_004 | goal | SE_GOAL_04 | qualify_goal |
| SE_GOAL_Q_005 | goal | SE_GOAL_05 | qualify_goal |
| SE_GOAL_X_001 | goal | SE_GOAL_01 | exclude_goal |
| SE_GOAL_X_002 | goal | SE_GOAL_01 | exclude_goal |
| SE_GOAL_X_003 | goal | SE_GOAL_02 | exclude_goal |
| SE_GOAL_X_004 | goal | SE_GOAL_02 | exclude_goal |
| SE_GOAL_X_005 | goal | SE_GOAL_03 | exclude_goal |
| SE_GOAL_X_006 | goal | SE_GOAL_03 | exclude_goal |
| SE_GOAL_X_007 | goal | SE_GOAL_04 | exclude_goal |
| SE_GOAL_X_008 | goal | SE_GOAL_05 | exclude_goal |
| SE_GOAL_X_009 | goal | SE_GOAL_05 | exclude_goal |
| SE_GOAL_X_010 | goal | SE_GOAL_01/02/05 | exclude_goal |
| SE_SANITY_001 | sanity | SE_GOAL_03/04 | exclude_goal |
| SE_SANITY_002 | sanity | SE_GOAL_03 | exclude_goal + add_reason |
| SE_SANITY_003 | sanity | SE_GOAL_05 | qualify_goal (fallback) |
| SE_SANITY_004 | sanity | — | add_reason (constraint) |
| SE_SANITY_005 | sanity | — | add_reason (constraint) |

### AIE Domain

| Rule ID | Tier | Goal(s) Affected | Action Type |
|---------|------|-------------------|-------------|
| AIE_PROFILE_001 | profile | — | add_reason (strength) |
| AIE_PROFILE_002 | profile | — | add_reason (weakness) |
| AIE_PROFILE_003 | profile | — | add_reason (constraint) |
| AIE_PROFILE_004 | profile | — | add_reason (constraint) |
| AIE_PROFILE_005 | profile | — | add_reason (strength) |
| AIE_GOAL_Q_001 | goal | AIE_GOAL_01 | qualify_goal |
| AIE_GOAL_Q_002 | goal | AIE_GOAL_02 | qualify_goal |
| AIE_GOAL_Q_003 | goal | AIE_GOAL_03 | qualify_goal |
| AIE_GOAL_Q_004 | goal | AIE_GOAL_04 | qualify_goal |
| AIE_GOAL_Q_005 | goal | AIE_GOAL_05 | qualify_goal |
| AIE_GOAL_X_001 | goal | AIE_GOAL_01 | exclude_goal |
| AIE_GOAL_X_002 | goal | AIE_GOAL_01 | exclude_goal |
| AIE_GOAL_X_003 | goal | AIE_GOAL_01 | exclude_goal |
| AIE_GOAL_X_004 | goal | AIE_GOAL_02 | exclude_goal |
| AIE_GOAL_X_005 | goal | AIE_GOAL_02 | exclude_goal |
| AIE_GOAL_X_006 | goal | AIE_GOAL_02 | exclude_goal |
| AIE_GOAL_X_007 | goal | AIE_GOAL_03 | exclude_goal |
| AIE_GOAL_X_008 | goal | AIE_GOAL_03 | exclude_goal |
| AIE_GOAL_X_009 | goal | AIE_GOAL_04 | exclude_goal |
| AIE_GOAL_X_010 | goal | AIE_GOAL_05 | exclude_goal |
| AIE_GOAL_X_011 | goal | AIE_GOAL_05 | exclude_goal |
| AIE_GOAL_X_012 | goal | AIE_GOAL_01/02/03 | exclude_goal |
| AIE_SANITY_001 | sanity | AIE_GOAL_01/02 | exclude_goal + add_reason |
| AIE_SANITY_002 | sanity | AIE_GOAL_03/05 | exclude_goal + add_reason |
| AIE_SANITY_003 | sanity | AIE_GOAL_05 | exclude_goal |
| AIE_SANITY_004 | sanity | — | add_reason (constraint) |
| AIE_SANITY_005 | sanity | — | add_reason (constraint) |

### CNE Domain

| Rule ID | Tier | Goal(s) Affected | Action Type |
|---------|------|-------------------|-------------|
| CNE_PROFILE_001 | profile | — | add_reason (strength) |
| CNE_PROFILE_002 | profile | — | add_reason (weakness) |
| CNE_PROFILE_003 | profile | — | add_reason (constraint) |
| CNE_PROFILE_004 | profile | — | add_reason (constraint) |
| CNE_PROFILE_005 | profile | — | add_reason (constraint) |
| CNE_GOAL_Q_001 | goal | CNE_GOAL_01 | qualify_goal |
| CNE_GOAL_Q_002 | goal | CNE_GOAL_02 | qualify_goal |
| CNE_GOAL_Q_003 | goal | CNE_GOAL_03 | qualify_goal |
| CNE_GOAL_Q_004 | goal | CNE_GOAL_04 | qualify_goal |
| CNE_GOAL_Q_005 | goal | CNE_GOAL_05 | qualify_goal |
| CNE_GOAL_X_001 | goal | CNE_GOAL_01 | exclude_goal |
| CNE_GOAL_X_002 | goal | CNE_GOAL_01 | exclude_goal |
| CNE_GOAL_X_003 | goal | CNE_GOAL_02 | exclude_goal |
| CNE_GOAL_X_004 | goal | CNE_GOAL_02 | exclude_goal |
| CNE_GOAL_X_005 | goal | CNE_GOAL_02 | exclude_goal |
| CNE_GOAL_X_006 | goal | CNE_GOAL_03 | exclude_goal |
| CNE_GOAL_X_007 | goal | CNE_GOAL_03 | exclude_goal |
| CNE_GOAL_X_008 | goal | CNE_GOAL_04 | exclude_goal |
| CNE_GOAL_X_009 | goal | CNE_GOAL_04 | exclude_goal |
| CNE_GOAL_X_010 | goal | CNE_GOAL_05 | exclude_goal |
| CNE_GOAL_X_011 | goal | CNE_GOAL_01/03/05 | exclude_goal |
| CNE_SANITY_001 | sanity | CNE_GOAL_01/02/03 | exclude_goal + add_reason |
| CNE_SANITY_002 | sanity | CNE_GOAL_04 | exclude_goal + add_reason |
| CNE_SANITY_003 | sanity | CNE_GOAL_02/04 | exclude_goal |
| CNE_SANITY_004 | sanity | — | add_reason (constraint) |
| CNE_SANITY_005 | sanity | CNE_GOAL_01 | qualify_goal (fallback) |

---

## 4) Alignment with gpes_plan.md

### Tiers
The three-tier design follows `gpes_plan.md` §7:

| Tier | Purpose | Priority Range | When |
|------|---------|----------------|------|
| **Profile** | Characterise user (strengths, weaknesses, constraints) | 300–399 | Fires first |
| **Goal** | Qualify or exclude specific goals based on eligibility/disqualifiers | 200–299 | Fires second |
| **Sanity** | Final overrides — scope reduction for device/time/internet constraints | 100–199 | Fires last |

### Forward Chaining
- Rules are evaluated in **priority-descending** order (highest first).
- Each rule's `conditions` list is evaluated as an implicit **AND**.
- If all conditions match, all `actions` fire.
- The engine accumulates **qualify_goal**, **exclude_goal**, and **add_reason** actions into a working memory.
- An **exclude** always overrides a **qualify** for the same goal (as per `gpes_plan.md` conflict resolution).

### Action Types
| Action | Effect |
|--------|--------|
| `qualify_goal` | Marks a goal as eligible; includes a human-readable `reason` |
| `exclude_goal` | Marks a goal as excluded (overrides qualify); includes `reason` |
| `add_reason` | Appends a note to the user's profile (`strength`, `weakness`, `constraint`, `info`) |

### Conflict Resolution
- Within the same goal: **exclude wins over qualify** (defensive strategy).
- Across goals: independent — each goal is evaluated separately.
- Sanity tier runs last and can override Goal tier decisions for resource constraints.
