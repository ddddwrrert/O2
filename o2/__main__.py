from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from o2.loop import run_drive_only, run_search
from o2.types import RunConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="o2",
        description="O2 lease search: Drive → Certify → Lease → Return",
    )
    p.add_argument("--B", type=int, default=80, help="official evaluation budget")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n-seeds", type=int, default=12)
    p.add_argument("--n-genes", type=int, default=12)
    p.add_argument("--mode", choices=["lease", "drive"], default="lease")
    p.add_argument("--no-verbalized", action="store_true")
    p.add_argument("--out", type=Path, default=Path("runs/latest"))
    p.add_argument("--json", action="store_true", help="print summary JSON to stdout")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = RunConfig(
        B=args.B,
        seed=args.seed,
        n_seeds=args.n_seeds,
        n_genes=args.n_genes,
        use_verbalized=not args.no_verbalized,
    )
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    if args.mode == "drive":
        report = run_drive_only(cfg)
        # drive_only mutates rho; restore reported config label
        report = replace(report, config=cfg)
    else:
        report = run_search(cfg, log_dir=out)

    summary = {
        "mode": args.mode,
        "seed": cfg.seed,
        "B": cfg.B,
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
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"O2 mode={args.mode} seed={cfg.seed} B={cfg.B}")
        print(f"  final_best          = {report.final_best:.4f}")
        print(f"  certify_triggers    = {report.certify_triggers}")
        print(f"  leases_issued       = {report.leases_issued}")
        print(f"  leases_refused      = {report.leases_refused}")
        print(f"  close_reasons       = {report.close_reasons}")
        print(f"  post_certify_delta  = {report.post_certify_delta}")
        print(f"  archive_size        = {report.archive_size}")
        print(f"  wrote               = {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
