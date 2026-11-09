"""O2 — lease-gated search against mid-run stagnation."""

__version__ = "0.1.0"

from o2.loop import run_search
from o2.types import RunConfig, RunReport

__all__ = ["__version__", "run_search", "RunConfig", "RunReport"]
