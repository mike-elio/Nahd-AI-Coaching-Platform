from __future__ import annotations

import unittest

from core.output_gap_resolution import build_gap_resolution_plan


class TestGapResolutionBankUsage(unittest.TestCase):
    def test_empty_gap_plan_uses_bank_before_internal_fallbacks(self) -> None:
        plan = build_gap_resolution_plan(
            [],
            {"goal_name": "AI Foundations Track", "domain": "AIE"},
            {"current_level": "beginner", "hours_per_week": 12},
        )

        actions = [item["action"] for item in plan]
        self.assertIn(
            "Write Python functions to clean missing values in a pandas DataFrame.",
            actions,
        )
        self.assertNotIn(
            "Practice Python fundamentals with small coding exercises.",
            actions,
        )


if __name__ == "__main__":
    unittest.main()
