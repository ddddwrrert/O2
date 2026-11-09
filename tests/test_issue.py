from __future__ import annotations

import random

from o2.archive import Archive
from o2.issue import compute_gaps, select_view, try_issue_lease, view_hash
from o2.operators import evaluate_program
from o2.task import MockTask
from o2.types import RunConfig


def _archive_with_gap(seed: int = 1) -> tuple[Archive, RunConfig]:
    cfg = RunConfig(seed=seed, n_seeds=12, n_genes=12, gamma=0.5)
    task = MockTask(cfg.n_seeds, cfg.n_genes, cfg.seed)
    rng = random.Random(seed)
    archive = Archive()
    easy = evaluate_program(
        task.initial_genes(rng, "easy"), task, program_id="P0", parent_id=None, generation=0
    )
    hard = evaluate_program(
        task.initial_genes(rng, "hard"), task, program_id="P1", parent_id=None, generation=0
    )
    archive.add(easy)
    archive.add(hard)
    return archive, cfg


def test_gaps_positive_where_hard_beats_easy():
    archive, cfg = _archive_with_gap()
    inc = archive.incumbent()
    assert inc is not None
    gaps = compute_gaps(inc, archive)
    view = select_view(gaps, cfg)
    assert len(view) >= 1
    assert all(gaps[i] > 0 for i in view)


def test_issue_and_no_renew():
    archive, cfg = _archive_with_gap()
    first = try_issue_lease(
        archive=archive,
        cfg=cfg,
        B_remaining=50,
        eval_index=30,
        closed_keys=set(),
        lease_counter=1,
    )
    assert first.lease is not None
    key = (first.lease.parent_id, first.lease.view_hash)
    assert key[1] == view_hash(first.lease.view)

    second = try_issue_lease(
        archive=archive,
        cfg=cfg,
        B_remaining=50,
        eval_index=40,
        closed_keys={key},
        lease_counter=2,
    )
    assert second.lease is None
    assert second.refusal is not None
    assert second.refusal.reason == "no_renew"


def test_budget_too_small():
    archive, cfg = _archive_with_gap()
    result = try_issue_lease(
        archive=archive,
        cfg=cfg,
        B_remaining=1,
        eval_index=30,
        closed_keys=set(),
        lease_counter=1,
    )
    assert result.lease is None
    assert result.refusal is not None
    assert result.refusal.reason == "budget_too_small"
