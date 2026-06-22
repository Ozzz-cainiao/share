from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class ScenarioEntry:
    name: str
    description: str
    add_arguments: Callable[[argparse.ArgumentParser], None]
    run: Callable[[argparse.Namespace], int]


class UnknownScenarioError(Exception):
    def __init__(self, name: str, available: list[str]) -> None:
        super().__init__(
            f"Unknown scenario: {name}. Available scenarios: {', '.join(available)}"
        )
        self.name = name
        self.available = available


class ScenarioRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, ScenarioEntry] = {}

    def register(self, entry: ScenarioEntry) -> None:
        if entry.name in self._entries:
            raise ValueError(f"scenario already registered: {entry.name}")
        self._entries[entry.name] = entry

    def get(self, name: str) -> ScenarioEntry:
        if name not in self._entries:
            raise UnknownScenarioError(name, self.keys())
        return self._entries[name]

    def keys(self) -> list[str]:
        return sorted(self._entries)

    def entries(self) -> list[ScenarioEntry]:
        return [self._entries[key] for key in self.keys()]


SCENARIO_REGISTRY = ScenarioRegistry()
