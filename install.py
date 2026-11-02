#!/usr/bin/env python3
"""Usage: python install.py /path/to/another/repository"""
import sys

sys.dont_write_bytecode = True
from optmm.cli import main

if __name__ == '__main__':
    raise SystemExit(main(['install', *sys.argv[1:]]))
