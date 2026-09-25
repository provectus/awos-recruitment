"""CLI entry point for registry validation.

Usage::

    uv run python -m awos_recruitment_mcp.validate [--format human|json|github]
        [--registry-path PATH] [--strict] [--summary PATH]

Errors always fail the run. Warnings (skill-quality findings) are reported
and only fail it under ``--strict``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

from awos_recruitment_mcp.validate import (
    ValidationError,
    ValidationResult,
    validate_registry,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the AWOS Recruitment registry.",
    )
    parser.add_argument(
        "--format",
        choices=["human", "json", "github"],
        default="human",
        help=(
            "Output format (default: human). 'github' prints workflow "
            "annotations so findings show inline on the PR."
        ),
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=Path("../registry"),
        help="Path to the registry directory (default: ../registry)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warnings as well as errors.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help=(
            "Append a markdown summary (counts per rule and per entry) to "
            "this file, e.g. $GITHUB_STEP_SUMMARY."
        ),
    )
    return parser


def _location(issue: ValidationError) -> str:
    return f"{issue.file}:{issue.line}" if issue.line else issue.file


def _issue_dict(issue: ValidationError) -> dict[str, object]:
    return {
        "file": issue.file,
        "field": issue.field,
        "message": issue.message,
        "severity": issue.severity,
        "rule": issue.rule,
        "line": issue.line,
    }


def _escape_annotation(text: str) -> str:
    # Workflow-command escaping for the message part.
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(text: str) -> str:
    return _escape_annotation(text).replace(":", "%3A").replace(",", "%2C")


def _print_github(results: list[ValidationResult], registry_path: Path) -> None:
    """Print ``::error``/``::warning`` workflow commands, one per finding."""

    # Annotations need repo-relative paths; the workflow runs from server/.
    base = Path(os.environ.get("GITHUB_WORKSPACE", Path.cwd()))
    for result in results:
        for issue in [*result.errors, *result.warnings]:
            path = os.path.relpath(registry_path / issue.file, base)
            props = [f"file={_escape_property(path)}"]
            if issue.line:
                props.append(f"line={issue.line}")
            props.append(f"title={_escape_property(issue.rule or 'schema')}")
            print(
                f"::{issue.severity} {','.join(props)}::"
                f"{_escape_annotation(issue.message)}"
            )


def _markdown_summary(results: list[ValidationResult], failed: bool) -> str:
    errors = [e for r in results for e in r.errors]
    warnings = [w for r in results for w in r.warnings]

    lines = [
        "## Registry validation",
        "",
        (
            f"**{'Failed' if failed else 'Passed'}** — {len(results)} entries, "
            f"{len(errors)} errors, {len(warnings)} warnings."
        ),
        "",
    ]
    if not errors and not warnings:
        return "\n".join(lines) + "\n"

    by_rule = Counter(
        (issue.severity, issue.rule or "schema") for issue in [*errors, *warnings]
    )
    lines += ["### By rule", "", "| Severity | Rule | Count |", "|---|---|---|"]
    for (severity, rule), count in sorted(by_rule.items()):
        lines.append(f"| {severity} | `{rule}` | {count} |")

    lines += [
        "",
        "### By entry",
        "",
        "| Entry | Errors | Warnings |",
        "|---|---|---|",
    ]
    for result in results:
        if result.errors or result.warnings:
            entry = str(Path(result.file).parent) if result.file.endswith(
                ("SKILL.md", "HOOK.md")
            ) else result.file
            lines.append(
                f"| `{entry}` | {len(result.errors)} | {len(result.warnings)} |"
            )

    # GitHub renders at most 10 annotations of each severity per step, so the
    # full list lives here.
    lines += ["", "<details><summary>All findings</summary>", ""]
    for issue in [*errors, *warnings]:
        lines.append(
            f"- **{issue.severity}** `{issue.rule or 'schema'}` "
            f"`{_location(issue)}` — {issue.message}"
        )
    lines += ["", "</details>"]
    return "\n".join(lines) + "\n"


def main() -> None:
    """Parse arguments, run validation, and print results."""

    args = _build_parser().parse_args()
    registry_path: Path = args.registry_path.resolve()

    results = validate_registry(registry_path)

    def _fails(result: ValidationResult) -> bool:
        return not result.valid or (args.strict and bool(result.warnings))

    total_entries = len(results)
    failed_files = sum(1 for r in results if _fails(r))
    passed_files = total_entries - failed_files
    all_valid = failed_files == 0
    total_errors = sum(len(r.errors) for r in results)
    total_warnings = sum(len(r.warnings) for r in results)

    if args.summary is not None:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write(_markdown_summary(results, not all_valid))

    if args.format == "json":
        output = {
            "valid": all_valid,
            "errors": [_issue_dict(e) for r in results for e in r.errors],
            "warnings": [_issue_dict(w) for r in results for w in r.warnings],
            "summary": {
                "total": total_entries,
                "passed": passed_files,
                "failed": failed_files,
                "warnings": total_warnings,
            },
        }
        print(json.dumps(output, indent=2))
        sys.exit(0 if all_valid else 1)

    if args.format == "github":
        _print_github(results, registry_path)
    else:
        for result in results:
            if not result.valid:
                status = "FAIL"
            elif result.warnings:
                status = "WARN"
            else:
                status = "OK"
            print(f"{status:<5} {result.file}")
            for error in result.errors:
                if error.rule:
                    print(f"  - [{error.rule}] {_location(error)}: {error.message}")
                elif error.field:
                    print(f"  - {error.field}: {error.message}")
                else:
                    print(f"  - {error.message}")
            for warning in result.warnings:
                print(
                    f"  - WARN [{warning.rule}] {_location(warning)}: "
                    f"{warning.message}"
                )

    print()
    warn_note = f", {total_warnings} warnings" if total_warnings else ""
    if not all_valid:
        if total_errors:
            print(
                f"{total_errors} errors{warn_note} in {failed_files} files. "
                "Validation failed."
            )
        else:
            print(f"{total_warnings} warnings (--strict). Validation failed.")
        sys.exit(1)
    print(f"All {total_entries} entries valid{warn_note}.")
    sys.exit(0)


if __name__ == "__main__":
    main()
