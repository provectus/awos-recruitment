"""Recommendations: capabilities a stack probably needs that search does not find.

``registry/recommendations.yaml`` is a list of entries (see
:class:`~awos_recruitment_mcp.models.recommendation.Recommendation`). The
caller sends the technologies and domains of its project as stack terms; an
entry triggers when one of its ``when_stack_has`` phrases is a whole word in
one of those terms. The match is plain text, not the semantic index: the user
did not ask for a recommendation, so a miss costs less than a false match.

The file sits outside every capability directory, so editing it changes no
skill hash and marks no installed copy as outdated.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import ValidationError as PydanticValidationError

from awos_recruitment_mcp.models.capability import RegistryCapability
from awos_recruitment_mcp.models.recommendation import Recommendation

RECOMMENDATIONS_FILE = "recommendations.yaml"

MAX_RECOMMENDATIONS = 4
"""At most this many items per call: one ``AskUserQuestion`` holds 4 options."""


class RecommendationsFileError(ValueError):
    """``recommendations.yaml`` is present but malformed."""


def normalize(text: str) -> str:
    """Lowercase *text* and collapse runs of whitespace to one space."""
    return " ".join(text.lower().split())


def has_phrase(term: str, phrase: str) -> bool:
    """Return ``True`` when *phrase* is a whole word (or words) in *term*.

    Both are compared after :func:`normalize`. A word boundary is any
    character that is not a letter or a digit, so ``aws`` matches
    ``AWS ECS`` and ``aws-sdk`` but not ``laws``; ``next.js`` matches
    ``Next.js 14``.
    """
    pattern = r"(?<![a-z0-9])" + re.escape(normalize(phrase)) + r"(?![a-z0-9])"
    return re.search(pattern, normalize(term)) is not None


def matched_term(rec: Recommendation, stack: list[str]) -> str | None:
    """Return the first stack term that triggers *rec*, or ``None``."""
    for term in stack:
        if any(has_phrase(term, p) for p in rec.unless_term_has):
            continue
        if any(has_phrase(term, p) for p in rec.when_stack_has):
            return term
    return None


def load_recommendations(registry_path: str | Path) -> list[Recommendation]:
    """Load ``<registry>/recommendations.yaml``.

    Returns an empty list when the file is absent.

    Raises:
        RecommendationsFileError: The file is not a list of valid entries,
            or two entries share an id.
    """
    path = Path(registry_path) / RECOMMENDATIONS_FILE
    if not path.is_file():
        return []

    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise RecommendationsFileError(f"{RECOMMENDATIONS_FILE}: {exc}") from exc

    if data is None:
        return []
    if not isinstance(data, list):
        raise RecommendationsFileError(
            f"{RECOMMENDATIONS_FILE}: top level must be a list of entries"
        )

    recs: list[Recommendation] = []
    seen: set[str] = set()
    for index, entry in enumerate(data):
        try:
            rec = Recommendation.model_validate(entry)
        except PydanticValidationError as exc:
            raise RecommendationsFileError(
                f"{RECOMMENDATIONS_FILE}: entry {index}: {exc}"
            ) from exc
        if rec.id in seen:
            raise RecommendationsFileError(
                f"{RECOMMENDATIONS_FILE}: duplicate id '{rec.id}'"
            )
        seen.add(rec.id)
        recs.append(rec)
    return recs


def recommend(
    recs: list[Recommendation],
    capabilities: dict[tuple[str, str], RegistryCapability],
    stack: list[str],
    exclude: list[str] | None = None,
    limit: int = MAX_RECOMMENDATIONS,
) -> list[dict]:
    """Return the recommendations that *stack* triggers.

    Entries are taken in file order. An entry is left out when its target is
    in *exclude*, when an earlier entry already returned the same target, or
    when the target is not in *capabilities* (removed since the file was
    written; ``validate`` catches this in CI). At most *limit* items.

    Args:
        recs: Entries from :func:`load_recommendations`.
        capabilities: Registry capabilities keyed by ``(type, name)``.
        stack: The caller's technology and domain terms.
        exclude: Capability names the caller already has or declined.
        limit: Maximum number of items.

    Returns:
        Dicts with ``id``, ``name``, ``type``, ``description``, ``reason``
        and ``matched_term``; a skill item also has ``user_invoked``.
    """
    excluded = {normalize(name) for name in exclude or []}
    returned: set[tuple[str, str]] = set()
    items: list[dict] = []

    for rec in recs:
        if len(items) >= limit:
            break
        key = (rec.type, rec.recommend)
        if key in returned or normalize(rec.recommend) in excluded:
            continue
        cap = capabilities.get(key)
        if cap is None:
            continue
        term = matched_term(rec, stack)
        if term is None:
            continue

        item: dict = {
            "id": rec.id,
            "name": cap.name,
            "type": cap.type,
            "description": cap.description,
            "reason": rec.reason,
            "matched_term": term,
        }
        if cap.user_invoked is not None:
            item["user_invoked"] = cap.user_invoked
        items.append(item)
        returned.add(key)

    return items
