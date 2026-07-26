from app.repositories.references import load_reference_rows
from app.rules.reference_scoring import (
    _resolve_reference_context,
    _resolve_visible_domain,
    choose_reference_for_step,
    _build_references_summary,
    _supplement_references_summary,
)
from app.rules.text_processing import collapse_whitespace


def _step_text(step: dict) -> str:
    return collapse_whitespace(
        " ".join(
            str(step.get(key, ""))
            for key in (
                "semantic_key",
                "title",
                "action",
                "expected_result",
                "expected",
                "if_failed",
                "if_this_fails",
                "reference_hint",
            )
        )
    ).lower()


def _reference_text(row: dict) -> str:
    return collapse_whitespace(
        " ".join(
            str(row.get(key, ""))
            for key in ("title", "tag", "domain", "source_type", "url")
        )
    ).lower()


def _find_better_reference_for_step(
    step: dict,
    selected_reference: dict,
    reference_rows: list[dict],
    selected_urls: set,
) -> dict:
    text = _step_text(step)
    selected_text = _reference_text(selected_reference)

    is_redis_step = (
        "redis" in text
        or "cache_session" in text
        or "session store" in text
        or "cache state" in text
        or "ttl" in text
        or "failover" in text
    )
    selected_is_jwt = (
        "jwt" in selected_text
        or "json web token" in selected_text
        or selected_reference.get("tag") == "jwt"
    )

    if not is_redis_step or not selected_is_jwt:
        return selected_reference

    preferred_terms = ("redis", "cache", "session", "ttl", "persistence", "replication")
    candidates = []
    for row in reference_rows:
        if row.get("url") in selected_urls:
            continue
        row_text = _reference_text(row)
        score = sum(1 for term in preferred_terms if term in row_text)
        if score > 0:
            candidates.append((score, row))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    return selected_reference


def attach_step_references(case_context: dict, diagnostic_checklist: list[dict]) -> dict:
    stage_context, case_summary = _resolve_reference_context(case_context)
    if not isinstance(diagnostic_checklist, list) or not diagnostic_checklist:
        raise ValueError("diagnostic_checklist must be a non-empty list.")

    domain = _resolve_visible_domain(case_summary)
    reference_rows = load_reference_rows(domain)
    allowed_urls = {row["url"] for row in reference_rows}
    enriched_steps = []
    trace_entries = []
    selected_urls = set()
    selected_tags = set()

    for step in diagnostic_checklist:
        if not isinstance(step, dict):
            raise ValueError("diagnostic_checklist contains a non-dictionary step.")

        selected_reference, trace = choose_reference_for_step(
            stage_context,
            step,
            reference_rows,
            used_urls=selected_urls,
            used_tags=selected_tags,
        )

        selected_reference = _find_better_reference_for_step(
            step,
            selected_reference,
            reference_rows,
            selected_urls,
        )

        reference_label = collapse_whitespace(selected_reference["title"])
        reference_url = collapse_whitespace(selected_reference["url"])
        reference_source_type = selected_reference["source_type"]

        if not reference_label or not reference_url or reference_url not in allowed_urls:
            raise ValueError(f"Invalid reference selection for checklist step '{step.get('title', '')}'.")

        enriched_step = {
            **step,
            "reference_label": reference_label,
            "reference_url": reference_url,
            "reference_source_type": reference_source_type,
        }
        enriched_steps.append(enriched_step)
        selected_urls.add(reference_url)
        if selected_reference["tag"]:
            selected_tags.add(selected_reference["tag"])
        trace_entries.append(
            {
                "step_number": int(step.get("step", len(trace_entries) + 1)),
                "step_title": collapse_whitespace(step.get("title", "")),
                "selected_reference": {
                    "title": reference_label,
                    "url": reference_url,
                    "source_type": reference_source_type,
                    "tag": selected_reference["tag"],
                },
                "selected_score": trace["selected_score"],
                "selection_reason_summary": trace["reasons"],
                "semantic_key": trace["profile"]["semantic_key"],
                "anchor_tag": trace["profile"]["anchor_tag"],
                "primary_issue_family": trace["profile"]["primary_issue_family"],
                "selected_reasoning_cluster": trace["profile"]["selected_reasoning_cluster"],
                "boundary_names": trace["profile"]["boundary_names"],
            }
        )

    references_summary = _build_references_summary(trace_entries)
    references_summary = _supplement_references_summary(
        domain=domain,
        summary=references_summary,
        trace_entries=trace_entries,
        reference_rows=reference_rows,
    )

    return {
        "diagnostic_checklist": enriched_steps,
        "references_summary": references_summary,
        "reference_trace_internal": {
            "steps": trace_entries,
        },
        "reference_selection_metadata": {
            "domain": domain,
            "step_count": len(enriched_steps),
            "summary_count": len(references_summary),
            "selection_rule": "step-aware, stack-aware, boundary-aware reference selection",
        },
    }


__all__ = [
    "attach_step_references",
]