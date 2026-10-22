"""Pydantic model for POST /check: the CLI lock file, extra fields ignored."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

SkillName = Annotated[str, Field(pattern=r"^[a-z0-9-]{1,64}$")]


Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class LockSkip(BaseModel):
    """The registry version the user chose to skip (`skill skip`)."""

    model_config = ConfigDict(extra="ignore")

    hash: Sha256


class LockSkill(BaseModel):
    """One entry of the lock file's ``skills`` map; ``hash`` and ``skip`` are read."""

    model_config = ConfigDict(extra="ignore")

    hash: Sha256
    skip: LockSkip | None = None


class CheckRequest(BaseModel):
    """The lock file ``.claude/awos-recruitment.lock.json`` as the CLI writes it.

    Attributes:
        project_id: Random id from the lock file; used as the telemetry key.
        skills: Installed skills by name. At most 200.
    """

    model_config = ConfigDict(extra="ignore")

    project_id: Annotated[str, Field(pattern=r"^[0-9a-fA-F-]{36}$")] | None = None
    skills: dict[SkillName, LockSkill] = Field(default_factory=dict, max_length=200)
