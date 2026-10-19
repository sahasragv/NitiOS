"""Tests for MCP server config loading and secret substitution."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.modules.tools.infrastructure.mcp_config import load_mcp_server_configs


class LoadMCPServerConfigsTests(unittest.TestCase):
    """Verify variable substitution and that unconfigured servers are skipped."""

    def _load(self, servers: dict[str, object], environment: dict[str, str | None]) -> list:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mcp_servers.json"
            path.write_text(json.dumps({"servers": servers}), encoding="utf-8")
            return load_mcp_server_configs(path, environment)

    def test_substitutes_variables_into_headers(self) -> None:
        servers = {"github": {"transport": "http", "url": "https://example.test/mcp", "headers": {"Authorization": "Bearer ${TOKEN}"}}}
        configs = self._load(servers, {"TOKEN": "secret"})
        self.assertEqual(configs[0].headers["Authorization"], "Bearer secret")

    def test_skips_servers_with_missing_or_empty_variables(self) -> None:
        servers = {
            "github": {"transport": "http", "url": "https://example.test/mcp", "headers": {"Authorization": "Bearer ${TOKEN}"}},
            "basics": {"transport": "stdio", "command": "python", "args": ["-m", "app.mcp_servers.basics"]},
        }
        self.assertEqual([config.name for config in self._load(servers, {"TOKEN": ""})], ["basics"])

    def test_skips_disabled_servers(self) -> None:
        servers = {"basics": {"transport": "stdio", "command": "python", "enabled": False}}
        self.assertEqual(self._load(servers, {}), [])

    def test_missing_file_returns_no_servers(self) -> None:
        self.assertEqual(load_mcp_server_configs(Path("does-not-exist.json"), {}), [])

    def test_stdio_server_requires_command(self) -> None:
        with self.assertRaises(ValueError):
            self._load({"broken": {"transport": "stdio"}}, {})
