"""
웹 검색 + 크롤링 모듈.

DuckDuckGo HTML 검색(API 없음) → 상위 URL 추출 → BeautifulSoup 본문 크롤링.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}
DDG_URL = "https://html.duckduckgo.com/html/"
MAX_RESULTS = 5
MAX_BODY_CHARS = 2000
REQUEST_TIMEOUT = 10


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    body: str = ""


def search(query: str, max_results: int = MAX_RESULTS) -> list[SearchResult]:
    """DuckDuckGo HTML 검색 → 상위 결과 반환."""
    try:
        resp = requests.post(
            DDG_URL,
            data={"q": query, "kl": "kr-ko"},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as e:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results: list[SearchResult] = []

    for tag in soup.select(".result__body")[:max_results * 2]:
        title_tag = tag.select_one(".result__title a")
        snippet_tag = tag.select_one(".result__snippet")
        if not title_tag:
            continue
        href = title_tag.get("href", "")
        # DDG redirect URL에서 실제 URL 추출
        url = _extract_url(href)
        if not url or not url.startswith("http"):
            continue
        results.append(
            SearchResult(
                title=title_tag.get_text(strip=True),
                url=url,
                snippet=snippet_tag.get_text(strip=True) if snippet_tag else "",
            )
        )
        if len(results) >= max_results:
            break

    return results


def crawl(url: str, max_chars: int = MAX_BODY_CHARS) -> str:
    """URL 본문 텍스트 추출. 실패 시 빈 문자열 반환."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "")
        if "text/html" not in ct:
            return ""
    except Exception:
        return ""

    soup = BeautifulSoup(resp.text, "lxml")

    # 불필요한 태그 제거
    for tag in soup(["script", "style", "nav", "header", "footer",
                     "aside", "form", "iframe", "noscript", "ads"]):
        tag.decompose()

    # 본문 우선 추출
    for selector in ["article", "main", "[role='main']", ".content", "#content", "body"]:
        node = soup.select_one(selector)
        if node:
            text = node.get_text(separator="\n", strip=True)
            text = _clean_text(text)
            if len(text) > 200:
                return text[:max_chars]

    return ""


def search_and_crawl(
    query: str,
    max_results: int = MAX_RESULTS,
    progress_callback=None,
) -> tuple[list[SearchResult], str]:
    """
    검색 후 크롤링까지 수행.
    progress_callback(url, done, total) 형태로 진행상황 알림.
    반환: (results, context_text)
    """
    results = search(query, max_results)
    if not results:
        return [], ""

    for i, r in enumerate(results):
        if progress_callback:
            progress_callback(r.url, i, len(results))
        r.body = crawl(r.url)
        time.sleep(0.3)

    if progress_callback:
        progress_callback("", len(results), len(results))

    context = _build_context(query, results)
    return results, context


def _build_context(query: str, results: list[SearchResult]) -> str:
    lines = [f'[웹 검색: "{query}"]']
    for i, r in enumerate(results, 1):
        domain = urlparse(r.url).netloc
        body = r.body or r.snippet
        if body:
            lines.append(f"\n[{i}] {r.title} ({domain})")
            lines.append(body[:MAX_BODY_CHARS])
    return "\n".join(lines)


def _extract_url(href: str) -> str:
    """DDG 리다이렉트 href에서 실제 URL 추출."""
    # //duckduckgo.com/l/?uddg=https%3A...
    m = re.search(r"uddg=([^&]+)", href)
    if m:
        from urllib.parse import unquote
        return unquote(m.group(1))
    if href.startswith("http"):
        return href
    return ""


def _clean_text(text: str) -> str:
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l and len(l) > 20]
    # 연속 빈 줄 제거
    result, prev_empty = [], False
    for l in lines:
        if not l:
            if not prev_empty:
                result.append(l)
            prev_empty = True
        else:
            result.append(l)
            prev_empty = False
    return "\n".join(result)
