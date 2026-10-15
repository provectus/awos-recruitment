"""Parity check between repo-local skill copies and their registry source.

Some skills live twice: once under ``registry/skills/<name>`` (the published
copy the MCP server bundles) and once under ``.claude/skills/<alias>`` so this
repository's own Claude Code sessions pick them up without an install step.
The two must stay identical apart from what the local copy legitimately
differs in:

* the ``name:`` line of ``SKILL.md`` — the local alias is not the registry name;
* a leading provenance comment (``<!-- … -->``) at the top of the ``SKILL.md``
  body (or above the front matter) pointing back at the registry copy;
* ``README.md`` (local docs) and ``evals/`` (author-side test cases), which
  are skipped on both sides.

Everything else — the ``SKILL.md`` body and front matter, every file under
``references/``, ``scripts/`` and ``assets/`` — must match byte for byte.

Usage::

    uv run python -m awos_recruitment_mcp.validate.parity [--repo-root PATH]

Exit codes: ``0`` when every pair matches, ``1`` otherwise.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

# (repo-local copy, registry source), both relative to the repository root.
# Adding a pair is one line here; nothing else needs to change.
SKILL_PAIRS: tuple[tuple[str, str], ...] = (
    (".claude/skills/python", "registry/skills/modern-python-development"),
    (".claude/skills/typescript", "registry/skills/typescript-development"),
    (".claude/skills/terraform-skill", "registry/skills/terraform-conventions"),
)

# Top-level entries ignored on both sides of a pair.
IGNORED_TOP_LEVEL: frozenset[str] = frozenset({"README.md", "evals"})

# How many unified-diff lines to print per differing text file.
_DIFF_CONTEXT_LINES = 20

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_NAME_LINE = re.compile(r"^name:[^\n]*\n?", re.MULTILINE)
_LEADING_COMMENT = re.compile(r"\A\s*<!--.*?-->[ \t]*\n?", re.DOTALL)


def normalize_skill_md(text: str) -> str:
    """Strip the parts of ``SKILL.md`` a local copy is allowed to differ in.

    Drops the ``name:`` line from the front matter and one leading
    ``<!-- … -->`` block, whether it sits above the front matter or at the top
    of the body. Blank lines at the top of the body are collapsed so the
    removed comment leaves no trace.
    """
    text = _LEADING_COMMENT.sub("", text, count=1)
    m = _FRONT_MATTER.match(text)
    if m:
        front = _NAME_LINE.sub("", m.group(1), count=1)
        body = text[m.end() :]
    else:
        front = ""
        body = text
    body = _LEADING_COMMENT.sub("", body, count=1).lstrip("\n")
    return f"---\n{front}\n---\n{body}"


def _files(root: Path) -> dict[str, Path]:
    """Map relative POSIX paths to files under *root*, minus ignored entries."""
    out: dict[str, Path] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if rel.parts[0] in IGNORED_TOP_LEVEL:
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        out[rel.as_posix()] = path
    return out


def _unified_diff(rel: str, local: str, registry: str) -> list[str]:
    diff = difflib.unified_diff(
        registry.splitlines(),
        local.splitlines(),
        fromfile=f"registry/{rel}",
        tofile=f"local/{rel}",
        lineterm="",
        n=1,
    )
    lines = list(diff)
    if len(lines) > _DIFF_CONTEXT_LINES:
        lines = lines[:_DIFF_CONTEXT_LINES] + [f"… ({len(lines) - _DIFF_CONTEXT_LINES} more lines)"]
    return lines


def compare_pair(local: Path, registry: Path) -> list[str]:
    """Return human-readable differences between one local/registry pair.

    An empty list means the pair is in sync.
    """
    for side, path in (("local", local), ("registry", registry)):
        if not path.is_dir():
            return [f"{side} copy '{path}' is not a directory"]

    local_files = _files(local)
    registry_files = _files(registry)
    problems: list[str] = []

    for rel in sorted(registry_files.keys() - local_files.keys()):
        problems.append(f"only in registry: {rel}")
    for rel in sorted(local_files.keys() - registry_files.keys()):
        problems.append(f"only in local: {rel}")

    for rel in sorted(local_files.keys() & registry_files.keys()):
        local_bytes = local_files[rel].read_bytes()
        registry_bytes = registry_files[rel].read_bytes()
        if rel == "SKILL.md":
            local_text = normalize_skill_md(local_bytes.decode("utf-8", errors="replace"))
            registry_text = normalize_skill_md(registry_bytes.decode("utf-8", errors="replace"))
            if local_text != registry_text:
                problems.append(
                    "SKILL.md differs beyond the name: line and the provenance comment"
                )
                problems.extend(f"    {line}" for line in _unified_diff(rel, local_text, registry_text))
        elif local_bytes != registry_bytes:
            problems.append(f"differs: {rel}")
            try:
                local_text = local_bytes.decode("utf-8")
                registry_text = registry_bytes.decode("utf-8")
            except UnicodeDecodeError:
                continue
            problems.extend(f"    {line}" for line in _unified_diff(rel, local_text, registry_text))

    return problems


def check_pairs(
    repo_root: Path, pairs: tuple[tuple[str, str], ...] = SKILL_PAIRS
) -> dict[str, list[str]]:
    """Run :func:`compare_pair` for every pair; keys are ``local <-> registry``."""
    return {
        f"{local} <-> {registry}": compare_pair(repo_root / local, repo_root / registry)
        for local, registry in pairs
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that repo-local skill copies match their registry source.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(".."),
        help="Repository root (default: .., i.e. run from server/)",
    )
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root.resolve()

    outcome = check_pairs(repo_root)
    failed = 0
    for label, problems in outcome.items():
        if problems:
            failed += 1
            print(f"FAIL  {label}")
            for problem in problems:
                print(f"  - {problem}" if not problem.startswith("    ") else problem)
        else:
            print(f"OK    {label}")

    print()
    if failed:
        print(
            f"{failed} of {len(outcome)} skill pairs out of sync. Re-copy the "
            "registry skill into .claude/skills/, keeping only the local "
            "name: line and the provenance comment."
        )
        return 1
    print(f"All {len(outcome)} skill pairs in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
