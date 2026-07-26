"""
GPES Forward Chaining Engine — Working Memory.

Stores facts with recency tracking. Every set() increments a global
counter so the conflict resolver can prefer rules that depend on
recently-updated facts.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class WorkingMemory:
    """
    In-memory fact store with recency metadata.

    Attributes
    ----------
    _facts : dict[str, Any]
        Current fact values.
    _recency : dict[str, int]
        Per-fact timestamp (monotonically increasing counter).
    _sources : dict[str, str | None]
        Which rule_id last set each fact (None = initial load).
    _counter : int
        Global recency counter.
    """

    def __init__(self, facts: Dict[str, Any] | None = None) -> None:
        self._facts: Dict[str, Any] = {}
        self._recency: Dict[str, int] = {}
        self._sources: Dict[str, Optional[str]] = {}
        self._counter: int = 0

        if facts:
            for k, v in facts.items():
                self.set(k, v, source_rule_id=None)

    # ----- read -----

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value of *key*, or *default* if not present."""
        return self._facts.get(key, default)

    def has(self, key: str) -> bool:
        """Check whether *key* exists in working memory."""
        return key in self._facts

    def get_recency(self, key: str) -> int:
        """Return the recency timestamp for *key* (0 if unknown)."""
        return self._recency.get(key, 0)

    # ----- write -----

    def set(self, key: str, value: Any, source_rule_id: Optional[str] = None) -> None:
        """
        Store or update a fact.

        Parameters
        ----------
        key : str
            Fact name (must match schema).
        value : Any
            Fact value.
        source_rule_id : str | None
            The rule that asserted this fact (None for initial facts).
        """
        self._counter += 1
        self._facts[key] = value
        self._recency[key] = self._counter
        self._sources[key] = source_rule_id

    # ----- export -----

    def export_facts(self) -> Dict[str, Any]:
        """Return a plain dict copy of all facts."""
        return dict(self._facts)

    def export_recency(self) -> Dict[str, int]:
        """Return a copy of the recency map."""
        return dict(self._recency)

    def export_sources(self) -> Dict[str, Optional[str]]:
        """Return a copy of the source-rule map."""
        return dict(self._sources)

    # ----- dunder -----

    def __repr__(self) -> str:
        return f"WorkingMemory(facts={len(self._facts)}, counter={self._counter})"
