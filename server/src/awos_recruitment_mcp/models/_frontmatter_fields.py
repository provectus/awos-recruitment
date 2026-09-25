"""Field types shared by skill and agent front matter.

The limits follow Anthropic's skill-authoring guide ("Skill structure" →
YAML frontmatter): https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
Agents reuse them because their name and description are loaded into the
system prompt the same way.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, Field

_BEST_PRACTICES_URL = (
    "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices"
)

# Words the platform reserves; a name containing either is rejected on upload.
_RESERVED_NAME_WORDS: tuple[str, ...] = ("anthropic", "claude")

# An opening, closing or self-closing tag such as <example>, </example>, <br/>.
_XML_TAG = re.compile(r"</?[A-Za-z][\w.:-]*(\s[^<>]*)?/?>")

DESCRIPTION_MAX_LENGTH = 1024


def _reject_xml_tags(value: str) -> str:
    if _XML_TAG.search(value):
        raise ValueError(
            "must not contain XML tags (see 'Skill structure' in "
            f"{_BEST_PRACTICES_URL})"
        )
    return value


def _check_description_length(value: str) -> str:
    if len(value) > DESCRIPTION_MAX_LENGTH:
        raise ValueError(
            f"is {len(value)} characters; the maximum is "
            f"{DESCRIPTION_MAX_LENGTH} (see 'Skill structure' in "
            f"{_BEST_PRACTICES_URL})"
        )
    return value


def _reject_reserved_words(value: str) -> str:
    for word in _RESERVED_NAME_WORDS:
        if word in value:
            raise ValueError(
                f"must not contain the reserved word '{word}' (see 'Skill "
                f"structure' in {_BEST_PRACTICES_URL})"
            )
    return value


# The pattern already rules out '<' and '>', so the XML check on names is a
# second line of defence should the pattern ever be relaxed.
FrontmatterName = Annotated[
    str,
    Field(pattern=r"^[a-z0-9-]{1,64}$"),
    AfterValidator(_reject_xml_tags),
    AfterValidator(_reject_reserved_words),
]

FrontmatterDescription = Annotated[
    str,
    Field(min_length=1),
    AfterValidator(_check_description_length),
    AfterValidator(_reject_xml_tags),
]
