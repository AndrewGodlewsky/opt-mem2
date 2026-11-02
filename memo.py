#!/usr/bin/env python3
"""Run OptMM directly from this checkout; no package installation required."""
import sys

sys.dont_write_bytecode = True
from optmm.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
