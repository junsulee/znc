"""
콘텐츠 타입 자동 감지 및 추출 모듈.

AI 응답에서 코드 블록, JSON, CSV 등을 감지하고
저장에 적합한 확장자와 정제된 내용을 반환한다.
"""
from __future__ import annotations

import re
import json as _json
from datetime import datetime
from typing import NamedTuple

# 마크다운 언어 식별자 → 확장자
LANG_TO_EXT: dict[str, str] = {
    "python": "py",    "py": "py",
    "javascript": "js", "js": "js",  "jsx": "jsx",
    "typescript": "ts", "ts": "ts",  "tsx": "tsx",
    "bash": "sh",      "shell": "sh", "sh": "sh", "zsh": "sh",
    "sql": "sql",
    "html": "html",    "htm": "html",
    "css": "css",      "scss": "scss",
    "java": "java",
    "rust": "rs",      "rs": "rs",
    "go": "go",
    "yaml": "yaml",    "yml": "yaml",
    "json": "json",
    "toml": "toml",
    "xml": "xml",
    "cpp": "cpp",      "c++": "cpp", "cc": "cpp",
    "c": "c",
    "markdown": "md",  "md": "md",
    "r": "r",
    "ruby": "rb",      "rb": "rb",
    "php": "php",
    "swift": "swift",
    "kotlin": "kt",    "kts": "kt",
    "csv": "csv",
    "diff": "diff",    "patch": "diff",
}

EXT_DISPLAY: dict[str, str] = {
    "py": "Python",   "js": "JavaScript", "ts": "TypeScript",
    "sh": "Shell",    "sql": "SQL",       "html": "HTML",
    "css": "CSS",     "java": "Java",     "rs": "Rust",
    "go": "Go",       "yaml": "YAML",     "json": "JSON",
    "toml": "TOML",   "xml": "XML",       "cpp": "C++",
    "c": "C",         "md": "Markdown",   "txt": "Plain text",
    "r": "R",         "rb": "Ruby",       "php": "PHP",
    "swift": "Swift", "kt": "Kotlin",     "csv": "CSV",
    "diff": "Diff/Patch",
}

# 저장 가능한 주요 포맷 목록 (버튼으로 표시)
QUICK_FORMATS = ["md", "txt", "py", "js", "json", "csv", "sh", "sql"]


class DetectResult(NamedTuple):
    ext: str          # 확장자 (py, md, csv …)
    display: str      # 표시용 이름 (Python, Markdown …)
    content: str      # 저장할 정제된 내용
    filename: str     # 추천 파일명 (확장자 포함)


def detect_and_extract(raw: str) -> DetectResult:
    """
    AI 응답에서 콘텐츠 타입을 감지하고 저장에 적합한 형태로 반환한다.

    우선순위:
      1. 단일 코드 블록 (전체가 ```lang...```)
      2. 복수 코드 블록 중 첫 번째 인식 언어
      3. JSON 구조
      4. CSV 패턴
      5. 기본값: Markdown
    """
    stripped = raw.strip()

    # 1. 전체가 단일 코드 블록인지 확인
    single = re.fullmatch(r"```(\w*)\s*\n(.*?)\n?```", stripped, re.DOTALL)
    if single:
        lang = single.group(1).lower()
        code = single.group(2)
        ext = LANG_TO_EXT.get(lang)
        if ext:
            return DetectResult(ext, EXT_DISPLAY.get(ext, ext), code, _suggest_filename(code, ext))

    # 2. 복수 코드 블록 중 첫 인식 언어
    blocks = re.findall(r"```(\w+)\s*\n(.*?)```", stripped, re.DOTALL)
    if blocks:
        for lang, code in blocks:
            ext = LANG_TO_EXT.get(lang.lower())
            if ext:
                # 단일 코드 블록이면 코드만, 복수면 Markdown 그대로
                content = code if len(blocks) == 1 else raw
                actual_ext = ext if len(blocks) == 1 else "md"
                display = EXT_DISPLAY.get(actual_ext, actual_ext)
                return DetectResult(actual_ext, display, content, _suggest_filename(content, actual_ext))

    # 3. JSON 감지
    if stripped.startswith(("{", "[")):
        try:
            obj = _json.loads(stripped)
            pretty = _json.dumps(obj, ensure_ascii=False, indent=2)
            return DetectResult("json", "JSON", pretty, _suggest_filename(pretty, "json"))
        except Exception:
            pass

    # 4. CSV 감지 (3줄 이상, 쉼표 수 일정)
    lines = [l for l in stripped.split("\n") if l.strip()]
    if len(lines) >= 3:
        commas = [l.count(",") for l in lines[:10]]
        if min(commas) >= 1 and max(commas) - min(commas) <= 2:
            return DetectResult("csv", "CSV", stripped, _suggest_filename(stripped, "csv"))

    # 5. 기본값: Markdown
    return DetectResult("md", "Markdown", raw, _suggest_filename(raw, "md"))


def _suggest_filename(content: str, ext: str) -> str:
    """내용에서 의미 있는 파일명을 추출한다."""
    name = ""

    if ext == "py":
        m = re.search(r"(?:def|class)\s+(\w+)", content)
        if m:
            name = m.group(1)
    elif ext in ("js", "ts"):
        m = re.search(r"(?:function|class|const|let|var)\s+(\w+)", content)
        if m:
            name = m.group(1)
    elif ext == "sql":
        m = re.search(r"(?:CREATE|SELECT|INSERT|UPDATE|DELETE)\s+(?:TABLE\s+)?(\w+)", content, re.I)
        if m:
            name = m.group(1).lower()
    elif ext == "json":
        m = re.search(r'"(\w+)"\s*:', content)
        if m:
            name = m.group(1)
    elif ext in ("md", "txt"):
        # 첫 번째 헤딩 또는 첫 줄
        m = re.search(r"^#+\s*(.+)$", content, re.MULTILINE)
        if m:
            name = re.sub(r"[^\w\s-]", "", m.group(1)).strip().replace(" ", "_")[:30]
        else:
            first = content.strip().split("\n")[0][:40]
            name = re.sub(r"[^\w\s-]", "", first).strip().replace(" ", "_")[:30]

    if not name:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"export_{ts}"

    # 파일명 안전화
    name = re.sub(r"[^\w\-]", "_", name).strip("_")
    return f"{name}.{ext}"


def clean_content_for_ext(content: str, ext: str) -> str:
    """저장 전 마지막 정리 (코드 블록 래퍼 제거 등)."""
    if ext in LANG_TO_EXT.values() and ext not in ("md", "txt"):
        # 단일 코드 블록 래퍼 제거 시도
        m = re.fullmatch(r"```\w*\s*\n(.*?)\n?```", content.strip(), re.DOTALL)
        if m:
            return m.group(1)
    return content
