"""Question-bank validation for the GPES expert system."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.models import QuestionNode, get_all_valid_fact_keys


class ValidationReport:
    """Accumulates errors and warnings for a knowledge base."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def summary(self) -> str:
        lines: list[str] = []
        if self.errors:
            lines.append(f"ERRORS ({len(self.errors)}):")
            lines.extend(f"  - {item}" for item in self.errors)
        if self.warnings:
            lines.append(f"WARNINGS ({len(self.warnings)}):")
            lines.extend(f"  - {item}" for item in self.warnings)
        if self.is_valid and not self.warnings:
            lines.append("Knowledge base is valid.")
        return "\n".join(lines)


class KBValidator:
    """Validates a question-bank JSON file against app models and schema rules."""

    SENTINEL = "END"

    def __init__(self, kb_path: str | Path) -> None:
        self.kb_path = Path(kb_path)
        self.raw_data: list[dict[str, Any]] = []
        self.nodes: list[QuestionNode] = []
        self.node_map: dict[str, QuestionNode] = {}
        self.report = ValidationReport()

    def validate(self) -> ValidationReport:
        self._load_json()
        if not self.report.is_valid:
            return self.report

        self._parse_nodes()
        if not self.report.is_valid:
            return self.report

        self._check_duplicate_ids()
        self._check_dangling_references()
        self._check_unreachable_nodes()
        self._check_loops()
        self._check_fact_keys()
        self._check_pool_pair_size()
        self._check_source_citation()
        return self.report

    def _load_json(self) -> None:
        if not self.kb_path.exists():
            self.report.add_error(f"File not found: {self.kb_path}")
            return
        try:
            with open(self.kb_path, encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            self.report.add_error(f"Invalid JSON: {exc}")
            return
        if not isinstance(data, list):
            self.report.add_error("JSON root must be an array of question nodes")
            return
        self.raw_data = data

    def _parse_nodes(self) -> None:
        for index, item in enumerate(self.raw_data):
            try:
                node = QuestionNode.model_validate(item)
            except ValidationError as exc:
                node_id = item.get("id", f"<index {index}>")
                self.report.add_error(f"Node '{node_id}' failed validation: {exc}")
                continue
            self.nodes.append(node)
            self.node_map[node.id] = node

    def _check_duplicate_ids(self) -> None:
        seen: dict[str, int] = defaultdict(int)
        for node in self.nodes:
            seen[node.id] += 1
        for node_id, count in seen.items():
            if count > 1:
                self.report.add_error(f"Duplicate node ID: '{node_id}' appears {count} times")

    def _check_dangling_references(self) -> None:
        valid_ids = set(self.node_map) | {self.SENTINEL}
        for node in self.nodes:
            if node.next_if_true not in valid_ids:
                self.report.add_error(
                    f"Node '{node.id}': next_if_true='{node.next_if_true}' is unknown"
                )
            if node.next_if_false not in valid_ids:
                self.report.add_error(
                    f"Node '{node.id}': next_if_false='{node.next_if_false}' is unknown"
                )

    def _check_unreachable_nodes(self) -> None:
        if not self.nodes:
            return
        reachable: set[str] = set()
        stack = [self.nodes[0].id]
        while stack:
            node_id = stack.pop()
            if node_id in reachable or node_id == self.SENTINEL:
                continue
            reachable.add(node_id)
            node = self.node_map.get(node_id)
            if node is None:
                continue
            stack.append(node.next_if_true)
            stack.append(node.next_if_false)
        for node_id in sorted(set(self.node_map) - reachable):
            self.report.add_warning(f"Unreachable node: '{node_id}'")

    def _check_loops(self) -> None:
        white, gray, black = 0, 1, 2
        color = {node_id: white for node_id in self.node_map}
        path: list[str] = []

        def visit(node_id: str) -> None:
            if node_id == self.SENTINEL or node_id not in self.node_map:
                return
            if color[node_id] == gray:
                cycle_start = path.index(node_id)
                cycle = path[cycle_start:] + [node_id]
                self.report.add_error(f"Loop detected: {' -> '.join(cycle)}")
                return
            if color[node_id] == black:
                return
            color[node_id] = gray
            path.append(node_id)
            node = self.node_map[node_id]
            visit(node.next_if_true)
            visit(node.next_if_false)
            path.pop()
            color[node_id] = black

        for node_id in self.node_map:
            if color[node_id] == white:
                visit(node_id)

    def _check_fact_keys(self) -> None:
        valid_keys = get_all_valid_fact_keys()
        for node in self.nodes:
            if node.fact_key not in valid_keys:
                self.report.add_error(
                    f"Node '{node.id}': fact_key='{node.fact_key}' is not in the facts schema"
                )

    def _check_pool_pair_size(self) -> None:
        for node in self.nodes:
            if len(node.pool_pair) != 2:
                self.report.add_error(
                    f"Node '{node.id}': pool_pair has {len(node.pool_pair)} items (expected 2)"
                )

    def _check_source_citation(self) -> None:
        for node in self.nodes:
            if not node.source_citation or not node.source_citation.strip():
                self.report.add_error(f"Node '{node.id}': missing source_citation")


__all__ = ["KBValidator", "ValidationReport"]
