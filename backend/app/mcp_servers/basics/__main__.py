"""Run the basics MCP server over stdio: ``python -m app.mcp_servers.basics``."""

from app.mcp_servers.basics.server import server


if __name__ == "__main__":
    server.run()
