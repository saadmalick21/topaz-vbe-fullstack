"""CLI: roll a Topaz-VBE quarter from the command line.

Usage (cwd = ~/workspace/topaz-vbe/engine):
    python -m topaz_engine.cli --industry 1 --year 1 --quarter 3
"""
from __future__ import annotations

import argparse
import json
import sys

from topaz_engine.runner import run_quarter


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Roll a Topaz-VBE quarter: simulate all active teams, "
        "publish reports, and audit the roll."
    )
    parser.add_argument("--industry", type=int, required=True, help="Industry id")
    parser.add_argument("--year", type=int, required=True, help="Simulation year")
    parser.add_argument("--quarter", type=int, required=True, help="Quarter (1-4)")
    args = parser.parse_args(argv)

    result = run_quarter(args.industry, args.year, args.quarter)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
