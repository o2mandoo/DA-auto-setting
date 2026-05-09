#!/usr/bin/env python3
"""Clone-ready setup helper.

This helper stays intentionally small: it validates that the repository ships
the expected placeholder files, can copy `.env.example` to `.env`, and prints
the canonical local setup commands from the docs/Makefile flow.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = ROOT / ".env.example"
ENV_FILE = ROOT / ".env"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bootstrap")
    parser.add_argument("--copy-env", action="store_true", help="Copy .env.example to .env if .env is missing.")
    parser.add_argument("--check-only", action="store_true", help="Validate setup files without copying anything.")
    args = parser.parse_args(argv)

    if not ENV_EXAMPLE.exists():
        raise FileNotFoundError(".env.example is missing; the clone-ready setup docs expect it to exist")

    if args.copy_env:
        if ENV_FILE.exists():
            print(".env already exists; leaving it unchanged")
        else:
            shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
            print("created .env from .env.example")

    print("setup-ready")
    print("next: make setup")
    print("next: make env-check")
    print("next: make demo")
    print("next: python3 scripts/demo/run_local_demo.py")

    if args.check_only:
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
