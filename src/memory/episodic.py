"""
Episodic memory — short-term, session-scoped storage.
Implemented as an ordered dict to preserve insertion sequence,
which matters for conversation replay and audit narration.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any


class EpisodicMemory:
    """
    In-process episodic memory with optional capacity cap.
    Evicts oldest entries (LRU-style) when capacity is exceeded.
    """

    def __init__(self, max_entries: int = 500) -> None:
        self._store: OrderedDict[str, Any] = OrderedDict()
        self._max = max_entries

    def set(self, key: str, value: Any) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = value
        if len(self._store) > self._max:
            self._store.popitem(last=False)  # evict oldest

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def all(self) -> dict[str, Any]:
        return dict(self._store)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)