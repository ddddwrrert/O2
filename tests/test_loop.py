from __future__ import annotations

from o2.certify import certify_collapse, warmup_done
from o2.loop import run_drive_only, run_search
from o2.operators import operator_hashes
from o2.types import ProposalRecord, RunConfig


def test_warmup_gate():
    cfg = RunConfig(B=80, warmup_min=20, warmup_frac=0.2)
    assert not warmup_done(10, cfg)
    assert warmup_done(20, cfg)


def test_certify_requires_collapse_not_just_stall():
    cfg = RunConfig(W=4, M=4, rho=0.75)
    stall_only = [
        ProposalRecord(
            eval_index=i,
            parent_id="other",
            child_id=f"c{i}",
            global_score=1.0,
            improved_incumbent=False,
            under_lease=False,
            admitted=True,
        )
        for i in range(4)
    ]
    assert not certify_collapse(stall_only, "inc", cfg)

    collapsed = [
        ProposalRecord(
            eval_index=i,
            parent_id="inc",
            child_id=f"c{i}",
            global_score=1.0,
            improved_incumbent=False,
            under_lease=False,
            admitted=True,
        )
        for i in range(4)
    ]
    assert certify_collapse(collapsed, "inc", cfg)


def test_lease_run_smoke():
    cfg = RunConfig(B=40, seed=2, warmup_min=10, warmup_frac=0.2, W=5, M=5, rho=0.6, K=6)
    report = run_search(cfg)
    assert report.evaluations == 40
    assert report.archive_size >= 3
    assert report.operator_hashes == operator_hashes()
    assert report.final_best >= 0.0


def test_drive_only_never_issues():
    cfg = RunConfig(B=30, seed=3, warmup_min=8)
    report = run_drive_only(cfg)
    assert report.leases_issued == 0
    assert report.evaluations == 30


def test_operator_hashes_stable_across_runs():
    h1 = operator_hashes()
    _ = run_search(RunConfig(B=15, seed=0, warmup_min=5))
    h2 = operator_hashes()
    assert h1 == h2
