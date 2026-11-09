from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional, Union

from o2.archive import Archive
from o2.types import IssueRefusal, Lease, LeaseStatus, Program, RunConfig


@dataclass
class IssueResult:
    lease: Optional[Lease] = None
    refusal: Optional[IssueRefusal] = None


def view_hash(view: tuple[int, ...]) -> str:
    payload = ",".join(str(i) for i in view)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def aggregate_on(program: Program, indices: tuple[int, ...]) -> float:
    if not indices:
        return 0.0
    return sum(program.seed_scores[i] for i in indices) / len(indices)


def compute_gaps(incumbent: Program, archive: Archive) -> list[float]:
    """δ_s = max_{P≠I} score_P(s) - score_I(s). Positive ⇒ archive beats incumbent on s."""
    gaps: list[float] = []
    n = len(incumbent.seed_scores)
    others = list(archive.others(incumbent.id))
    for s in range(n):
        if not others:
            gaps.append(0.0)
            continue
        best_other = max(p.seed_scores[s] for p in others)
        gaps.append(best_other - incumbent.seed_scores[s])
    return gaps


def select_view(gaps: list[float], cfg: RunConfig) -> tuple[int, ...]:
    k = max(cfg.view_k_min, int(round(cfg.view_k_frac * len(gaps))))
    k = min(k, len(gaps))
    ranked = sorted(range(len(gaps)), key=lambda i: (-gaps[i], i))
    chosen = [i for i in ranked[:k] if gaps[i] > 0]
    return tuple(sorted(chosen))


def pick_parent(
    archive: Archive,
    incumbent: Program,
    view: tuple[int, ...],
    cfg: RunConfig,
) -> Union[Program, IssueRefusal]:
    best: Optional[Program] = None
    best_agg = float("-inf")
    for p in archive.others(incumbent.id):
        agg = aggregate_on(p, view)
        if agg > best_agg or (agg == best_agg and best is not None and p.id < best.id):
            best = p
            best_agg = agg
    if best is None:
        return IssueRefusal("no_margin", "archive has no non-incumbent programs")
    inc_agg = aggregate_on(incumbent, view)
    if best_agg < inc_agg + cfg.gamma:
        return IssueRefusal(
            "no_margin",
            f"best_view_agg={best_agg:.4f} incumbent_view_agg={inc_agg:.4f} gamma={cfg.gamma}",
        )
    return best


def compute_budget(cfg: RunConfig, B_remaining: int, view_size: int) -> int:
    by_frac = int(cfg.budget_frac * B_remaining)
    by_view = 2 + view_size
    return min(cfg.K, by_frac, by_view)


def try_issue_lease(
    *,
    archive: Archive,
    cfg: RunConfig,
    B_remaining: int,
    eval_index: int,
    closed_keys: set[tuple[str, str]],
    lease_counter: int,
) -> IssueResult:
    incumbent = archive.incumbent()
    if incumbent is None:
        return IssueResult(refusal=IssueRefusal("no_margin", "empty archive"))

    gaps = compute_gaps(incumbent, archive)
    view = select_view(gaps, cfg)
    if not view:
        return IssueResult(refusal=IssueRefusal("empty_gap", "no seed where archive beats incumbent"))

    parent_or_refuse = pick_parent(archive, incumbent, view, cfg)
    if isinstance(parent_or_refuse, IssueRefusal):
        return IssueResult(refusal=parent_or_refuse)
    parent = parent_or_refuse

    key = (parent.id, view_hash(view))
    if key in closed_keys:
        return IssueResult(refusal=IssueRefusal("no_renew", f"already closed {key}"))

    budget = compute_budget(cfg, B_remaining, len(view))
    if budget < 2:
        return IssueResult(
            refusal=IssueRefusal("budget_too_small", f"budget={budget} B_remaining={B_remaining}")
        )

    lease = Lease(
        id=f"lease-{lease_counter}",
        parent_id=parent.id,
        view=view,
        view_hash=key[1],
        budget_left=budget,
        budget_total=budget,
        status=LeaseStatus.OPEN,
        issued_at=eval_index,
        view_best=aggregate_on(parent, view),
    )
    return IssueResult(lease=lease)
