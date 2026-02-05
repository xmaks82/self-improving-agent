"""Web search tool."""

import asyncio
import urllib.parse
from typing import Any, Optional
from dataclasses import dataclass

import httpx

from .base import BaseTool, ToolResult


@dataclass
class SearchResult:
    """A single search result."""

    title: str
    url: str
    snippet: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
        }


class WebSearchTool(BaseTool):
    """
    Web search tool using DuckDuckGo.

    Searches the internet and returns relevant results.
    No API key required.
    """

    name = "web_search"
    description = "Search the internet for information using DuckDuckGo."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default: 5)",
                "default": 5,
            },
            "region": {
                "type": "string",
                "description": "Region for search (e.g., 'us-en', 'ru-ru')",
                "default": "wt-wt",
            },
        },
        "required": ["query"],
    }

    # DuckDuckGo HTML search URL
    SEARCH_URL = "https://html.duckduckgo.com/html/"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def execute(
        self,
        query: str,
        max_results: int = 5,
        region: str = "wt-wt",
        **kwargs,
    ) -> ToolResult:
        """Execute web search."""
        try:
            results = await self._search_duckduckgo(query, max_results, region)

            if not results:
                return ToolResult.ok(
                    f"No results found for: {query}",
                    count=0,
                )

            # Format results
            output_lines = [f"Search results for: {query}\n"]
            for i, result in enumerate(results, 1):
                output_lines.append(f"{i}. {result.title}")
                output_lines.append(f"   URL: {result.url}")
                output_lines.append(f"   {result.snippet}\n")

            return ToolResult.ok(
                "\n".join(output_lines),
                count=len(results),
                results=[r.to_dict() for r in results],
            )

        except asyncio.TimeoutError:
            return ToolResult.fail("Search timed out")
        except Exception as e:
            return ToolResult.fail(f"Search error: {e}")

    async def _search_duckduckgo(
        self,
        query: str,
        max_results: int,
        region: str,
    ) -> list[SearchResult]:
        """Search using DuckDuckGo HTML interface."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.SEARCH_URL,
                data={
                    "q": query,
                    "kl": region,
                },
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AgentBot/1.0)",
                },
            )
            response.raise_for_status()

            return self._parse_results(response.text, max_results)

    def _parse_results(self, html: str, max_results: int) -> list[SearchResult]:
        """Parse search results from HTML."""
        results = []

        # Simple parsing without external dependencies
        # Look for result blocks
        import re

        # Pattern for result links
        link_pattern = r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
        snippet_pattern = r'<a[^>]+class="result__snippet"[^>]*>([^<]+(?:<[^>]+>[^<]*</[^>]+>)*[^<]*)</a>'

        links = re.findall(link_pattern, html)
        snippets = re.findall(snippet_pattern, html)

        for i, (url, title) in enumerate(links[:max_results]):
            # Clean URL (DuckDuckGo uses redirect URLs)
            if "uddg=" in url:
                url_match = re.search(r'uddg=([^&]+)', url)
                if url_match:
                    url = urllib.parse.unquote(url_match.group(1))

            # Get snippet
            snippet = ""
            if i < len(snippets):
                snippet = re.sub(r'<[^>]+>', '', snippets[i])
                snippet = snippet.strip()[:200]

            results.append(SearchResult(
                title=title.strip(),
                url=url,
                snippet=snippet,
            ))

        return results


class WebSearchSimpleTool(BaseTool):
    """
    Simplified web search using DuckDuckGo Instant Answer API.

    Returns quick answers when available.
    """

    name = "quick_search"
    description = "Get quick answers from DuckDuckGo Instant Answers."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
        },
        "required": ["query"],
    }

    API_URL = "https://api.duckduckgo.com/"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def execute(self, query: str, **kwargs) -> ToolResult:
        """Execute instant answer search."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self.API_URL,
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": "1",
                        "skip_disambig": "1",
                    },
                )
                response.raise_for_status()
                data = response.json()

            # Extract answer
            answer = data.get("AbstractText", "")
            if not answer:
                answer = data.get("Answer", "")

            if not answer:
                # Try related topics
                topics = data.get("RelatedTopics", [])
                if topics and isinstance(topics[0], dict):
                    answer = topics[0].get("Text", "")

            if answer:
                source = data.get("AbstractSource", "DuckDuckGo")
                url = data.get("AbstractURL", "")

                return ToolResult.ok(
                    f"{answer}\n\nSource: {source}\n{url}",
                    source=source,
                    url=url,
                )
            else:
                return ToolResult.ok(
                    f"No instant answer found for: {query}",
                    count=0,
                )

        except Exception as e:
            return ToolResult.fail(f"Search error: {e}")
