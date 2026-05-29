"""Lightweight web search helpers."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from langchain_starter.config import Settings


@dataclass(frozen=True)
class SearchResult:
    """联网搜索结果的标准数据结构。"""

    title: str
    snippet: str
    url: str
    page_text: str = ""


def _request_text(url: str, timeout: float) -> str:
    """发起 HTTP 请求并返回文本内容。"""
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
    """清洗 HTML 文本，去掉脚本、样式和多余空白。"""
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _decode_duckduckgo_url(url: str) -> str:
    """解码 DuckDuckGo 搜索结果里的跳转链接。"""
    parsed = urlparse(html.unescape(url))
    if "duckduckgo.com" not in parsed.netloc:
        return html.unescape(url)

    query = parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return unquote(query["uddg"][0])
    return html.unescape(url)


def _extract_duckduckgo_html_results(page_html: str) -> list[SearchResult]:
    """从 DuckDuckGo HTML 页面中提取搜索结果。"""
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


def _decode_baidu_url(url: str) -> str:
    """解码百度搜索结果里的相对链接或跳转链接。"""
    url = html.unescape(url)
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return urljoin("https://www.baidu.com", url)
    return url


def _extract_baidu_results(page_html: str) -> list[SearchResult]:
    """从百度搜索页面中提取结果。"""
    if "百度安全验证" in page_html or "wappass.baidu.com" in page_html:
        return []

    results: list[SearchResult] = []
    blocks = re.findall(
        r'<div[^>]+(?:class="[^"]*\bresult\b[^"]*"|tpl="[^"]+")[\s\S]*?</div>\s*</div>',
        page_html,
        flags=re.IGNORECASE,
    )
    if not blocks:
        blocks = re.findall(
            r'<h3[\s\S]*?</h3>[\s\S]*?(?=<h3|<div id="page"|</body>)',
            page_html,
            flags=re.IGNORECASE,
        )

    for block in blocks:
        title_match = re.search(
            r'<h3[^>]*>[\s\S]*?<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>[\s\S]*?</h3>',
            block,
            flags=re.IGNORECASE,
        )
        if not title_match:
            title_match = re.search(
                r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>',
                block,
                flags=re.IGNORECASE,
            )
        if not title_match:
            continue

        url = _decode_baidu_url(title_match.group(1))
        title = _clean_text(title_match.group(2))
        snippet = _clean_text(re.sub(r"<h3[\s\S]*?</h3>", " ", block, flags=re.IGNORECASE))
        if len(snippet) > 260:
            snippet = snippet[:260].rstrip() + "..."
        if title and url:
            results.append(SearchResult(title=title, snippet=snippet or title, url=url))

    return results


def _search_baidu_html(query: str, settings: Settings) -> list[SearchResult]:
    """使用百度 HTML 搜索接口抓取结果。"""
    params = urlencode({"wd": query, "rn": settings.web_search_max_results})
    page_html = _request_text(
        f"https://www.baidu.com/s?{params}",
        settings.web_search_timeout,
    )
    return _extract_baidu_results(page_html)


def _extract_sogou_results(page_html: str) -> list[SearchResult]:
    """从搜狗搜索页面中提取结果。"""
    results: list[SearchResult] = []
    blocks = re.findall(
        r'<div[^>]+class="[^"]*(?:vrwrap|results|rb)[^"]*"[\s\S]*?(?=<div[^>]+class="[^"]*(?:vrwrap|results|rb)[^"]*"|<div id="pagebar_container"|</body>)',
        page_html,
        flags=re.IGNORECASE,
    )
    if not blocks:
        blocks = re.findall(
            r'<h3[^>]*>[\s\S]*?</h3>[\s\S]*?(?=<h3|<div id="pagebar_container"|</body>)',
            page_html,
            flags=re.IGNORECASE,
        )

    for block in blocks:
        title_match = re.search(
            r'<h3[^>]*>[\s\S]*?<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>[\s\S]*?</h3>',
            block,
            flags=re.IGNORECASE,
        )
        if not title_match:
            title_match = re.search(
                r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>',
                block,
                flags=re.IGNORECASE,
            )
        if not title_match:
            continue

        url = html.unescape(title_match.group(1))
        if url.startswith("//"):
            url = f"https:{url}"
        elif url.startswith("/"):
            url = urljoin("https://www.sogou.com", url)

        title = _clean_text(title_match.group(2))
        snippet_source = re.sub(r"<h3[\s\S]*?</h3>", " ", block, flags=re.IGNORECASE)
        snippet = _clean_text(snippet_source)
        if len(snippet) > 300:
            snippet = snippet[:300].rstrip() + "..."
        if title and url.startswith(("http://", "https://")) and "javascript:" not in url:
            results.append(SearchResult(title=title, snippet=snippet or title, url=url))

    return results


def _search_sogou_html(query: str, settings: Settings) -> list[SearchResult]:
    """使用搜狗搜索接口抓取结果。"""
    params = urlencode({"query": query})
    page_html = _request_text(
        f"https://www.sogou.com/web?{params}",
        settings.web_search_timeout,
    )
    return _extract_sogou_results(page_html)


def _extract_bing_results(page_html: str) -> list[SearchResult]:
    """从 Bing 搜索页面中提取结果。"""
    results: list[SearchResult] = []
    blocks = re.findall(
        r'<li[^>]+class="[^"]*b_algo[^"]*"[\s\S]*?</li>',
        page_html,
        flags=re.IGNORECASE,
    )
    for block in blocks:
        title_match = re.search(
            r'<h2[^>]*>[\s\S]*?<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>[\s\S]*?</h2>',
            block,
            flags=re.IGNORECASE,
        )
        if not title_match:
            continue
        snippet_match = re.search(
            r'<p[^>]*>([\s\S]*?)</p>',
            block,
            flags=re.IGNORECASE,
        )
        url = html.unescape(title_match.group(1))
        title = _clean_text(title_match.group(2))
        snippet = _clean_text(snippet_match.group(1)) if snippet_match else title
        if title and url:
            results.append(SearchResult(title=title, snippet=snippet, url=url))
    return results


def _search_bing_html(query: str, settings: Settings) -> list[SearchResult]:
    """使用 Bing 搜索接口抓取结果。"""
    params = urlencode({"q": query, "setlang": "zh-CN"})
    page_html = _request_text(
        f"https://www.bing.com/search?{params}",
        settings.web_search_timeout,
    )
    return _extract_bing_results(page_html)


def _search_duckduckgo_html(query: str, settings: Settings) -> list[SearchResult]:
    """使用 DuckDuckGo HTML 页面抓取结果。"""
    params = urlencode({"q": query})
    page_html = _request_text(
        f"https://duckduckgo.com/html/?{params}",
        settings.web_search_timeout,
    )
    return _extract_duckduckgo_html_results(page_html)


def _collect_related_topics(items: list[dict], results: list[SearchResult]) -> None:
    """递归收集 DuckDuckGo instant answer 里的相关主题。"""
    for item in items:
        if "Topics" in item:
            _collect_related_topics(item.get("Topics", []), results)
            continue

        title = str(item.get("Text", "")).strip()
        url = str(item.get("FirstURL", "")).strip()
        if title and url:
            results.append(SearchResult(title=title, snippet=title, url=url))


def _search_duckduckgo_instant(query: str, settings: Settings) -> list[SearchResult]:
    """使用 DuckDuckGo instant answer API 抓取结果。"""
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
    """抓取单个结果页正文，用于补充搜索摘要。"""
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
    """执行联网搜索，并返回去重后的文本结果列表。"""

    provider = settings.web_search_provider
    if provider not in {"auto", "baidu", "sogou", "bing", "duckduckgo"}:
        provider = "auto"

    search_errors: list[str] = []
    searchers = []
    if provider in {"auto", "baidu"}:
        searchers.append(("baidu", _search_baidu_html))
    if provider in {"auto", "sogou"}:
        searchers.append(("sogou", _search_sogou_html))
    if provider in {"auto", "bing"}:
        searchers.append(("bing", _search_bing_html))
    if provider in {"auto", "duckduckgo"}:
        searchers.append(("duckduckgo-html", _search_duckduckgo_html))
        searchers.append(("duckduckgo-api", _search_duckduckgo_instant))

    results: list[SearchResult] = []
    for name, searcher in searchers:
        try:
            results = searcher(query, settings)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            search_errors.append(f"{name}: {exc}")
            continue
        if not results:
            search_errors.append(f"{name}: 没有解析到搜索结果")
        if results:
            break

    if not results and search_errors:
        raise RuntimeError("联网搜索失败：" + "；".join(search_errors))
    if not results:
        raise RuntimeError("联网搜索失败：所有搜索源都没有返回可用结果。")

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
    """把搜索结果整理成可直接喂给模型的上下文字符串。"""

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
