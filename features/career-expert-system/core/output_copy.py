"""Gap copy text helpers for GPES output formatting."""

from __future__ import annotations

from typing import Any

from app.models import AIE_FACTS, CNE_FACTS, SE_FACTS, UNIVERSAL_FACTS
from core.output_specs import FACT_LABEL_OVERRIDES


_ALL_FACT_TYPES: dict[str, str] = {
    **UNIVERSAL_FACTS,
    **SE_FACTS,
    **AIE_FACTS,
    **CNE_FACTS,
}


def gap_copy(fact_key: str, actual: Any, expected: Any) -> tuple[str, str]:
    actual_display = _format_fact_value(fact_key, actual)
    expected_display = _format_fact_value(fact_key, expected)
    if fact_key == "programming_basic":
        return (
            "You still need the basics of coding syntax and very small scripts.",
            "Start with variables, conditions, loops, functions, and very small scripts.",
        )
    if fact_key == "basics_control_flow":
        return (
            "You still need stronger logic flow with conditions, loops, and functions.",
            "Practice short exercises on conditions, loops, and function flow.",
        )
    if fact_key == "api_concepts":
        return (
            "You still need the basics of HTTP requests, responses, and APIs.",
            "Review HTTP methods, status codes, and simple request-response exercises.",
        )
    if fact_key == "db_modeling_skill":
        return (
            f"Your database modeling is still early at about {actual_display}.",
            "Practice simple ERDs and table design on small examples.",
        )
    if fact_key == "input_validation":
        return (
            "You still need more practice validating user input and requests.",
            "Add validation to one small form or API endpoint.",
        )
    if fact_key == "backend_testing":
        return (
            "You still need practice checking backend behavior with tests.",
            "Write a few request-and-response tests for one small API.",
        )
    if fact_key == "web_basics":
        return (
            f"Your HTML, CSS, and JavaScript basics are still early at about {actual_display}.",
            "Strengthen HTML, CSS, and core JavaScript through a few small page builds.",
        )
    if fact_key == "js_skill":
        return (
            f"Your JavaScript level is still early at about {actual_display}.",
            "Build JavaScript basics through syntax, DOM, and small interaction exercises.",
        )
    if fact_key == "dom_events":
        return (
            "You still need practice with interactive page behavior.",
            "Build one small page with click, input, and submit interactions.",
        )
    if fact_key == "http_client_basics":
        return (
            "You still need the basics of sending requests from the browser and handling responses.",
            "Practice fetch, JSON parsing, and simple loading and error states.",
        )
    if fact_key == "ui_accessibility":
        return (
            "Accessibility is not yet part of your current frontend workflow.",
            "Review one page for semantic HTML, keyboard access, and clear labels.",
        )
    if fact_key == "version_control_git":
        return (
            "You still need a stable basic Git workflow.",
            "Practice creating commits, branches, and merges on one small project.",
        )
    if fact_key == "python_skill_basic":
        return (
            "You still need the basic building blocks of Python.",
            "Work through Python variables, conditions, loops, and functions.",
        )
    if fact_key == "any_programming_experience":
        return (
            "You still need more real coding practice before moving deeper.",
            "Complete a batch of very small coding exercises before the next step.",
        )
    if fact_key == "python_skill":
        return (
            f"Your Python level is still below the starting level this track expects at about {actual_display}.",
            "Raise Python through syntax practice, functions, files, and small scripts.",
        )
    if fact_key == "math_skill":
        return (
            f"Your math foundation is still early at about {actual_display}.",
            "Review algebra, probability, and basic statistics before moving deeper.",
        )
    if fact_key == "ml_exposure":
        return (
            f"Your exposure to machine learning is still limited at about {actual_display}.",
            "Complete one simple end-to-end machine learning workflow.",
        )
    if fact_key == "data_handling":
        return (
            f"Your data handling practice is still limited at about {actual_display}.",
            "Practice loading, cleaning, and splitting small datasets.",
        )
    if fact_key == "networking_basic":
        return (
            "You still need the basic language and concepts of networking.",
            "Review TCP/IP, switching, routing, and packet flow.",
        )
    if fact_key == "osi_layers_basic":
        return (
            "You still need stronger layer-based troubleshooting.",
            "Map common protocols and failures to the OSI layers.",
        )
    if fact_key == "ip_subnetting_basic":
        return (
            "You still need more comfort with addressing and subnetting.",
            "Practice subnetting drills until the patterns become easier.",
        )
    if fact_key == "linux_cli_net_tools_skill":
        return (
            f"Your Linux networking-tool practice is still early at about {actual_display}.",
            "Practice ping, traceroute, ip, ss, and tcpdump on small troubleshooting tasks.",
        )
    if fact_key == "networking_theory":
        return (
            f"Your networking theory is still below the level this track expects at about {actual_display}.",
            "Review routing, VLANs, and basic troubleshooting before moving on.",
        )
    if fact_key == "lab_access":
        return (
            "You still need a hands-on environment for network practice.",
            "Set up Packet Tracer, GNS3, or another simple lab environment.",
        )
    if fact_key == "cisco_tools":
        return (
            f"Your Cisco tool practice is still early at about {actual_display}.",
            "Practice basic Cisco CLI navigation and starter configurations.",
        )
    if fact_key == "scripting_skill":
        return (
            f"Your scripting practice is still early at about {actual_display}.",
            "Automate a few small network tasks in Python or Bash.",
        )
    if fact_key == "sql_skill":
        return (
            f"Your SQL level is still early at about {actual_display}.",
            "Practice SELECT, JOIN, GROUP BY, and simple schema work.",
        )
    if fact_key == "linux_skill":
        return (
            f"Your Linux level is still early at about {actual_display}.",
            "Practice file navigation, processes, permissions, and package management.",
        )
    if fact_key == "containers_basics":
        return (
            "You still need the basics of working with containers.",
            "Build and run one small Docker image.",
        )
    if fact_key == "ci_basics":
        return (
            "You still need the basics of automated validation.",
            "Add one simple pipeline that runs tests or linting.",
        )
    if fact_key == "cloud_basics":
        return (
            "You still need the core ideas behind cloud deployment.",
            "Review compute, storage, networking, and deployment basics.",
        )
    if fact_key == "security_mindset":
        return (
            "You still need stronger security thinking around how systems can be abused.",
            "Review common attack surfaces and simple abuse cases.",
        )
    if fact_key == "owasp_awareness":
        return (
            "You still need more familiarity with common web vulnerabilities.",
            "Study the OWASP Top 10 at a practical overview level.",
        )
    if fact_key == "secure_coding":
        return (
            "Defensive coding habits are not stable yet.",
            "Refactor one small app with stronger validation, auth checks, and safer defaults.",
        )
    if fact_key == "data_pipeline_basics":
        return (
            "You still need the basics of moving data from one step to another.",
            "Build one small extract-transform-load script.",
        )
    if fact_key == "data_quality_awareness":
        return (
            "You still need stronger habits for checking data quality.",
            "Add null, duplication, and schema checks to one dataset.",
        )
    if fact_key == "hours_per_week":
        return (
            "Your weekly study time is still lower than this path usually needs.",
            "Protect a steadier weekly study block before pushing into a heavier track.",
        )
    if fact_key == "weak_device":
        return (
            "Your current device may limit heavier tools and labs.",
            "Use lighter tooling, cloud options, or another machine when needed.",
        )
    if fact_key == "weak_internet":
        return (
            "Your connection may make cloud-heavy work harder.",
            "Prepare offline resources or local labs whenever possible.",
        )
    if fact_key == "pressure_load":
        return (
            "Your current workload may make steady study harder.",
            "Reduce the weekly scope or extend the timeline for a while.",
        )
    if fact_key == "english_level":
        return (
            "English-first technical resources may still feel a bit heavy for you.",
            "Read short English technical material regularly alongside your main study.",
        )
    if fact_key == "problem_solving":
        return (
            f"Your problem-solving level is still early at about {actual_display}.",
            "Solve short debugging and logic exercises more regularly.",
        )
    return (
        f"Your {_fact_label(fact_key)} still needs more work before the next step.",
        f"Spend focused practice time improving {_fact_label(fact_key)}.",
    )


