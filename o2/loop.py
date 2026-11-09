from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Optional

from o2.archive import Archive
from o2.certify import certify_collapse, warmup_done
from o2.issue import aggregate_on, try_issue_lease
from o2.operators import (
    evaluate_program,
    mutate,
    operator_hashes,
    pick_executed_direction,
    propose_directions,
    select,
    survive,
)
from o2.task import MockTask
from o2.types import (
    Lease,
    LeaseStatus,
    ProposalRecord,
    RunConfig,
    RunReport,
)


def _seed_archive(task: MockTask, cfg: RunConfig, rng: random.Random) -> Archive:
    archive = Archive()
    # Easy specialist becomes early incumbent under monopoly select.
    easy = evaluate_program(
        task.initial_genes(rng, "easy"),
        task,
        program_id="P0",
        parent_id=None,
        generation=0,
    )
    hard = evaluate_program(
        task.initial_genes(rng, "hard"),
        task,
        program_id="P1",
        parent_id=None,
        generation=0,
    )
    mixed = evaluate_program(
        task.initial_genes(rng, "mixed"),
        task,
        program_id="P2",
        parent_id=None,
        generation=0,
    )
    for p in (easy, hard, mixed):
        archive.add(p)
    return archive


def _admit_under_lease(
    child,
    incumbent,
    parent,
    view: tuple[int, ...],
    noise: float = 0.0,
) -> tuple[bool, float, bool]:
    trio = [incumbent, parent, child]
    view_scores = {p.id: aggregate_on(p, view) for p in trio}
    best_id = max(view_scores, key=lambda i: (view_scores[i], i == child.id))
    credit_best = best_id == child.id
    complement = tuple(i for i in range(len(child.seed_scores)) if i not in view)
    child_c = aggregate_on(child, complement) if complement else 0.0
    inc_c = aggregate_on(incumbent, complement) if complement else 0.0
    complement_ok = child_c + 1e-12 >= inc_c - noise
    return credit_best and complement_ok, view_scores[child.id], complement_ok


