#!/usr/bin/env python3
"""CLI: parse department workload Excel files into draft CSV catalogs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from department_workload_parser import main

if __name__ == "__main__":
    raise SystemExit(main())
