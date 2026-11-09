from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class MockTask:
    """
    Multi-seed scoring task that makes mid-run parent monopoly easy to trigger.

    Each seed s is dominated by gene s % n_genes. Easy seeds (first half) have
    soft targets near 0; hard seeds (second half) have targets near 1. A program
    that only climbs the easy half reaches a high mean early and then stalls,
    while archive members that sit closer to the hard half remain useful parents
    for a lease view.
    """

    n_seeds: int
    n_genes: int
    seed: int

    def __post_init__(self) -> None:
        rng = random.Random(self.seed ^ 0xA5A5)
        targets = []
        for s in range(self.n_seeds):
            # Hard seeds live in the upper half of the index space.
            hardness = s / max(1, self.n_seeds - 1)
            base = 0.15 + 0.75 * hardness
            noise = rng.uniform(-0.05, 0.05)
            targets.append(min(1.0, max(0.0, base + noise)))
        object.__setattr__(self, "_targets", tuple(targets))

    @property
    def targets(self) -> tuple[float, ...]:
        return self._targets  # type: ignore[attr-defined]

    def evaluate(self, genes: list[float]) -> list[float]:
        if len(genes) != self.n_genes:
            raise ValueError(f"expected {self.n_genes} genes, got {len(genes)}")
        scores: list[float] = []
        for s, target in enumerate(self.targets):
            g = genes[s % self.n_genes]
            # Soft local peak around the seed target; secondary genes add a small penalty.
            primary = 100.0 * math.exp(-((g - target) ** 2) / 0.08)
            bleed = 0.0
            for j, gj in enumerate(genes):
                if j == s % self.n_genes:
                    continue
                bleed += abs(gj - 0.5) * 1.5
            scores.append(max(0.0, primary - bleed / max(1, self.n_genes - 1)))
        return scores

    @staticmethod
    def aggregate(seed_scores: list[float]) -> float:
        if not seed_scores:
            return 0.0
        return sum(seed_scores) / len(seed_scores)

    def initial_genes(self, rng: random.Random, mode: str = "easy") -> list[float]:
        genes = [rng.uniform(0.0, 0.25) for _ in range(self.n_genes)]
        if mode == "easy":
            # Match the easy half roughly; leave hard half near 0.
            for s in range(self.n_seeds // 2):
                genes[s % self.n_genes] = self.targets[s] + rng.uniform(-0.05, 0.05)
        elif mode == "hard":
            for s in range(self.n_seeds // 2, self.n_seeds):
                genes[s % self.n_genes] = self.targets[s] + rng.uniform(-0.08, 0.08)
        elif mode == "mixed":
            for s in range(self.n_seeds):
                if rng.random() < 0.5:
                    genes[s % self.n_genes] = self.targets[s] + rng.uniform(-0.1, 0.1)
        return [min(1.0, max(0.0, g)) for g in genes]
