"""Skill-quality rules from Anthropic's skill-authoring guide.

Source of truth:
https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

Front-matter limits (name/description length, reserved words, XML tags) live
in the Pydantic models. This module covers what a model cannot see: the
markdown body of SKILL.md and the files under references/.

Every rule has a stable id (the ``RULE_*`` constants) that shows up in the
validator output, the JSON report, and the CI summary, and every message names
the guide section it enforces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import unquote

BEST_PRACTICES_URL = (
    "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices"
)
# The skill guide has no rule on emphasis; the prompting guide does.
PROMPTING_URL = (
    "https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/"
    "claude-prompting-best-practices"
)

Severity = Literal["error", "warning"]

# Rule ids — errors.
RULE_BODY_LENGTH = "skill-body-length"
RULE_BROKEN_LINK = "broken-link"
RULE_WINDOWS_PATH = "windows-path"
# Rule ids — warnings.
RULE_REFERENCE_TOC = "reference-toc"
RULE_NESTED_REFERENCE = "nested-reference"
RULE_DESCRIPTION_TRIGGER = "description-trigger"
RULE_DESCRIPTION_PERSON = "description-person"
RULE_CAPS_EMPHASIS = "caps-emphasis"
RULE_TIME_SENSITIVE = "time-sensitive"

# "Keep SKILL.md body under 500 lines for optimal performance."
SKILL_BODY_MAX_LINES = 500

# "For reference files longer than 100 lines, include a table of contents at
# the top."
REFERENCE_TOC_MIN_LINES = 100

# How far down a reference file the contents section may start and still count
# as "at the top". The longest preamble in the registry today (title, a
# "Part of" blockquote, an intro paragraph, a rule) puts the contents heading
# around line 10; 40 lines leaves room for a longer intro without accepting a
# TOC buried mid-file.
REFERENCE_TOC_WINDOW_LINES = 40

# A list of at least this many in-page anchor links counts as a contents
# section even without a "Contents" heading.
REFERENCE_TOC_MIN_ANCHORS = 3

# All-caps emphasis words. The skill guide itself suggests "MUST filter" as a
# legitimate fix, so a few are fine; what hurts is shouting throughout a file,
# which current models over-apply ("dial back any aggressive language" under
# "Tool usage" in the prompting best practices). Measured on the 22-skill baseline, outside code:
# kotlin-development/SKILL.md 10, verify-ui/SKILL.md 7,
# postgres-best-practices/SKILL.md 6, then react-best-practices/SKILL.md 4 and
# terraform-conventions/SKILL.md 3, every other file 0-1. A threshold of 5 per
# file separates the three files already flagged as shouting from ordinary
# occasional emphasis.
CAPS_EMPHASIS_WORDS: tuple[str, ...] = (
    "CRITICAL",
    "MUST",
    "NEVER",
    "ALWAYS",
    "IMPORTANT",
)
CAPS_EMPHASIS_THRESHOLD = 5

_CAPS_EMPHASIS = re.compile(r"\b(" + "|".join(CAPS_EMPHASIS_WORDS) + r")\b")

# Fenced code blocks (``` or ~~~, three or more). Closing fence must use the
# same character and be at least as long as the opening one.
_FENCE_OPEN = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_INLINE_CODE = re.compile(r"(`+)(.+?)\1")

# Inline links and images: [text](target "title"). Reference-style
# definitions: [label]: target.
_INLINE_LINK = re.compile(r"!?\[(?:[^\]\\]|\\.)*\]\(\s*(<[^>]*>|[^)\s]+)")
_REFERENCE_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)")
_URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")

# A backslash-separated path ending in a file name, e.g. references\guide.md.
_WINDOWS_PATH = re.compile(r"(?:[\w.-]+\\)+[\w.-]+\.[A-Za-z0-9]{1,5}\b")

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_CONTENTS_HEADING = re.compile(r"\b(table of )?contents\b", re.IGNORECASE)
_ANCHOR_LINK = re.compile(r"\]\(#[^)]+\)")

# Sections where dated wording is expected ("Old patterns" in the guide).
_LEGACY_HEADING = re.compile(
    r"\b(old patterns?|legacy|deprecated|history|changelog)\b", re.IGNORECASE
)

_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_YEAR = r"(?:19|20)\d{2}"
_TIME_SENSITIVE = re.compile(
    r"\b(?:"
    rf"(?:before|after|until|since|by|from|starting|as of) {_MONTH}\.? (?:\d{{1,2}},? )?{_YEAR}"
    rf"|as of (?:(?:Q[1-4]|early|mid|late)[ -])?{_YEAR}"
    rf"|(?:before|after|until|since|by) (?:Q[1-4]|early|mid|late)[ -]{_YEAR}"
    r")\b",
    re.IGNORECASE,
)

# "Use when ...", "Use this skill for ...", "This skill should be used when",
# "... when the user asks ...", "Triggers on ...".
_TRIGGER_PHRASE = re.compile(
    r"\buse (?:this(?: skill| agent)? )?(?:when|whenever|for|if|to|with|in|on)\b"
    r"|\bshould be used\b"
    r"|\bwhen (?:the user|a user|users|working|writing|building|creating|"
    r"reviewing|debugging|asked|you)\b"
    r"|\btrigger(?:s|ed)?\b"
    r"|\bapplies (?:when|to)\b",
    re.IGNORECASE,
)

# First/second person voice. "when you ..." inside a trigger clause is common
# and harmless, so only statements about the skill itself are flagged.
_PERSON_PHRASE = re.compile(
    r"\b(?:I|we)(?:'m|'ll| am| can| will| help| provide| offer)\b"
    r"|\byou can\b"
    r"|\b(?:helps|lets|allows) you\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class QualityIssue:
    """A single quality finding, before it is turned into a ValidationError.

    Attributes:
        file: Path relative to the skill directory (e.g. ``SKILL.md`` or
            ``references/guide.md``).
        line: 1-based line number, or ``None`` for file-level findings.
        rule: Stable rule id (one of the ``RULE_*`` constants).
        severity: ``"error"`` blocks merge, ``"warning"`` is reported only.
        message: Human-readable description, naming the guide section.
    """

    file: str
    line: int | None
    rule: str
    severity: Severity
    message: str


def _cite(section: str, url: str = BEST_PRACTICES_URL) -> str:
    return f"(see '{section}' in {url})"


def _strip_code(text: str) -> list[str]:
    """Return *text* as lines with code blanked out, line numbers preserved.

    Fenced blocks become empty lines and inline code spans become spaces, so
    links, emphasis, and dates inside code samples are not mistaken for prose.
    """

    lines = text.splitlines()
    out: list[str] = []
    fence: str | None = None
    for line in lines:
        if fence is not None:
            stripped = line.strip()
            if stripped.startswith(fence) and set(stripped) == {fence[0]}:
                fence = None
            out.append("")
            continue
        match = _FENCE_OPEN.match(line)
        if match:
            fence = match.group(1)
            out.append("")
            continue
        out.append(_INLINE_CODE.sub(lambda m: " " * len(m.group(0)), line))
    return out


def _inline_code_spans(text: str) -> list[tuple[int, str]]:
    """Return ``(line_number, code)`` for every inline code span outside fences."""

    spans: list[tuple[int, str]] = []
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if fence is not None:
            stripped = line.strip()
            if stripped.startswith(fence) and set(stripped) == {fence[0]}:
                fence = None
            continue
        match = _FENCE_OPEN.match(line)
        if match:
            fence = match.group(1)
            continue
        spans.extend((number, m.group(2)) for m in _INLINE_CODE.finditer(line))
    return spans


def _link_targets(prose_lines: list[str]) -> list[tuple[int, str]]:
    """Return ``(line_number, target)`` for every link in code-free lines."""

    targets: list[tuple[int, str]] = []
    for number, line in enumerate(prose_lines, start=1):
        for match in _INLINE_LINK.finditer(line):
            targets.append((number, match.group(1)))
        match = _REFERENCE_DEF.match(line)
        if match:
            targets.append((number, match.group(1)))
    return targets


def _local_path(target: str) -> str | None:
    """Return the file part of a relative link target, or ``None`` if not local."""

    target = target.strip("<>")
    if not target or target.startswith(("#", "//")) or _URL_SCHEME.match(target):
        return None
    path = target.split("#", 1)[0].split("?", 1)[0]
    return unquote(path) or None


def _check_links(
    skill_dir: Path,
    file_rel: str,
    text: str,
    prose_lines: list[str],
    bundled: set[Path],
) -> list[QualityIssue]:
    """Broken relative links, Windows-style paths, and nested references."""

    issues: list[QualityIssue] = []
    file_path = skill_dir / file_rel
    is_reference = file_rel != "SKILL.md"
    skill_md = (skill_dir / "SKILL.md").resolve()

    for line, target in _link_targets(prose_lines):
        path = _local_path(target)
        if path is None:
            continue

        if "\\" in path:
            issues.append(
                QualityIssue(
                    file=file_rel,
                    line=line,
                    rule=RULE_WINDOWS_PATH,
                    severity="error",
                    message=(
                        f"Link '{target}' uses backslashes — use forward "
                        f"slashes {_cite('Avoid Windows-style paths')}"
                    ),
                )
            )
            continue

        resolved = (file_path.parent / path).resolve()
        if resolved not in bundled:
            if not resolved.exists():
                reason = "does not exist"
            elif not resolved.is_relative_to(skill_dir.resolve()):
                reason = "points outside the skill directory"
            else:
                reason = (
                    "is not shipped in the install bundle (only SKILL.md, "
                    "references/ and scripts/ are)"
                )
            issues.append(
                QualityIssue(
                    file=file_rel,
                    line=line,
                    rule=RULE_BROKEN_LINK,
                    severity="error",
                    message=(
                        f"Link '{target}' {reason} "
                        f"{_cite('Progressive disclosure patterns')}"
                    ),
                )
            )
            continue

        if (
            is_reference
            and resolved.suffix == ".md"
            and resolved != skill_md
            and resolved != file_path.resolve()
        ):
            issues.append(
                QualityIssue(
                    file=file_rel,
                    line=line,
                    rule=RULE_NESTED_REFERENCE,
                    severity="warning",
                    message=(
                        f"Reference links to another reference '{target}' — "
                        "link it from SKILL.md instead so references stay one "
                        f"level deep {_cite('Avoid deeply nested references')}"
                    ),
                )
            )

    for line, code in _inline_code_spans(text):
        for match in _WINDOWS_PATH.finditer(code):
            issues.append(
                QualityIssue(
                    file=file_rel,
                    line=line,
                    rule=RULE_WINDOWS_PATH,
                    severity="error",
                    message=(
                        f"Path '{match.group(0)}' uses backslashes — use "
                        f"forward slashes {_cite('Avoid Windows-style paths')}"
                    ),
                )
            )

    return issues


def _check_caps(file_rel: str, prose_lines: list[str]) -> list[QualityIssue]:
    count = sum(len(_CAPS_EMPHASIS.findall(line)) for line in prose_lines)
    if count < CAPS_EMPHASIS_THRESHOLD:
        return []
    return [
        QualityIssue(
            file=file_rel,
            line=None,
            rule=RULE_CAPS_EMPHASIS,
            severity="warning",
            message=(
                f"{count} all-caps emphasis words "
                f"({'/'.join(CAPS_EMPHASIS_WORDS)}) outside code; the "
                f"threshold is {CAPS_EMPHASIS_THRESHOLD} per file — state the "
                f"rule plainly and keep emphasis for the one that matters "
                f"{_cite('Tool usage', PROMPTING_URL)}"
            ),
        )
    ]


def _check_time_sensitive(
    file_rel: str, prose_lines: list[str]
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    legacy_level: int | None = None
    for number, line in enumerate(prose_lines, start=1):
        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            if legacy_level is not None and level <= legacy_level:
                legacy_level = None
            if legacy_level is None and _LEGACY_HEADING.search(heading.group(2)):
                legacy_level = level
            continue
        if legacy_level is not None:
            continue
        for match in _TIME_SENSITIVE.finditer(line):
            issues.append(
                QualityIssue(
                    file=file_rel,
                    line=number,
                    rule=RULE_TIME_SENSITIVE,
                    severity="warning",
                    message=(
                        f"Time-sensitive phrase '{match.group(0)}' — move it "
                        "under an 'Old patterns' section or drop the date "
                        f"{_cite('Avoid time-sensitive information')}"
                    ),
                )
            )
    return issues


def _has_contents_near_top(lines: list[str]) -> bool:
    top = lines[:REFERENCE_TOC_WINDOW_LINES]
    for line in top:
        heading = _HEADING.match(line)
        if heading and _CONTENTS_HEADING.search(heading.group(2)):
            return True
    anchors = sum(len(_ANCHOR_LINK.findall(line)) for line in top)
    return anchors >= REFERENCE_TOC_MIN_ANCHORS


def _check_reference_toc(file_rel: str, text: str) -> list[QualityIssue]:
    lines = text.splitlines()
    if len(lines) <= REFERENCE_TOC_MIN_LINES or _has_contents_near_top(lines):
        return []
    return [
        QualityIssue(
            file=file_rel,
            line=None,
            rule=RULE_REFERENCE_TOC,
            severity="warning",
            message=(
                f"Reference file is {len(lines)} lines with no contents "
                f"section in its first {REFERENCE_TOC_WINDOW_LINES} lines "
                f"{_cite('Structure longer reference files with table of contents')}"
            ),
        )
    ]


def check_description(description: object) -> list[QualityIssue]:
    """Warnings about a skill description's voice and trigger wording.

    Length and XML tags are hard limits enforced by the model; these are the
    softer "Writing effective descriptions" guidelines.
    """

    if not isinstance(description, str) or not description.strip():
        return []

    issues: list[QualityIssue] = []
    if not _TRIGGER_PHRASE.search(description):
        issues.append(
            QualityIssue(
                file="SKILL.md",
                line=None,
                rule=RULE_DESCRIPTION_TRIGGER,
                severity="warning",
                message=(
                    "Description does not say when to use the skill — add a "
                    "trigger clause such as 'Use when …' "
                    f"{_cite('Writing effective descriptions')}"
                ),
            )
        )
    person = _PERSON_PHRASE.search(description)
    if person:
        issues.append(
            QualityIssue(
                file="SKILL.md",
                line=None,
                rule=RULE_DESCRIPTION_PERSON,
                severity="warning",
                message=(
                    f"Description uses first/second person ('{person.group(0)}') "
                    f"— write it in third person "
                    f"{_cite('Writing effective descriptions')}"
                ),
            )
        )
    return issues


def _bundled_files(skill_dir: Path) -> set[Path]:
    """Files the install bundle ships: SKILL.md plus flat references/ and scripts/."""

    files = {(skill_dir / "SKILL.md").resolve()}
    for sub in ("references", "scripts"):
        directory = skill_dir / sub
        if directory.is_dir():
            files.update(p.resolve() for p in directory.iterdir() if p.is_file())
    return files


def check_skill_quality(skill_dir: Path, body: str) -> list[QualityIssue]:
    """Run every body-level quality rule on one skill.

    Args:
        skill_dir: The skill directory (contains SKILL.md).
        body: The SKILL.md markdown body, front matter already removed.

    Returns:
        All findings, errors and warnings mixed; callers split on ``severity``.
    """

    issues: list[QualityIssue] = []
    bundled = _bundled_files(skill_dir)

    body_lines = len(body.splitlines())
    if body_lines > SKILL_BODY_MAX_LINES:
        issues.append(
            QualityIssue(
                file="SKILL.md",
                line=None,
                rule=RULE_BODY_LENGTH,
                severity="error",
                message=(
                    f"SKILL.md body is {body_lines} lines; the limit is "
                    f"{SKILL_BODY_MAX_LINES} — move sections into references/ "
                    f"{_cite('Progressive disclosure patterns')}"
                ),
            )
        )

    # Line numbers for SKILL.md are reported against the body; shift them so
    # they point at the right line of the file.
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    offset = skill_text.count("\n", 0, skill_text.find(body)) if body else 0

    documents: list[tuple[str, str, int]] = [("SKILL.md", body, offset)]
    references_dir = skill_dir / "references"
    if references_dir.is_dir():
        for ref in sorted(references_dir.glob("*.md")):
            if ref.is_file():
                documents.append(
                    (f"references/{ref.name}", ref.read_text(encoding="utf-8"), 0)
                )

    for file_rel, text, line_offset in documents:
        prose = _strip_code(text)
        found = _check_links(skill_dir, file_rel, text, prose, bundled)
        found += _check_caps(file_rel, prose)
        found += _check_time_sensitive(file_rel, prose)
        if file_rel != "SKILL.md":
            found += _check_reference_toc(file_rel, text)
        for issue in found:
            if line_offset and issue.line is not None:
                issue = QualityIssue(
                    file=issue.file,
                    line=issue.line + line_offset,
                    rule=issue.rule,
                    severity=issue.severity,
                    message=issue.message,
                )
            issues.append(issue)

    return issues
