"""MCP client for connecting NEXUS agents to external MCP servers.

Supports multiple MCP servers:
  - n8n: Workflow automation (SSE transport)
  - playwright: Headless browser automation (Streamable HTTP transport)

Uses pydantic-ai's native MCP clients for both SSE and Streamable HTTP.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai.mcp import MCPServer, MCPServerSSE, MCPServerStreamableHTTP

from app.config import settings

# ── Known MCP server registry ───────────────────────────────────────

# Each entry maps a server name to (url, transport_type).
# "sse" = legacy SSE transport (n8n), "http" = Streamable HTTP (Playwright).
_MCP_SERVERS: dict[str, tuple[str, str]] = {
    "n8n": (settings.n8n_mcp_url, "sse"),
    "playwright": (settings.playwright_mcp_url, "http"),
}


def _create_client(url: str, transport: str) -> MCPServer:
    """Create the appropriate MCP client for the given transport."""
    if transport == "http":
        return MCPServerStreamableHTTP(url=url)
    return MCPServerSSE(url=url)


def get_mcp_server(
    server_name: str | None = None,
    server_url: str | None = None,
) -> MCPServer:
    """Create an MCP client connection to a named or custom server.

    Resolution order:
      1. If server_url is provided, use it with SSE transport.
      2. If server_name is provided, look up the URL and transport.
      3. Default to n8n.

    Args:
        server_name: Registered server name ("n8n", "playwright").
        server_url: Full URL override (uses SSE transport).

    Returns:
        An MCPServer instance for the resolved server.
    """
    if server_url:
        return MCPServerSSE(url=server_url)
    name = server_name or "n8n"
    entry = _MCP_SERVERS.get(name)
    if entry is None:
        available = ", ".join(sorted(_MCP_SERVERS.keys()))
        raise ValueError(f"Unknown MCP server '{name}'. Available: {available}")
    url, transport = entry
    return _create_client(url, transport)


# ── Convenience aliases ──────────────────────────────────────────────


def get_n8n_mcp_server(workflow_url: str | None = None) -> MCPServer:
    """Create an MCP client for n8n (backward-compatible)."""
    return get_mcp_server(server_name="n8n", server_url=workflow_url)


def get_playwright_mcp_server() -> MCPServer:
    """Create an MCP client for the Playwright browser automation server."""
    return get_mcp_server(server_name="playwright")


# ── Tool discovery and invocation ────────────────────────────────────


async def list_mcp_tools(
    server_url: str | None = None,
    server_name: str | None = None,
) -> list[dict[str, Any]]:
    """List all tools available from an MCP server.

    Connects to the MCP server, discovers available tools, and returns
    their metadata (name, description, input schema).

    Returns an empty list if the MCP server is unreachable.

    Args:
        server_url: URL override.
        server_name: Registered server name ("n8n", "playwright").

    Returns:
        List of tool metadata dicts with name, description, and schema.
    """
    server = get_mcp_server(server_name=server_name, server_url=server_url)
    try:
        async with server:
            tools = await server.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": (t.inputSchema if hasattr(t, "inputSchema") else {}),
                }
                for t in tools
            ]
    except Exception:
        return []


async def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    server_url: str | None = None,
    server_name: str | None = None,
) -> Any:
    """Call a specific tool on an MCP server.

    Args:
        tool_name: Name of the tool to call.
        arguments: Arguments to pass to the tool.
        server_url: URL override.
        server_name: Registered server name ("n8n", "playwright").

    Returns:
        The tool's response.

    Raises:
        ConnectionError: If the MCP server is unreachable.
    """
    server = get_mcp_server(server_name=server_name, server_url=server_url)
    try:
        async with server:
            result = await server.direct_call_tool(tool_name, arguments or {})
            return result
    except Exception as e:
        name = server_name or "custom"
        msg = f"MCP server '{name}' unreachable: {e}."
        raise ConnectionError(msg) from e


def list_registered_servers() -> dict[str, str]:
    """Return the registry of known MCP server names and their URLs."""
    return {name: url for name, (url, _) in _MCP_SERVERS.items()}
