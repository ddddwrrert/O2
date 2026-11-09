from __future__ import annotations

from typing import Iterable, Optional

from o2.types import Program


class Archive:
    """Append-only program archive."""

    def __init__(self) -> None:
        self._by_id: dict[str, Program] = {}
        self._order: list[str] = []

    def __len__(self) -> int:
        return len(self._order)

    def add(self, program: Program) -> None:
        if program.id in self._by_id:
            raise ValueError(f"program id already in archive: {program.id}")
        self._by_id[program.id] = program
        self._order.append(program.id)

    def get(self, program_id: str) -> Program:
        return self._by_id[program_id]

    def __contains__(self, program_id: str) -> bool:
        return program_id in self._by_id

    def all(self) -> list[Program]:
        return [self._by_id[i] for i in self._order]

    def incumbent(self) -> Optional[Program]:
        programs = self.all()
        if not programs:
            return None
        return max(programs, key=lambda p: (p.global_score, -p.generation, p.id))

    def others(self, exclude_id: str) -> Iterable[Program]:
        for p in self.all():
            if p.id != exclude_id:
                yield p
