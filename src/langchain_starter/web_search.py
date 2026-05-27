"""Lightweight web search helpers."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from langchain_starter.config import Settings


@dataclass(frozen=True)
class SearchResult:
    title: str
    snippet: str
    url: str
    page_text: str = ""


def _request_text(url: str, timeout: float) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        if "text" not in content_type and "html" not in content_type and "json" not in content_type:
            return ""
        return response.read().decode("utf-8", errors="ignore")


def _clean_text(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _decode_duckduckgo_url(url: str) -> str:
    parsed = urlparse(html.unescape(url))
    if "duckduckgo.com" not in parsed.netloc:
        return html.unescape(url)

    query = parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return unquote(query["uddg"][0])
    return html.unescape(url)


def _extract_duckduckgo_html_results(page_html: str) -> list[SearchResult]:
    results: list[SearchResult] = []
    blocks = re.findall(
        r'<div[^>]+class="[^"]*result[^"]*"[\s\S]*?</div>\s*</div>',
        page_html,
        flags=re.IGNORECASE,
    )
    for block in blocks:
        title_match = re.search(
            r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>',
            block,
            flags=re.IGNORECASE,
        )
        if not title_match:
            continue

        snippet_match = re.search(
            r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>([\s\S]*?)</a>',
            block,
            flags=re.IGNORECASE,
        )
        if not snippet_match:
            snippet_match = re.search(
                r'<div[^>]+class="[^"]*result__snippet[^"]*"[^>]*>([\s\S]*?)</div>',
                block,
                flags=re.IGNORECASE,
            )

        url = _decode_duckduckgo_url(title_match.group(1))
        title = _clean_text(title_match.group(2))
        snippet = _clean_text(snippet_match.group(1)) if snippet_match else ""
        if title and url:
            results.append(SearchResult(title=title, snippet=snippet or title, url=url))

    return results


def _search_duckduckgo_html(query: str, settings: Settings) -> list[SearchResult]:
    params = urlencode({"q": query})
    page_html = _request_text(
        f"https://duckduckgo.com/html/?{params}",
        settings.web_search_timeout,
    )
    return _extract_duckduckgo_html_results(page_html)


def _collect_related_topics(items: list[dict], results: list[SearchResult]) -> None:
    for item in items:
        if "Topics" in item:
            _collect_related_topics(item.get("Topics", []), results)
            continue

        title = str(item.get("Text", "")).strip()
        url = str(item.get("FirstURL", "")).strip()
        if title and url:
            results.append(SearchResult(title=title, snippet=title, url=url))


def _search_duckduckgo_instant(query: str, settings: Settings) -> list[SearchResult]:
    params = urlencode(
        {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
    )
    payload = json.loads(
        _request_text(
            f"https://api.duckduckgo.com/?{params}",
            settings.web_search_timeout,
        )
    )

    results: list[SearchResult] = []
    abstract = str(payload.get("AbstractText", "")).strip()
    abstract_url = str(payload.get("AbstractURL", "")).strip()
    heading = str(payload.get("Heading", "")).strip()
    if abstract and abstract_url:
        results.append(
            SearchResult(
                title=heading or query,
                snippet=abstract,
                url=abstract_url,
            )
        )

    _collect_related_topics(payload.get("RelatedTopics", []), results)
    return results


def _fetch_page_text(result: SearchResult, settings: Settings) -> SearchResult:
    try:
        page_html = _request_text(result.url, settings.web_search_timeout)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return result

    text = _clean_text(page_html)
    if len(text) > settings.web_search_page_chars:
        text = text[: settings.web_search_page_chars].rstrip() + "..."
    return SearchResult(
        title=result.title,
        snippet=result.snippet,
        url=result.url,
        page_text=text,
    )


def search_web(query: str, settings: Settings) -> list[SearchResult]:
    """Search the web and return a small list of text results."""

    try:
        results = _search_duckduckgo_html(query, settings)
    except (HTTPError, URLError, TimeoutError, ValueError):
        results = []

    if not results:
        try:
            results = _search_duckduckgo_instant(query, settings)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"联网搜索失败：{exc}") from exc

    deduped: list[SearchResult] = []
    seen_urls: set[str] = set()
    for result in results:
        if result.url in seen_urls:
            continue
        seen_urls.add(result.url)
        deduped.append(result)
        if len(deduped) >= settings.web_search_max_results:
            break

    if settings.web_search_fetch_pages:
        deduped = [_fetch_page_text(result, settings) for result in deduped]

    return deduped


def format_search_context(results: list[SearchResult]) -> str:
    """Format search results for the model prompt."""

    if not results:
        return "联网搜索没有返回可用结果。"

    lines = []
    for index, result in enumerate(results, start=1):
        page_text = f"\n网页正文摘录：{result.page_text}" if result.page_text else ""
        lines.append(
            f"[{index}] {result.title}\n"
            f"搜索摘要：{result.snippet}\n"
            f"链接：{result.url}"
            f"{page_text}"
        )
    return "\n\n".join(lines)
