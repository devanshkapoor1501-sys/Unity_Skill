"""Stable topological ordering with bounded, iterative cycle detection."""

from __future__ import annotations

import heapq

from polyforge.contracts.validation import InputError


def topological_order(dependencies: dict[str, list[str]]) -> tuple[str, ...]:
    """Return dependency-before-consumer order, independent of declaration order."""
    indegree = {key: len(set(values)) for key, values in dependencies.items()}
    descendants: dict[str, list[str]] = {key: [] for key in dependencies}
    for key, values in dependencies.items():
        for value in set(values):
            if value not in dependencies:
                raise InputError(f"$.dependencies[{key}]: dangling reference {value}")
            descendants[value].append(key)
    ready = [key for key, count in indegree.items() if count == 0]
    heapq.heapify(ready)
    ordered = []
    while ready:
        current = heapq.heappop(ready)
        ordered.append(current)
        for child in sorted(descendants[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(ready, child)
    if len(ordered) != len(dependencies):
        raise InputError("$.dependencies: cycle detected")
    return tuple(ordered)