def _fact_label(fact_key: str) -> str:
    if fact_key in FACT_LABEL_OVERRIDES:
        return FACT_LABEL_OVERRIDES[fact_key]
    words = fact_key.split("_")
    replacements = {
        "api": "API",
        "apis": "APIs",
        "js": "JavaScript",
        "sql": "SQL",
        "ml": "ML",
        "nlp": "NLP",
        "cv": "computer vision",
        "cli": "CLI",
        "erd": "ERD",
        "http": "HTTP",
        "osi": "OSI",
        "tcp": "TCP",
        "ip": "IP",
        "ui": "UI",
        "git": "Git",
        "owasp": "OWASP",
    }
    rendered: list[str] = []
    for word in words:
        rendered.append(replacements.get(word, word))
    label = " ".join(rendered)
    label = label.replace("prefers ", "")
    return label


def _format_fact_value(fact_key: str, value: Any) -> str:
    if value is None:
        return "missing"
    fact_type = _ALL_FACT_TYPES.get(fact_key, "")
    if fact_type.startswith("scale"):
        numeric = _number(value)
        return f"{_format_number(numeric)}/5" if numeric is not None else str(value)
    if fact_key == "hours_per_week":
        numeric = _number(value)
        return _format_number(numeric) if numeric is not None else str(value)
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def _format_number(value: Any) -> str:
    numeric = _number(value)
    if numeric is None:
        return str(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}".rstrip("0").rstrip(".")


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _join_text(parts: list[str], *, conjunction: str) -> str:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} {conjunction} {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, {conjunction} {cleaned[-1]}"


def _natural_scale(value: Any) -> str:
    return f"{_format_number(value)} out of 5"


def _sentence_case(text: str) -> str:
    if not text:
        return text
    return text[:1].upper() + text[1:]


def _strip_trailing_period(text: str) -> str:
    return text.rstrip().rstrip(".")


def _take_unique_strings(items: list[str], limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = (item or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result
