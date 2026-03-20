"""
웹 검색 + 크롤링 모듈.

지원 검색 엔진:
  - DuckDuckGo  : 기본값. HTML POST 엔드포인트, API 불필요.
  - Naver       : webkr 탭 HTML 파싱, API 불필요.
  - Google      : JS 렌더링 필요로 순수 크롤링 불가.
                  Serper.dev API (무료 2500회/월, 선택적) 를 통해 지원.

검색 엔진 우선순위:
  설정에서 engines 리스트 지정 (기본: ["ddg", "naver"])
  각 엔진에서 max_results 만큼 수집 후 중복 URL 제거.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# 공통 상수
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}
MAX_RESULTS = 5
MAX_BODY_CHARS = 2000
REQUEST_TIMEOUT = 10

ProgressCallback = Callable[[str, int, int], None]


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------
@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    engine: str = ""
    body: str = ""


# ---------------------------------------------------------------------------
# DuckDuckGo
# ---------------------------------------------------------------------------
def _search_ddg(query: str, max_results: int, freshness: str = "") -> list[SearchResult]:
    """DuckDuckGo HTML POST 검색.

    freshness: ""=전체  "d"=하루  "w"=1주  "m"=1달
    """
    data: dict = {"q": query, "kl": "kr-ko"}
    if freshness:
        data["df"] = freshness
    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data=data,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results: list[SearchResult] = []

    for tag in soup.select(".result__body"):
        title_tag = tag.select_one(".result__title a")
        snippet_tag = tag.select_one(".result__snippet")
        if not title_tag:
            continue
        href = title_tag.get("href", "")
        url = _ddg_extract_url(href)
        if not url or not url.startswith("http"):
            continue
        results.append(SearchResult(
            title=title_tag.get_text(strip=True),
            url=url,
            snippet=snippet_tag.get_text(strip=True) if snippet_tag else "",
            engine="ddg",
        ))
        if len(results) >= max_results:
            break

    return results


def _ddg_extract_url(href: str) -> str:
    m = re.search(r"uddg=([^&]+)", href)
    if m:
        return urllib.parse.unquote(m.group(1))
    if href.startswith("http"):
        return href
    return ""


# ---------------------------------------------------------------------------
# Naver
# ---------------------------------------------------------------------------
def _search_naver(query: str, max_results: int, freshness: str = "") -> list[SearchResult]:
    """Naver 웹탭(webkr) HTML 크롤링.

    freshness: ""=전체  "d"=하루  "w"=1주  "m"=1달
    """
    params: dict = {"query": query, "where": "webkr"}
    if freshness:
        # so:r = 최신순, p:1w/p:1d/p:1m = 기간
        period = {"d": "1d", "w": "1w", "m": "1m"}.get(freshness, "")
        if period:
            params["nso"] = f"p:{period},so:r"
    try:
        resp = requests.get(
            "https://search.naver.com/search.naver",
            params=params,
            headers={**HEADERS, "Referer": "https://www.naver.com"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for bx in soup.select(".api_subject_bx"):
        # naver 도메인이 아닌 외부 링크만 수집
        ext_links = [
            a for a in bx.find_all("a", href=True)
            if a["href"].startswith("http") and "naver" not in a["href"]
        ]
        if not ext_links:
            continue

        url = ext_links[0]["href"].split("?")[0] if "?" in ext_links[0]["href"] else ext_links[0]["href"]
        # 인코딩된 URL 정규화
        url = urllib.parse.unquote(url)
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # 제목: 텍스트가 충분히 긴 첫 번째 인라인 요소
        title = _naver_extract_title(bx, url)

        # 스니펫
        snip_el = (
            bx.select_one(".dsc_txt_wrap")
            or bx.select_one(".total_dsc")
            or bx.select_one("p")
        )
        snippet = snip_el.get_text(strip=True) if snip_el else ""

        results.append(SearchResult(
            title=title,
            url=url,
            snippet=snippet,
            engine="naver",
        ))
        if len(results) >= max_results:
            break

    return results


def _naver_extract_title(bx, fallback_url: str) -> str:
    """네이버 결과 블록에서 기사 제목 텍스트 추출."""
    # 외부 링크 중 텍스트에 '›'(breadcrumb) 없고 가장 긴 것
    candidates = []
    for a in bx.find_all("a", href=True):
        href = a.get("href", "")
        if not (href.startswith("http") and "naver" not in href):
            continue
        t = a.get_text(strip=True)
        # breadcrumb 라벨 제외, 날짜 제외, 의미있는 길이
        if "›" in t or len(t) < 8 or len(t) > 150:
            continue
        # 도메인만 있는 경우 제외
        try:
            import urllib.parse as _up
            domain = _up.urlparse(href).netloc
            if t.lower().replace("www.", "") == domain.replace("www.", ""):
                continue
        except Exception:
            pass
        candidates.append((len(t), t))

    if candidates:
        candidates.sort(reverse=True)
        title = candidates[0][1]
        # 앞에 붙는 날짜 패턴 제거 (예: "2024.10.08.제목...")
        title = re.sub(r"^\d{4}\.\d{2}\.\d{2}\.", "", title).strip()
        return title

    return urllib.parse.urlparse(fallback_url).netloc


# ---------------------------------------------------------------------------
# Google (Serper.dev — 선택적)
# ---------------------------------------------------------------------------
def _search_google_serper(query: str, max_results: int, api_key: str) -> list[SearchResult]:
    """
    Serper.dev API를 통한 Google 검색.
    무료 플랜: 2500회/월. https://serper.dev 에서 키 발급.
    """
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            json={"q": query, "gl": "kr", "hl": "ko", "num": max_results},
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    results: list[SearchResult] = []
    for item in data.get("organic", [])[:max_results]:
        results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("link", ""),
            snippet=item.get("snippet", ""),
            engine="google",
        ))
    return results


# ---------------------------------------------------------------------------
# 크롤링
# ---------------------------------------------------------------------------
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
    for tag in soup(["script", "style", "nav", "header", "footer",
                     "aside", "form", "iframe", "noscript"]):
        tag.decompose()

    for selector in ["article", "main", "[role='main']", ".content",
                     "#content", "#main", ".post-content", "body"]:
        node = soup.select_one(selector)
        if node:
            text = node.get_text(separator="\n", strip=True)
            text = _clean_text(text)
            if len(text) > 200:
                return text[:max_chars]
    return ""


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------
def search(
    query: str,
    engines: list[str] | None = None,
    max_results: int = MAX_RESULTS,
    google_serper_key: str = "",
    freshness: str = "",
) -> list[SearchResult]:
    """
    여러 엔진에서 검색 후 중복 URL 제거한 결과 반환.

    engines: ["ddg", "naver", "google"] 순서대로 시도.
             기본값: ["ddg", "naver"]
             "google"은 google_serper_key 가 있을 때만 동작.
    freshness: ""=전체  "d"=하루  "w"=1주  "m"=1달
    """
    if engines is None:
        engines = ["ddg", "naver"]

    all_results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for engine in engines:
        partial: list[SearchResult] = []
        remaining = max_results - len(all_results)
        if remaining <= 0:
            break

        if engine == "ddg":
            partial = _search_ddg(query, remaining, freshness)
        elif engine == "naver":
            partial = _search_naver(query, remaining, freshness)
        elif engine == "google":
            if google_serper_key:
                partial = _search_google_serper(query, remaining, google_serper_key)

        for r in partial:
            if r.url and r.url not in seen_urls:
                seen_urls.add(r.url)
                all_results.append(r)
            if len(all_results) >= max_results:
                break

    return all_results


def search_and_crawl(
    query: str,
    engines: list[str] | None = None,
    max_results: int = MAX_RESULTS,
    google_serper_key: str = "",
    freshness: str = "",
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[SearchResult], str]:
    """
    검색 + 크롤링 일괄 수행.
    progress_callback(url, done, total) 으로 진행 상황 전달.
    freshness: ""=전체  "d"=하루  "w"=1주  "m"=1달
    반환: (results, context_text)
    """
    results = search(query, engines=engines, max_results=max_results,
                     google_serper_key=google_serper_key, freshness=freshness)
    if not results:
        return [], ""

    total = len(results)
    for i, r in enumerate(results):
        if progress_callback:
            progress_callback(r.url, i, total)
        r.body = crawl(r.url)
        time.sleep(0.25)

    if progress_callback:
        progress_callback("", total, total)

    context = _build_context(query, results)
    return results, context


# ---------------------------------------------------------------------------
# 내부 유틸
# ---------------------------------------------------------------------------
def _build_context(query: str, results: list[SearchResult]) -> str:
    lines = [f'[web search: "{query}"]']
    for i, r in enumerate(results, 1):
        domain = urllib.parse.urlparse(r.url).netloc
        body = r.body or r.snippet
        if body:
            lines.append(f"\n[{i}] {r.title} ({domain}) [{r.engine}]")
            lines.append(body[:MAX_BODY_CHARS])
    return "\n".join(lines)


def _clean_text(text: str) -> str:
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l and len(l) > 20]
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
