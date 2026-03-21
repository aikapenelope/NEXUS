"""Multi-provider web search for NEXUS agents.

Implements the pydantic-deep SearchProvider protocol with fallback support:
  1. Tavily (if TAVILY_API_KEY is set) -- best quality, AI-optimized
  2. DuckDuckGo (no API key needed) -- free fallback, always available

The provider is selected automatically based on available API keys.
Agents get web search via include_web=True in their AgentConfig.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from pydantic_deep.toolsets.web import SearchResult

logger = logging.getLogger(__name__)


class DuckDuckGoSearchProvider:
    """Free web search provider using DuckDuckGo.

    No API key required. Uses the duckduckgo-search package.
    Quality is lower than Tavily but always available.
    """

    async def search(
        self,
        query: str,
        max_results: int = 5,
        topic: str = "general",
    ) -> list[SearchResult]:
        """Search the web using DuckDuckGo.

        Args:
            query: Search query string.
            max_results: Maximum number of results.
            topic: Search topic (ignored by DuckDuckGo).

        Returns:
            List of search results.
        """
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            logger.warning("duckduckgo-search not installed, returning empty results")
            return []

        try:
            results: list[SearchResult] = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(
                        SearchResult(
                            title=r.get("title", ""),
                            url=r.get("href", ""),
                            content=r.get("body", ""),
                            score=0.5,  # DuckDuckGo doesn't provide relevance scores
                        )
                    )
            return results
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return []


class MultiSearchProvider:
    """Search provider that tries Tavily first, falls back to DuckDuckGo.

    Automatically selects the best available provider:
    - If TAVILY_API_KEY is set, uses Tavily (higher quality)
    - Otherwise, uses DuckDuckGo (free, no key needed)

    Both providers can be used simultaneously for broader coverage
    by calling search_all().
    """

    def __init__(self) -> None:
        self._tavily: Any | None = None
        self._ddg = DuckDuckGoSearchProvider()
        self._tavily_available = bool(os.environ.get("TAVILY_API_KEY"))

    def _get_tavily(self) -> Any:
        """Lazy-init Tavily provider."""
        if self._tavily is not None:
            return self._tavily
        try:
            from pydantic_deep.toolsets.web import TavilySearchProvider

            self._tavily = TavilySearchProvider()
            return self._tavily
        except Exception:
            self._tavily_available = False
            return None

    async def search(
        self,
        query: str,
        max_results: int = 5,
        topic: str = "general",
    ) -> list[SearchResult]:
        """Search using the best available provider.

        Tries Tavily first (if API key available), falls back to DuckDuckGo.

        Args:
            query: Search query string.
            max_results: Maximum number of results.
            topic: Search topic -- "general", "news", or "finance".

        Returns:
            List of search results from the best available provider.
        """
        # Try Tavily first
        if self._tavily_available:
            try:
                tavily = self._get_tavily()
                if tavily is not None:
                    results = await tavily.search(query, max_results=max_results, topic=topic)
                    if results:
                        return results
            except Exception as e:
                logger.warning(f"Tavily search failed, falling back to DuckDuckGo: {e}")

        # Fall back to DuckDuckGo
        return await self._ddg.search(query, max_results=max_results, topic=topic)


def get_search_provider() -> MultiSearchProvider:
    """Return the multi-provider search instance.

    This is the provider passed to create_deep_agent via web_search_provider.
    """
    return MultiSearchProvider()
