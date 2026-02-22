"""CLI entry point for registry validation.

Usage::

    uv run python -m awos_recruitment_mcp.validate [--format human|json] [--registry-path PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from awos_recruitment_mcp.validate import validate_registry


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the AWOS Recruitment registry.",
    )
    parser.add_argument(
        "--format",
        choices=["human", "json"],
        default="human",
        help="Output format (default: human)",
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=Path("../registry"),
        help="Path to the registry directory (default: ../registry)",
    )
    return parser


def main() -> None:
    """Parse arguments, run validation, and print results."""

    args = _build_parser().parse_args()
    registry_path: Path = args.registry_path.resolve()

    results = validate_registry(registry_path)

    if args.format == "json":
        print("JSON output will be implemented in Slice 3.")
        sys.exit(0)

    # Human-readable output.
    total_entries = len(results)
    failed_files = 0
    total_errors = 0

    for result in results:
        if result.valid:
            print(f"OK    {result.file}")
        else:
            failed_files += 1
            total_errors += len(result.errors)
            print(f"FAIL  {result.file}")
            for error in result.errors:
                print(f"  - {error.message}")

    print()
    if total_errors > 0:
        print(f"{total_errors} errors in {failed_files} files. Validation failed.")
        sys.exit(1)
    else:
        print(f"All {total_entries} entries valid.")
        sys.exit(0)


if __name__ == "__main__":
    main()
