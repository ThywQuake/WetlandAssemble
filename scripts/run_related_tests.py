#!/usr/bin/env python3
"""Infer and optionally run the pytest subset related to changed files."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.test_selection import (  # noqa: E402
    categories_for_paths,
    infer_related_tests,
    iter_test_categories,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Infer the relevant pytest targets for one or more changed repository paths."
    )
    parser.add_argument("paths", nargs="*", help="Changed repo-relative file paths.")
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="Print the curated test families and exit.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run `python -m pytest` on the inferred targets instead of only printing them.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.list_categories:
        for category in iter_test_categories():
            print(f"[{category.key}] {category.description}")
            for test_path in category.tests:
                print(f"  - {test_path}")
        return 0

    if not args.paths:
        print("No paths provided. Pass changed files or use --list-categories.", file=sys.stderr)
        return 2

    matched_categories = categories_for_paths(args.paths)
    tests = infer_related_tests(args.paths)

    if matched_categories:
        print("Matched categories:")
        for category in matched_categories:
            print(f"- {category.key}: {category.description}")
    else:
        print("Matched categories: none")

    if not tests:
        print("No related tests inferred from the provided paths.")
        return 0

    print("Recommended pytest targets:")
    for test_path in tests:
        print(f"- {test_path}")

    if not args.run:
        print("\nSuggested command:")
        print("python -m pytest " + " ".join(tests))
        return 0

    command = [sys.executable, "-m", "pytest", *tests]
    print("\nRunning:")
    print(" ".join(command))
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
