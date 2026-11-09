from __future__ import annotations

import hashlib
import inspect
import random
from typing import Callable, Optional

from o2.archive import Archive
from o2.task import MockTask
from o2.types import Direction, Program, RunConfig


def fn_hash(fn: Callable) -> str:
    src = inspect.getsource(fn)
    return hashlib.sha256(src.encode("utf-8")).hexdigest()[:16]


def select(archive: Archive, rng: random.Random) -> Program:
    """Default Drive selector: tournament biased to the current incumbent."""
    programs = archive.all()
    if not programs:
        raise RuntimeError("select() on empty archive")
    if len(programs) == 1:
        return programs[0]
    # Soft monopoly: 70% pick incumbent, otherwise tournament of 3.
    inc = archive.incumbent()
    assert inc is not None
    if rng.random() < 0.70:
        return inc
    sample = rng.sample(programs, k=min(3, len(programs)))
    return max(sample, key=lambda p: p.global_score)


def mutate(
    parent: Program,
    rng: random.Random,
    cfg: RunConfig,
    *,
    focus_seeds: Optional[list[int]] = None,
    sigma: Optional[float] = None,
) -> list[float]:
    """Copy parent genes and perturb one gene. Lease may focus on view seeds."""
    genes = list(parent.genes)
    if focus_seeds:
        gene_idx = focus_seeds[rng.randrange(len(focus_seeds))] % cfg.n_genes
    else:
        gene_idx = rng.randrange(cfg.n_genes)
    step = sigma if sigma is not None else cfg.mutate_sigma
    genes[gene_idx] = min(1.0, max(0.0, genes[gene_idx] + rng.gauss(0.0, step)))
    return genes


def propose_directions(
    parent: Program,
    view: tuple[int, ...],
    rng: random.Random,
    cfg: RunConfig,
    task: MockTask,
) -> list[Direction]:
    """Lease-side verbalized portfolio. Probabilities need not sum to 1."""
    directions: list[Direction] = []
    view_list = list(view) if view else list(range(cfg.n_seeds))
    for i in range(cfg.n_directions):
        named = view_list[i % len(view_list)]
        gap = abs(parent.seed_scores[named] - 100.0)
        # Lower probability marks the less typical direction.
        prob = max(0.05, min(0.95, 0.55 - 0.08 * i + rng.uniform(-0.05, 0.05)))
        directions.append(
            Direction(
                bottleneck=f"seed-{named}-gap={gap:.2f}",
                mechanism=f"nudge-gene-{named % cfg.n_genes}",
                named_seed=named,
                verbalized_probability=prob,
            )
        )
    return directions


def pick_executed_direction(directions: list[Direction]) -> Direction:
    eligible = [d for d in directions]
    return min(eligible, key=lambda d: (d.verbalized_probability, d.named_seed))


def survive(archive: Archive, child: Program) -> None:
    """Append-only survive. Never deletes."""
    archive.add(child)


def evaluate_program(
    genes: list[float],
    task: MockTask,
    *,
    program_id: str,
    parent_id: Optional[str],
    generation: int,
) -> Program:
    scores = task.evaluate(genes)
    return Program(
        id=program_id,
        genes=genes,
        parent_id=parent_id,
        seed_scores=scores,
        global_score=MockTask.aggregate(scores),
        generation=generation,
    )


OPERATOR_FNS = {
    "select": select,
    "mutate": mutate,
    "survive": survive,
}


def operator_hashes() -> dict[str, str]:
    return {name: fn_hash(fn) for name, fn in OPERATOR_FNS.items()}
