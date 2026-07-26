"""
GPES Expert System — Interactive CLI Runner.

Usage
-----
Interactive interview with domain prompt:

    python tools/run_expert.py

Interactive interview with a preselected domain:

    python tools/run_expert.py --domain SE

Direct run with a custom facts JSON file:

    python tools/run_expert.py --domain SE --facts path/to/facts.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.expert import create_session
from core.inference_engine import InferenceEngine
from core.output_formatter import build_final_output, render_console_summary
from core.rules_loader import load_rules

_SUPPORTED_DOMAINS = ("SE", "AIE", "CNE")
_DOMAIN_LABELS = {
    "SE": "Software Engineering",
    "AIE": "AI Engineering",
    "CNE": "Communication Networks Engineering",
}
_QUESTION_BANK_FILES = {
    "SE": _PROJECT_ROOT / "knowledge_base" / "question_bank" / "se_questions.json",
    "AIE": _PROJECT_ROOT / "knowledge_base" / "question_bank" / "ai_questions.json",
    "CNE": _PROJECT_ROOT / "knowledge_base" / "question_bank" / "cn_questions.json",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GPES Expert System — CLI runner")
    parser.add_argument(
        "--domain",
        default=None,
        choices=_SUPPORTED_DOMAINS,
        help="Expert system domain. If omitted, the CLI prompts for it.",
    )
    parser.add_argument(
        "--facts",
        default=None,
        metavar="FILE",
        help="Path to a JSON file containing user facts. Skips the interview.",
    )
    return parser.parse_args()


def _load_facts(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise TypeError(
            f"Facts file must contain a JSON object (dict), got {type(data).__name__}."
        )
    return data


def _normalize_domain(value: str) -> str:
    domain = value.strip().upper()
    if domain not in _SUPPORTED_DOMAINS:
        raise ValueError(f"Unsupported domain '{value}'. Expected SE, AIE, or CNE.")
    return domain


def _prompt_domain() -> str:
    print("Select a domain:")
    for index, domain in enumerate(_SUPPORTED_DOMAINS, start=1):
        print(f"  {index}. {_DOMAIN_LABELS[domain]} ({domain})")

    while True:
        raw = input("Enter domain number or code: ").strip()
        if raw.isdigit():
            position = int(raw) - 1
            if 0 <= position < len(_SUPPORTED_DOMAINS):
                return _SUPPORTED_DOMAINS[position]
        try:
            return _normalize_domain(raw)
        except ValueError:
            print("Invalid domain. Please choose 1, 2, 3, or enter SE/AIE/CNE.")


def _question_bank_path(domain: str) -> Path:
    return _QUESTION_BANK_FILES[domain]


def _parse_boolean_input(raw: str) -> bool:
    normalized = raw.strip().lower()
    truthy = {"y", "yes", "true", "1"}
    falsy = {"n", "no", "false", "0"}
    if normalized in truthy:
        return True
    if normalized in falsy:
        return False
    raise ValueError("Please enter yes/no, y/n, true/false, or 1/0.")


def _parse_numeric_input(raw: str, *, as_int: bool) -> int | float:
    text = raw.strip()
    if not text:
        raise ValueError("Input cannot be empty.")
    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError("Please enter a valid number.") from exc

    if as_int:
        if not value.is_integer():
            raise ValueError("Please enter a whole number.")
        return int(value)
    return int(value) if value.is_integer() else value


def _ensure_range(value: int | float, *, minimum: int | None, maximum: int | None) -> None:
    if minimum is not None and value < minimum:
        raise ValueError(f"Please enter a value greater than or equal to {minimum}.")
    if maximum is not None and value > maximum:
        raise ValueError(f"Please enter a value less than or equal to {maximum}.")


def _match_choice(raw: str, choices: list[str]) -> str:
    text = raw.strip()
    if not text:
        raise ValueError("Input cannot be empty.")
    if text.isdigit():
        position = int(text) - 1
        if 0 <= position < len(choices):
            return choices[position]
    lowered = text.casefold()
    for choice in choices:
        if choice.casefold() == lowered:
            return choice
    raise ValueError("Please select a valid option number or exact option text.")


def _parse_multi_choice_input(raw: str, choices: list[str]) -> list[str]:
    tokens = [token.strip() for token in raw.split(",") if token.strip()]
    if not tokens:
        raise ValueError("Please enter at least one option.")

    selected: list[str] = []
    for token in tokens:
        choice = _match_choice(token, choices)
        if choice not in selected:
            selected.append(choice)
    return selected


def _render_choices(choices: Iterable[str]) -> None:
    for index, choice in enumerate(choices, start=1):
        print(f"  {index}. {choice}")


def _prompt_for_answer(question: dict[str, Any]) -> Any:
    qtype = question["type"]
    while True:
        try:
            if qtype == "boolean":
                return _parse_boolean_input(input("Answer [y/n]: "))

            if qtype == "scale":
                minimum = question.get("scale_min")
                maximum = question.get("scale_max")
                prompt = f"Answer [{minimum}-{maximum}]: "
                value = _parse_numeric_input(input(prompt), as_int=True)
                _ensure_range(value, minimum=minimum, maximum=maximum)
                return value

            if qtype == "numeric":
                return _parse_numeric_input(input("Answer: "), as_int=False)

            if qtype == "choice":
                choices = question.get("choices_en") or []
                _render_choices(choices)
                return _match_choice(input("Choose one option: "), choices)

            if qtype == "multi_choice":
                choices = question.get("choices_en") or []
                _render_choices(choices)
                return _parse_multi_choice_input(
                    input("Choose one or more options (comma-separated): "),
                    choices,
                )

            return input("Answer: ").strip()
        except ValueError as exc:
            print(f"Invalid input: {exc}")


def _collect_interview_facts(domain: str) -> dict[str, Any]:
    kb_path = _question_bank_path(domain)
    manager, session = create_session(kb_path, domain)

    print(f"\nStarting {_DOMAIN_LABELS[domain]} interview.\n")

    while not session.is_finished:
        question = manager.get_current_question()
        if question is None:
            break

        question_number = len(session.history) + 1
        print(f"Question {question_number}: {question['text_en']}")
        answer = _prompt_for_answer(question)
        manager.submit_answer(answer)
        print("")

    print("Interview completed.\n")
    return session.facts


def _run_expert(domain: str, facts: dict[str, Any]) -> dict[str, Any]:
    print(f"[run_expert] Loading rules for domain '{domain}' ...")
    rules = load_rules(domain)
    print(f"[run_expert] {len(rules)} rules loaded.")

    print("[run_expert] Running inference engine ...")
    fc_result = InferenceEngine.run(domain, facts, rules)
    print(f"[run_expert] Engine finished - {fc_result['steps']} rule(s) fired.")

    return build_final_output(domain, facts, fc_result)


def main() -> None:
    args = _parse_args()
    domain = _normalize_domain(args.domain) if args.domain else _prompt_domain()

    if args.facts:
        print(f"[run_expert] Loading facts from: {args.facts}")
        facts = _load_facts(args.facts)
    else:
        facts = _collect_interview_facts(domain)

    final_output = _run_expert(domain, facts)
    print(render_console_summary(final_output))


if __name__ == "__main__":
    main()
