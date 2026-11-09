from __future__ import annotations

from o2.types import ProposalRecord, RunConfig


def warmup_done(evaluations: int, cfg: RunConfig) -> bool:
    need = max(cfg.warmup_min, int(cfg.warmup_frac * cfg.B))
    return evaluations >= need


def certify_collapse(history: list[ProposalRecord], incumbent_id: str, cfg: RunConfig) -> bool:
    """
    Dual certificate:
      (1) last W evals: global incumbent did not improve
      (2) last M proposals: fraction with parent == incumbent >= rho
    Stall alone is not enough.
    """
    if len(history) < max(cfg.W, cfg.M):
        return False

    recent_w = history[-cfg.W :]
    if any(r.improved_incumbent for r in recent_w):
        return False

    recent_m = history[-cfg.M :]
    same_parent = sum(1 for r in recent_m if r.parent_id == incumbent_id)
    return (same_parent / len(recent_m)) >= cfg.rho
