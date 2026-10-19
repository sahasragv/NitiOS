"""Loading of MCP server definitions from ``mcp_servers.json``.

Secrets never live in the config file. Values may reference environment
variables as ``${NAME}``; a server whose variables are missing or empty is
skipped so the application still starts without that integration.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.logging import get_logger


_VARIABLE_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_logger = get_logger(__name__)


class MCPServerConfig(BaseModel):
    """Connection settings for one MCP server after variable substitution."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[A-Za-z0-9_-]{1,32}$")
    transport: Literal["stdio", "http"]
    enabled: bool = True
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_transport_target(self) -> "MCPServerConfig":
        """Require a command for stdio servers and a URL for HTTP servers."""
        if self.transport == "stdio" and not self.command:
            raise ValueError(f"MCP server '{self.name}' uses stdio and must define 'command'.")
        if self.transport == "http" and not self.url:
            raise ValueError(f"MCP server '{self.name}' uses http and must define 'url'.")
        return self


class MissingVariableError(ValueError):
    """Raised when a config value references an unset environment variable."""

    def __init__(self, variable: str) -> None:
        super().__init__(variable)
        self.variable = variable


def _substitute(value: str, environment: Mapping[str, str | None]) -> str:
    """Replace every ``${NAME}`` in ``value``, failing on missing or empty variables."""

    def replace(match: re.Match[str]) -> str:
        resolved = environment.get(match.group(1))
        if not resolved:
            raise MissingVariableError(match.group(1))
        return resolved

    return _VARIABLE_PATTERN.sub(replace, value)


def load_mcp_server_configs(path: Path, environment: Mapping[str, str | None]) -> list[MCPServerConfig]:
    """Return the enabled, fully resolved MCP servers declared in ``path``."""
    if not path.is_file():
        _logger.warning("MCP config file not found; no tools will be available | path=%s", path)
        return []

    raw_servers = json.loads(path.read_text(encoding="utf-8")).get("servers", {})
    configs: list[MCPServerConfig] = []
    for name, raw in raw_servers.items():
        if not raw.get("enabled", True):
            continue
        try:
            resolved = {
                **raw,
                "args": [_substitute(arg, environment) for arg in raw.get("args", [])],
                "env": {key: _substitute(value, environment) for key, value in raw.get("env", {}).items()},
                "headers": {key: _substitute(value, environment) for key, value in raw.get("headers", {}).items()},
            }
            if raw.get("url"):
                resolved["url"] = _substitute(raw["url"], environment)
        except MissingVariableError as error:
            _logger.info("MCP server skipped; set %s to enable it | server=%s", error.variable, name)
            continue
        configs.append(MCPServerConfig(name=name, **resolved))
    return configs
