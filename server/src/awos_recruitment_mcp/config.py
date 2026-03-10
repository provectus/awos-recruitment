"""Configuration for the AWOS Recruitment MCP server.

Loads settings from environment variables with sensible defaults.
A `.env` file in the project root is loaded automatically via python-dotenv.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load .env file before anything reads os.environ
load_dotenv()


@dataclass(frozen=True)
class Config:
    """Immutable server configuration.

    Attributes:
        host: Network interface to bind to.
        port: TCP port for the HTTP transport.
        version: Semantic version exposed via MCP server metadata.
        registry_path: Path to the capability registry directory.
        search_threshold: Maximum number of search results to return.
        posthog_api_key: PostHog project API key. ``None`` disables telemetry.
        posthog_host: PostHog ingestion endpoint.
    """

    host: str = "0.0.0.0"
    port: int = 8000
    version: str = "0.1.0"
    registry_path: str = "../registry"
    search_threshold: int = 20
    posthog_api_key: str | None = None
    posthog_host: str = "https://us.i.posthog.com"

    @classmethod
    def from_env(cls) -> Config:
        """Create a Config by reading environment variables.

        Recognised variables (all optional, fall back to class defaults):
            AWOS_HOST             -- network interface, e.g. "127.0.0.1"
            AWOS_PORT             -- TCP port, e.g. "9000"
            AWOS_VERSION          -- version string, e.g. "0.2.0"
            AWOS_REGISTRY_PATH    -- capability registry directory, e.g. "./registry"
            AWOS_SEARCH_THRESHOLD -- max search results, e.g. "10"
            AWOS_POSTHOG_API_KEY  -- PostHog project API key (unset = telemetry disabled)
            AWOS_POSTHOG_HOST     -- PostHog ingestion host, e.g. "https://eu.i.posthog.com"
        """
        defaults = cls()
        return cls(
            host=os.environ.get("AWOS_HOST", defaults.host),
            port=int(os.environ.get("AWOS_PORT", str(defaults.port))),
            version=os.environ.get("AWOS_VERSION", defaults.version),
            registry_path=os.environ.get("AWOS_REGISTRY_PATH", defaults.registry_path),
            search_threshold=int(os.environ.get("AWOS_SEARCH_THRESHOLD", str(defaults.search_threshold))),
            posthog_api_key=os.environ.get("AWOS_POSTHOG_API_KEY"),
            posthog_host=os.environ.get("AWOS_POSTHOG_HOST", defaults.posthog_host),
        )
