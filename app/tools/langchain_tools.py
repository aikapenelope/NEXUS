"""LangChain tools integration for NEXUS agents.

Uses Pydantic AI's official LangChain adapter (pydantic_ai.ext.langchain)
to wrap LangChain community tools for use in our agents.

Available tools:
  - Wikipedia: encyclopedia lookup
  - Arxiv: academic paper search
  - PubMed: biomedical literature search

These are registered as a LangChainToolset and passed to create_deep_agent
via the toolsets parameter.

Note: Pydantic AI does NOT validate arguments for LangChain tools.
The model must provide correct arguments, and the LangChain tool
handles its own error reporting.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic_ai.toolsets import AbstractToolset

logger = logging.getLogger(__name__)


def create_langchain_toolset() -> AbstractToolset[Any] | None:
    """Create a LangChainToolset with Wikipedia, Arxiv, and PubMed tools.

    Returns None if langchain-community is not installed, allowing
    graceful degradation.

    Returns:
        LangChainToolset with research tools, or None if unavailable.
    """
    try:
        from pydantic_ai.ext.langchain import LangChainToolset
    except ImportError:
        logger.info("pydantic_ai.ext.langchain not available, skipping LangChain tools")
        return None

    tools: list[Any] = []

    # Wikipedia -- encyclopedia lookup, no API key needed
    try:
        from langchain_community.tools import WikipediaQueryRun
        from langchain_community.utilities import WikipediaAPIWrapper

        wiki_wrapper = WikipediaAPIWrapper(  # type: ignore[call-arg]
            top_k_results=3, doc_content_chars_max=4000
        )
        tools.append(WikipediaQueryRun(api_wrapper=wiki_wrapper))  # type: ignore[call-arg]
        logger.info("LangChain Wikipedia tool loaded")
    except ImportError:
        logger.debug("langchain-community Wikipedia not available")

    # Arxiv -- academic paper search, no API key needed
    try:
        from langchain_community.tools import ArxivQueryRun
        from langchain_community.utilities import ArxivAPIWrapper

        arxiv_wrapper = ArxivAPIWrapper(  # type: ignore[call-arg]
            top_k_results=3, doc_content_chars_max=4000
        )
        tools.append(ArxivQueryRun(api_wrapper=arxiv_wrapper))  # type: ignore[call-arg]
        logger.info("LangChain Arxiv tool loaded")
    except ImportError:
        logger.debug("langchain-community Arxiv not available")

    # PubMed -- biomedical literature, no API key needed
    try:
        from langchain_community.tools.pubmed.tool import PubmedQueryRun
        from langchain_community.utilities.pubmed import PubMedAPIWrapper

        pubmed_wrapper = PubMedAPIWrapper(  # type: ignore[call-arg]
            top_k_results=3, doc_content_chars_max=4000
        )
        tools.append(PubmedQueryRun(api_wrapper=pubmed_wrapper))  # type: ignore[call-arg]
        logger.info("LangChain PubMed tool loaded")
    except ImportError:
        logger.debug("langchain-community PubMed not available")

    if not tools:
        logger.info("No LangChain tools available")
        return None

    return LangChainToolset(tools)
