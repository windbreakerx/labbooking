#!/usr/bin/env python3
"""Backward-compatible wrapper for metallurgy department parser."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from department_workload_parser import DEPARTMENTS, main, parse_workbook_file

if __name__ == "__main__":
    if len(sys.argv) == 1:
        default = Path(r"d:/Users/Mayorov_IV/Downloads/Кафедра 23 Металлургии.xlsx")
        if default.is_file():
            parse_workbook_file(default, DEPARTMENTS["met"])
            raise SystemExit(0)
    raise SystemExit(main())
