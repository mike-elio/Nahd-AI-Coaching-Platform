"""
Tests for the KB Validator.

Covers: valid KB, duplicate IDs, dangling references, unreachable nodes,
loops, invalid fact_key, missing source_citation, pool_pair checks.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from copy import deepcopy

import pytest

from app.expert import KBValidator, ValidationReport


# ---------------------------------------------------------------------------
# Fixtures: minimal valid KB
# ---------------------------------------------------------------------------

VALID_KB = [
    {
        "id": "N_T_001",
        "domain": "SE",
        "level_filter": ["beginner"],
        "type": "boolean",
        "fact_key": "programming_basic",
        "weight": 1,
        "next_if_true": "N_T_002",
        "next_if_false": "END",
        "source_citation": "SWEBOK v3",
        "pool_pair": [
            {"id": "N_T_001a", "text_ar": "سؤال أ", "text_en": "Question A"},
            {"id": "N_T_001b", "text_ar": "سؤال ب", "text_en": "Question B"},
        ],
    },
    {
        "id": "N_T_002",
        "domain": "SE",
        "level_filter": ["beginner", "intermediate"],
        "type": "scale",
        "fact_key": "python_skill",
        "weight": 2,
        "next_if_true": "END",
        "next_if_false": "END",
        "source_citation": "ACM CS 2023",
        "pool_pair": [
            {"id": "N_T_002a", "text_ar": "سؤال أ", "text_en": "Question A"},
            {"id": "N_T_002b", "text_ar": "سؤال ب", "text_en": "Question B"},
        ],
        "scale_min": 0,
        "scale_max": 5,
    },
]


def _write_kb(data, tmpdir: Path) -> Path:
    """Write a KB list to a temp JSON file and return its path."""
    path = tmpdir / "kb.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidKB:
    def test_valid_kb_passes(self, tmpdir):
        path = _write_kb(VALID_KB, tmpdir)
        v = KBValidator(path)
        report = v.validate()
        assert report.is_valid, report.summary()


class TestDuplicateIDs:
    def test_duplicate_id_detected(self, tmpdir):
        kb = deepcopy(VALID_KB)
        kb.append(deepcopy(kb[0]))  # duplicate first node
        path = _write_kb(kb, tmpdir)
        v = KBValidator(path)
        report = v.validate()
        assert not report.is_valid
        assert any("Duplicate" in e for e in report.errors)


class TestDanglingReferences:
    def test_dangling_next_if_true(self, tmpdir):
        kb = deepcopy(VALID_KB)
        kb[0]["next_if_true"] = "NONEXISTENT_NODE"
        path = _write_kb(kb, tmpdir)
        v = KBValidator(path)
        report = v.validate()
        assert not report.is_valid
        assert any("NONEXISTENT_NODE" in e for e in report.errors)

    def test_dangling_next_if_false(self, tmpdir):
        kb = deepcopy(VALID_KB)
        kb[0]["next_if_false"] = "GHOST"
        path = _write_kb(kb, tmpdir)
        v = KBValidator(path)
        report = v.validate()
        assert not report.is_valid
        assert any("GHOST" in e for e in report.errors)


class TestUnreachableNodes:
    def test_unreachable_node_warned(self, tmpdir):
        kb = deepcopy(VALID_KB)
        # Add a node that nothing points to
        kb.append({
            "id": "N_T_ORPHAN",
            "domain": "SE",
            "level_filter": ["beginner"],
            "type": "boolean",
            "fact_key": "programming_basic",
            "weight": 1,
            "next_if_true": "END",
            "next_if_false": "END",
            "source_citation": "Ref",
            "pool_pair": [
                {"id": "N_T_ORPHAN_a", "text_ar": "أ", "text_en": "A"},
                {"id": "N_T_ORPHAN_b", "text_ar": "ب", "text_en": "B"},
            ],
        })
        path = _write_kb(kb, tmpdir)
        v = KBValidator(path)
        report = v.validate()
        assert any("Unreachable" in w and "N_T_ORPHAN" in w for w in report.warnings)


class TestLoopDetection:
    def test_loop_detected(self, tmpdir):
        kb = [
            {
                "id": "A",
                "domain": "SE",
                "level_filter": ["beginner"],
                "type": "boolean",
                "fact_key": "programming_basic",
                "weight": 1,
                "next_if_true": "B",
                "next_if_false": "END",
                "source_citation": "Ref",
                "pool_pair": [
                    {"id": "Aa", "text_ar": "أ", "text_en": "A"},
                    {"id": "Ab", "text_ar": "ب", "text_en": "B"},
                ],
            },
            {
                "id": "B",
                "domain": "SE",
                "level_filter": ["beginner"],
                "type": "boolean",
                "fact_key": "python_skill",
                "weight": 1,
                "next_if_true": "A",  # loop back!
                "next_if_false": "END",
                "source_citation": "Ref",
                "pool_pair": [
                    {"id": "Ba", "text_ar": "أ", "text_en": "A"},
                    {"id": "Bb", "text_ar": "ب", "text_en": "B"},
                ],
            },
        ]
        path = _write_kb(kb, tmpdir)
        v = KBValidator(path)
        report = v.validate()
        assert any("Loop" in e for e in report.errors)


class TestFactKeyValidation:
    def test_invalid_fact_key(self, tmpdir):
        kb = deepcopy(VALID_KB)
        kb[0]["fact_key"] = "totally_unknown_fact_xyz"
        path = _write_kb(kb, tmpdir)
        v = KBValidator(path)
        report = v.validate()
        assert not report.is_valid
        assert any("totally_unknown_fact_xyz" in e for e in report.errors)


class TestSourceCitation:
    def test_empty_citation_rejected_by_pydantic(self, tmpdir):
        kb = deepcopy(VALID_KB)
        kb[0]["source_citation"] = ""
        path = _write_kb(kb, tmpdir)
        v = KBValidator(path)
        report = v.validate()
        assert not report.is_valid  # Pydantic min_length=1 or field_validator


class TestPoolPairSize:
    def test_wrong_pool_size_rejected_by_pydantic(self, tmpdir):
        kb = deepcopy(VALID_KB)
        kb[0]["pool_pair"] = [
            {"id": "x", "text_ar": "أ", "text_en": "A"},
        ]
        path = _write_kb(kb, tmpdir)
        v = KBValidator(path)
        report = v.validate()
        assert not report.is_valid


class TestFileErrors:
    def test_missing_file(self):
        v = KBValidator("nonexistent_file.json")
        report = v.validate()
        assert not report.is_valid
        assert any("not found" in e for e in report.errors)

    def test_invalid_json(self, tmpdir):
        path = tmpdir / "bad.json"
        path.write_text("{broken json", encoding="utf-8")
        v = KBValidator(path)
        report = v.validate()
        assert not report.is_valid
        assert any("Invalid JSON" in e for e in report.errors)


class TestRealQuestionBank:
    """Run the validator against real question bank files if they exist."""

    REAL_FILES = [
        Path(__file__).resolve().parent.parent / "knowledge_base" / "question_bank" / "se_questions.json",
        Path(__file__).resolve().parent.parent / "knowledge_base" / "question_bank" / "ai_questions.json",
        Path(__file__).resolve().parent.parent / "knowledge_base" / "question_bank" / "cn_questions.json",
    ]

    @pytest.mark.parametrize(
        "kb_file",
        REAL_FILES,
        ids=["SE_100q", "AIE_100q", "CNE_100q"],
    )
    def test_real_kb_valid(self, kb_file: Path):
        if not kb_file.exists():
            pytest.skip(f"Real KB file not found: {kb_file}")
        v = KBValidator(kb_file)
        report = v.validate()
        # Report warnings but they shouldn't be errors
        if report.warnings:
            print(f"\nWarnings for {kb_file.name}:")
            for w in report.warnings:
                print(f"  ⚠ {w}")
        assert report.is_valid, report.summary()
