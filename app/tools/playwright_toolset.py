"""Playwright MCP toolset for browser automation and testing.

Connects to the nexus-playwright container (already running) via
MCPServerStreamableHTTP. Provides agents with browser tools:
navigate, click, fill, screenshot, evaluate JS, etc.

Graceful degradation: returns None if PLAYWRIGHT_MCP_URL is empty.
"""

from __future__ import annotations

import logging
import os

from pydantic_ai.toolsets import AbstractToolset

logger = logging.getLogger(__name__)

_DEFAULT_PLAYWRIGHT_URL = "http://playwright:8931/mcp"


def create_playwright_toolset() -> AbstractToolset | None:
    """Create Playwright MCP toolset for browser automation.

    Connects to the nexus-playwright container via Streamable HTTP.
    Returns None if PLAYWRIGHT_MCP_URL is explicitly empty.
    """
    url = os.environ.get("PLAYWRIGHT_MCP_URL", _DEFAULT_PLAYWRIGHT_URL)
    if not url:
        logger.info("PLAYWRIGHT_MCP_URL empty, Playwright disabled")
        return None

    try:
        from pydantic_ai.mcp import MCPServerStreamableHTTP

        server = MCPServerStreamableHTTP(url=url)
        logger.info(f"Playwright MCP toolset configured: {url}")
        return server
    except Exception as e:
        logger.warning(f"Playwright MCP toolset failed: {e}")
        return None
