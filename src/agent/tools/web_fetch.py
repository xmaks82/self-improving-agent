"""Web fetch tool for loading and parsing web pages."""

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

from .base import BaseTool, ToolResult


class WebFetchTool(BaseTool):
    """
    Fetch and extract content from web pages.

    Loads a URL and extracts readable text content.
    """

    name = "fetch_url"
    description = "Fetch a web page and extract its text content."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch",
            },
            "extract": {
                "type": "string",
                "description": "What to extract: 'text', 'links', 'all'",
                "default": "text",
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum content length to return",
                "default": 10000,
            },
        },
        "required": ["url"],
    }

    # User agent for requests
    USER_AGENT = "Mozilla/5.0 (compatible; AgentBot/1.0; +https://github.com/example/agent)"

    def __init__(self, timeout: int = 30, max_redirects: int = 5):
        self.timeout = timeout
        self.max_redirects = max_redirects

    async def execute(
        self,
        url: str,
        extract: str = "text",
        max_length: int = 10000,
        **kwargs,
    ) -> ToolResult:
        """Fetch URL and extract content."""
        # Validate URL
        if not self._is_valid_url(url):
            return ToolResult.fail(f"Invalid URL: {url}")

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                max_redirects=self.max_redirects,
            ) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": self.USER_AGENT},
                )
                response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            # Handle different content types
            if "text/html" in content_type:
                html = response.text
                result = self._extract_from_html(html, extract, max_length, url)
            elif "text/plain" in content_type:
                result = response.text[:max_length]
            elif "application/json" in content_type:
                result = response.text[:max_length]
            else:
                return ToolResult.fail(
                    f"Unsupported content type: {content_type}"
                )

            return ToolResult.ok(
                result,
                url=str(response.url),
                status_code=response.status_code,
                content_type=content_type,
            )

        except httpx.TimeoutException:
            return ToolResult.fail(f"Request timed out: {url}")
        except httpx.HTTPStatusError as e:
            return ToolResult.fail(f"HTTP error {e.response.status_code}: {url}")
        except Exception as e:
            return ToolResult.fail(f"Fetch error: {e}")

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False

    def _extract_from_html(
        self,
        html: str,
        extract: str,
        max_length: int,
        base_url: str,
    ) -> str:
        """Extract content from HTML."""
        if extract == "links":
            return self._extract_links(html, base_url, max_length)
        elif extract == "all":
            text = self._extract_text(html)
            links = self._extract_links(html, base_url, 2000)
            combined = f"{text}\n\n---\nLinks:\n{links}"
            return combined[:max_length]
        else:  # text
            return self._extract_text(html)[:max_length]

    def _extract_text(self, html: str) -> str:
        """Extract readable text from HTML."""
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<head[^>]*>.*?</head>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML comments
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

        # Convert common elements to text markers
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</?p[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</?div[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</?li[^>]*>', '\n• ', html, flags=re.IGNORECASE)
        html = re.sub(r'<h[1-6][^>]*>', '\n\n## ', html, flags=re.IGNORECASE)
        html = re.sub(r'</h[1-6]>', '\n', html, flags=re.IGNORECASE)

        # Remove remaining tags
        html = re.sub(r'<[^>]+>', '', html)

        # Decode HTML entities
        html = self._decode_entities(html)

        # Clean up whitespace
        lines = []
        for line in html.split('\n'):
            line = ' '.join(line.split())
            if line:
                lines.append(line)

        return '\n'.join(lines)

    def _extract_links(self, html: str, base_url: str, max_length: int) -> str:
        """Extract links from HTML."""
        # Find all anchor tags
        link_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>'
        matches = re.findall(link_pattern, html, re.IGNORECASE)

        links = []
        for href, text in matches:
            # Make absolute URL
            if href.startswith('/'):
                href = urljoin(base_url, href)
            elif not href.startswith(('http://', 'https://')):
                continue

            # Clean text
            text = ' '.join(text.split())
            if text and len(text) > 2:
                links.append(f"- {text}: {href}")

        result = '\n'.join(links)
        return result[:max_length]

    def _decode_entities(self, text: str) -> str:
        """Decode HTML entities."""
        entities = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&apos;': "'",
            '&mdash;': '—',
            '&ndash;': '–',
            '&hellip;': '...',
            '&copy;': '©',
            '&reg;': '®',
            '&trade;': '™',
        }
        for entity, char in entities.items():
            text = text.replace(entity, char)

        # Decode numeric entities
        def decode_numeric(match):
            try:
                code = int(match.group(1))
                return chr(code)
            except (ValueError, OverflowError):
                return match.group(0)

        text = re.sub(r'&#(\d+);', decode_numeric, text)
        return text


class ReadabilityTool(BaseTool):
    """
    Extract main article content from a web page.

    Focuses on the main content, removing navigation,
    ads, and other non-essential elements.
    """

    name = "read_article"
    description = "Extract the main article content from a web page."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL of the article",
            },
        },
        "required": ["url"],
    }

    def __init__(self, timeout: int = 30):
        self.fetcher = WebFetchTool(timeout=timeout)

    async def execute(self, url: str, **kwargs) -> ToolResult:
        """Extract article content."""
        # Fetch the page
        result = await self.fetcher.execute(url, extract="text", max_length=50000)

        if not result.success:
            return result

        # Try to identify and extract main content
        content = result.output
        content = self._extract_main_content(content)

        return ToolResult.ok(
            content,
            url=result.metadata.get("url", url),
        )

    def _extract_main_content(self, text: str) -> str:
        """Try to extract main article content."""
        lines = text.split('\n')

        # Find the densest paragraph section
        # (articles tend to have more continuous text)
        best_start = 0
        best_score = 0

        window_size = 20
        for i in range(len(lines) - window_size):
            window = lines[i:i + window_size]
            # Score based on average line length and word count
            score = sum(len(line) for line in window if len(line) > 50)
            if score > best_score:
                best_score = score
                best_start = i

        # Extract content around best section
        start = max(0, best_start - 5)
        end = min(len(lines), best_start + window_size + 10)

        return '\n'.join(lines[start:end])
