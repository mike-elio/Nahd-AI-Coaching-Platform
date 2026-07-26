"""
GPES Forward Chaining Engine — Rules Loader.

Imports the RULES list from the appropriate domain module under
knowledge_base/rules/.
"""

from __future__ import annotations

from typing import List


def load_rules(domain: str) -> List[dict]:
    """
    Load and return the RULES list for *domain* (SE | AIE | CNE).

    Raises
    ------
    ValueError
        If the domain is not recognized.
    ImportError
        If the rules module cannot be imported.
    """
    domain = domain.upper()

    if domain == "SE":
        from knowledge_base.rules.rules_se import RULES
    elif domain == "AIE":
        from knowledge_base.rules.rules_ai import RULES
    elif domain == "CNE":
        from knowledge_base.rules.rules_cn import RULES
    else:
        raise ValueError(
            f"Unknown domain '{domain}'. Expected SE, AIE, or CNE."
        )

    return RULES
