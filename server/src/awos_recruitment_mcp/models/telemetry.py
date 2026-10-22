"""Pydantic models for client-reported telemetry (POST /telemetry)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

ClientEventName = Literal[
    "capability_update_checked",
    "capability_updated",
    "capability_removed_in_use",
]

CapabilityType = Literal["skill", "agent", "hook", "mcp_server"]

PropertyValue = bool | int | Annotated[str, Field(max_length=128)]


class ClientEvent(BaseModel):
    """One event reported by the CLI.

    Attributes:
        event: Allow-listed event name.
        capability_name: Kebab-case capability name, when the event is about one.
        capability_type: Capability type, when the event is about one.
        properties: Small bag of scalar properties (counts, flags).
    """

    event: ClientEventName
    capability_name: Annotated[str, Field(pattern=r"^[a-z0-9-]{1,64}$")] | None = None
    capability_type: CapabilityType | None = None
    properties: dict[Annotated[str, Field(pattern=r"^[a-z_]{1,32}$")], PropertyValue] = Field(
        default_factory=dict, max_length=10
    )


class TelemetryRequest(BaseModel):
    """Batch of client events for one project.

    Attributes:
        project_id: Random id the CLI stores in the lock file. Never a repo
            or user name.
        events: One to fifty events.
    """

    project_id: Annotated[str, Field(pattern=r"^[0-9a-fA-F-]{36}$")]
    events: list[ClientEvent] = Field(..., min_length=1, max_length=50)
