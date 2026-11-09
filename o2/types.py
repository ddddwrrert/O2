from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LeaseStatus(str, Enum):
    OPEN = "open"
    RETURNED = "returned"
    EXPIRED = "expired"


@dataclass(frozen=True)
class RunConfig:
    """Budget and certify / issue knobs. Defaults match the O2 proposal."""

    B: int = 80
    n_seeds: int = 12
    n_genes: int = 12
    warmup_frac: float = 0.2
    warmup_min: int = 20
    W: int = 8
    M: int = 8
    rho: float = 0.75
    view_k_frac: float = 0.25
    view_k_min: int = 3
    gamma: float = 1.0
    K: int = 8
    budget_frac: float = 0.1
    lease_flat_window: int = 3
    seed: int = 0
    task_name: str = "mock_gap"
    # mutation
    mutate_sigma: float = 0.35
    lease_sigma: float = 0.55
    # verbalized directions (lease step); set False to ablate
    use_verbalized: bool = True
    n_directions: int = 4


@dataclass
class Program:
    id: str
    genes: list[float]
    parent_id: Optional[str]
    seed_scores: list[float]
    global_score: float
    generation: int


@dataclass
class Direction:
    bottleneck: str
    mechanism: str
    named_seed: int
    verbalized_probability: float


@dataclass
class Lease:
    id: str
    parent_id: str
    view: tuple[int, ...]
    view_hash: str
    budget_left: int
    budget_total: int
    directions: list[Direction] = field(default_factory=list)
    executed: Optional[Direction] = None
    status: LeaseStatus = LeaseStatus.OPEN
    issued_at: int = 0
    view_best: float = float("-inf")
    flat_streak: int = 0


@dataclass
class ProposalRecord:
    eval_index: int
    parent_id: str
    child_id: str
    global_score: float
    improved_incumbent: bool
    under_lease: bool
    admitted: bool
    view_agg: Optional[float] = None
    complement_ok: bool = True
    close_reason: Optional[str] = None


@dataclass
class IssueRefusal:
    reason: str
    detail: str = ""


@dataclass
class RunReport:
    config: RunConfig
    evaluations: int
    final_best: float
    best_at_first_certify: Optional[float]
    post_certify_delta: Optional[float]
    certify_triggers: int
    leases_issued: int
    leases_refused: dict[str, int]
    close_reasons: dict[str, int]
    archive_size: int
    operator_hashes: dict[str, str]
    history: list[ProposalRecord] = field(default_factory=list)
    incumbent_curve: list[float] = field(default_factory=list)