def run_search(cfg: Optional[RunConfig] = None, *, log_dir: Optional[Path] = None) -> RunReport:
    cfg = cfg or RunConfig()
    rng = random.Random(cfg.seed)
    task = MockTask(n_seeds=cfg.n_seeds, n_genes=cfg.n_genes, seed=cfg.seed)
    archive = _seed_archive(task, cfg, rng)

    history: list[ProposalRecord] = []
    incumbent_curve: list[float] = []
    open_lease: Optional[Lease] = None
    closed_keys: set[tuple[str, str]] = set()
    refuse_counts: Counter[str] = Counter()
    close_counts: Counter[str] = Counter()
    certify_triggers = 0
    leases_issued = 0
    best_at_first_certify: Optional[float] = None
    hashes_start = operator_hashes()
    next_id = 3

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "events.jsonl"
        log_fh = log_path.open("w", encoding="utf-8")
    else:
        log_fh = None

    def log_event(obj: dict) -> None:
        if log_fh is not None:
            log_fh.write(json.dumps(obj, ensure_ascii=False) + "\n")

    evaluations = 0
    while evaluations < cfg.B:
        incumbent = archive.incumbent()
        assert incumbent is not None
        close_reason: Optional[str] = None
        under_lease = open_lease is not None and open_lease.status == LeaseStatus.OPEN

        if not under_lease:
            # Drive
            parent = select(archive, rng)
            genes = mutate(parent, rng, cfg)
            child = evaluate_program(
                genes,
                task,
                program_id=f"P{next_id}",
                parent_id=parent.id,
                generation=evaluations + 1,
            )
            next_id += 1
            evaluations += 1
            prev_best = incumbent.global_score
            survive(archive, child)
            new_inc = archive.incumbent()
            assert new_inc is not None
            improved = new_inc.global_score > prev_best + 1e-12
            admitted = True
            view_agg = None
            complement_ok = True

            rec = ProposalRecord(
                eval_index=evaluations,
                parent_id=parent.id,
                child_id=child.id,
                global_score=child.global_score,
                improved_incumbent=improved,
                under_lease=False,
                admitted=admitted,
            )
            history.append(rec)
            incumbent_curve.append(new_inc.global_score)
            log_event({"phase": "drive", **rec.__dict__})

            # Certify after Drive step
            if warmup_done(evaluations, cfg) and certify_collapse(history, new_inc.id, cfg):
                certify_triggers += 1
                if best_at_first_certify is None:
                    best_at_first_certify = new_inc.global_score
                B_remaining = cfg.B - evaluations
                result = try_issue_lease(
                    archive=archive,
                    cfg=cfg,
                    B_remaining=B_remaining,
                    eval_index=evaluations,
                    closed_keys=closed_keys,
                    lease_counter=leases_issued + 1,
                )
                if result.lease is not None:
                    open_lease = result.lease
                    leases_issued += 1
                    log_event(
                        {
                            "phase": "issue",
                            "lease_id": open_lease.id,
                            "parent_id": open_lease.parent_id,
                            "view": list(open_lease.view),
                            "budget": open_lease.budget_total,
                        }
                    )
                else:
                    assert result.refusal is not None
                    refuse_counts[result.refusal.reason] += 1
                    log_event(
                        {
                            "phase": "issue_refused",
                            "reason": result.refusal.reason,
                            "detail": result.refusal.detail,
                        }
                    )
            continue

        # Lease step
        assert open_lease is not None
        parent = archive.get(open_lease.parent_id)
        incumbent = archive.incumbent()
        assert incumbent is not None

        if cfg.use_verbalized:
            directions = propose_directions(parent, open_lease.view, rng, cfg, task)
            executed = pick_executed_direction(directions)
            open_lease.directions = directions
            open_lease.executed = executed
            focus = [executed.named_seed]
        else:
            open_lease.directions = []
            open_lease.executed = None
            focus = list(open_lease.view)

        genes = mutate(
            parent,
            rng,
            cfg,
            focus_seeds=focus,
            sigma=cfg.lease_sigma,
        )
        child = evaluate_program(
            genes,
            task,
            program_id=f"P{next_id}",
            parent_id=parent.id,
            generation=evaluations + 1,
        )
        next_id += 1
        evaluations += 1

        admitted, view_agg, complement_ok = _admit_under_lease(
            child, incumbent, parent, open_lease.view
        )
        prev_best = incumbent.global_score
        if admitted:
            survive(archive, child)
        new_inc = archive.incumbent()
        assert new_inc is not None
        improved = new_inc.global_score > prev_best + 1e-12

        # Track view progress for early expiry
        if view_agg > open_lease.view_best + 1e-12:
            open_lease.view_best = view_agg
            open_lease.flat_streak = 0
        else:
            open_lease.flat_streak += 1

        open_lease.budget_left -= 1
        if open_lease.budget_left <= 0:
            close_reason = "quota"
            open_lease.status = LeaseStatus.EXPIRED
        elif open_lease.flat_streak >= cfg.lease_flat_window:
            close_reason = "view_flat"
            open_lease.status = LeaseStatus.RETURNED

        rec = ProposalRecord(
            eval_index=evaluations,
            parent_id=parent.id,
            child_id=child.id,
            global_score=child.global_score,
            improved_incumbent=improved,
            under_lease=True,
            admitted=admitted,
            view_agg=view_agg,
            complement_ok=complement_ok,
            close_reason=close_reason,
        )
        history.append(rec)
        incumbent_curve.append(new_inc.global_score)
        log_event(
            {
                "phase": "lease",
                "lease_id": open_lease.id,
                "admitted": admitted,
                "view": list(open_lease.view),
                "budget_left": open_lease.budget_left,
                **{k: getattr(rec, k) for k in (
                    "eval_index",
                    "parent_id",
                    "child_id",
                    "global_score",
                    "improved_incumbent",
                    "view_agg",
                    "complement_ok",
                    "close_reason",
                )},
            }
        )

        if open_lease.status != LeaseStatus.OPEN:
            closed_keys.add((open_lease.parent_id, open_lease.view_hash))
            close_counts[close_reason or "returned"] += 1
            log_event(
                {
                    "phase": "return",
                    "lease_id": open_lease.id,
                    "reason": close_reason,
                    "closed_key": [open_lease.parent_id, open_lease.view_hash],
                }
            )
            open_lease = None

    hashes_end = operator_hashes()
    if hashes_start != hashes_end:
        raise RuntimeError(f"operator identity changed: {hashes_start} -> {hashes_end}")

    final = archive.incumbent()
    assert final is not None
    post_delta = None
    if best_at_first_certify is not None:
        post_delta = final.global_score - best_at_first_certify

    report = RunReport(
        config=cfg,
        evaluations=evaluations,
        final_best=final.global_score,
        best_at_first_certify=best_at_first_certify,
        post_certify_delta=post_delta,
        certify_triggers=certify_triggers,
        leases_issued=leases_issued,
        leases_refused=dict(refuse_counts),
        close_reasons=dict(close_counts),
        archive_size=len(archive),
        operator_hashes=hashes_end,
        history=history,
        incumbent_curve=incumbent_curve,
    )

    if log_fh is not None:
        summary_path = Path(log_dir) / "summary.json"  # type: ignore[arg-type]
        summary_path.write_text(
            json.dumps(
                {
                    "final_best": report.final_best,
                    "best_at_first_certify": report.best_at_first_certify,
                    "post_certify_delta": report.post_certify_delta,
                    "certify_triggers": report.certify_triggers,
                    "leases_issued": report.leases_issued,
                    "leases_refused": report.leases_refused,
                    "close_reasons": report.close_reasons,
                    "archive_size": report.archive_size,
                    "operator_hashes": report.operator_hashes,
                    "evaluations": report.evaluations,
                    "seed": cfg.seed,
                    "B": cfg.B,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        log_fh.close()

    return report


def run_drive_only(cfg: Optional[RunConfig] = None) -> RunReport:
    """Ablation: never issue leases (certify disabled by huge rho)."""
    from dataclasses import replace

    cfg = cfg or RunConfig()
    blocked = replace(cfg, rho=2.0)
    return run_search(blocked)
