"""MCP client for connecting NEXUS agents to external MCP servers.

Provides integration with n8n (workflow automation) and other MCP-compatible
servers. Agents can discover and call tools exposed by these servers.

Uses pydantic-ai's native MCPServerSSE client for SSE-based MCP servers
(n8n's default transport).
"""

from __future__ import annotations

from typing import Any

from pydantic_ai.mcp import MCPServerSSE

from app.config import settings


def get_n8n_mcp_server(
    workflow_url: str | None = None,
) -> MCPServerSSE:
    """Create an MCP client connection to an n8n MCP Server Trigger.

    n8n exposes workflows as MCP tools via the MCP Server Trigger node.
    Each workflow with an MCP Server Trigger gets its own SSE endpoint.

    Args:
        workflow_url: Full SSE URL of the n8n MCP Server Trigger.
            If not provided, uses the default from settings.

    Returns:
        An MCPServerSSE instance that can be passed as a toolset to
        pydantic-ai agents.
    """
    url = workflow_url or settings.n8n_mcp_url
    return MCPServerSSE(url=url)


async def list_mcp_tools(
    server_url: str | None = None,
) -> list[dict[str, Any]]:
    """List all tools available from an MCP server.

    Connects to the MCP server, discovers available tools, and returns
    their metadata (name, description, input schema).

    Args:
        server_url: SSE URL of the MCP server. Defaults to n8n.

    Returns:
        List of tool metadata dicts with name, description, and schema.
    """
    server = get_n8n_mcp_server(server_url)
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


async def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    server_url: str | None = None,
) -> Any:
    """Call a specific tool on an MCP server.

    Args:
        tool_name: Name of the tool to call.
        arguments: Arguments to pass to the tool.
        server_url: SSE URL of the MCP server. Defaults to n8n.

    Returns:
        The tool's response.
    """
    server = get_n8n_mcp_server(server_url)
    async with server:
        result = await server.direct_call_tool(tool_name, arguments or {})
        return result
