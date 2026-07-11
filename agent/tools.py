"""Agent tools: ``web_search`` (Tavily) and ``fetch_url`` (httpx + trafilatura).

Failure path #1 (tool failure): both tools wrap their network calls in
try/except and NEVER raise. On any failure they return a sentinel payload
containing ``"source unavailable"`` so the graph can continue and the editor
can degrade gracefully instead of crashing.

The low-level network helpers (``_tavily_search`` / ``_http_get``) are kept as
separate module-level functions specifically so tests can monkeypatch them to
simulate failures without any network access.
"""

from __future__ import annotations

import json

import httpx
from langchain_core.tools import tool

from settings import get_settings

SOURCE_UNAVAILABLE = "source unavailable"


# --------------------------------------------------------------------------
# Low-level helpers (monkeypatch targets in tests)
# --------------------------------------------------------------------------
def _tavily_search(query: str, max_results: int = 5) -> list[dict]:
    """Call Tavily and return a list of ``{title, url, content}`` dicts.

    Imported lazily so the module imports cleanly without the dependency or a
    real API key (e.g. during offline unit tests that monkeypatch this fn).
    """
    from tavily import TavilyClient

    settings = get_settings()
    client = TavilyClient(api_key=settings.tavily_api_key)
    resp = client.search(query=query, max_results=max_results)
    results = resp.get("results", []) if isinstance(resp, dict) else []
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
        }
        for r in results
    ]


def _http_get(url: str, timeout: float = 15.0) -> str:
    """Fetch raw HTML for a URL (raises on network/HTTP errors)."""
    headers = {"User-Agent": "Mozilla/5.0 (research-assistant)"}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def _extract_main_text(html: str) -> str:
    """Extract readable main content from HTML (best-effort)."""
    try:
        import trafilatura

        extracted = trafilatura.extract(html)
        if extracted:
            return extracted
    except Exception:
        pass
    # Fallback: crude tag strip so we still return *something* usable.
    import re

    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------
# Tools exposed to the researcher agent
# --------------------------------------------------------------------------
@tool
def web_search(query: str) -> str:
    """Search the web for up-to-date information about a query.

    Returns a JSON string with either ``{"results": [{title,url,content}, ...]}``
    or, on failure, ``{"error": "source unavailable", "query": ...}``.
    """
    try:
        results = _tavily_search(query)
        if not results:
            return json.dumps({"error": SOURCE_UNAVAILABLE, "query": query})
        return json.dumps({"results": results})
    except Exception as exc:  # never raise into the graph
        return json.dumps({"error": SOURCE_UNAVAILABLE, "query": query, "detail": str(exc)[:200]})


@tool
def fetch_url(url: str) -> str:
    """Fetch a URL and return its main readable text content.

    On any failure (timeout, HTTP error, parse error) returns the literal
    string ``"source unavailable"`` instead of raising.
    """
    settings = get_settings()
    try:
        html = _http_get(url)
        text = _extract_main_text(html)
        if not text:
            return SOURCE_UNAVAILABLE
        # Cap content length up-front to help avoid context overflow.
        from agent.truncate import truncate_content

        return truncate_content(text, settings.max_fetch_chars)
    except Exception:
        return SOURCE_UNAVAILABLE


TOOLS = [web_search, fetch_url]


def parse_sources_from_tool_output(content: str) -> list[dict]:
    """Extract ``{title, url}`` source dicts from a web_search tool output."""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, dict) or "results" not in data:
        return []
    sources: list[dict] = []
    for r in data.get("results", []):
        url = r.get("url")
        if url:
            sources.append({"title": r.get("title", url), "url": url})
    return sources
