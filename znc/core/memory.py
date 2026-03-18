"""
장기 메모리 저장소.

~/.znc/memory/
    manual.json   — 사용자가 /remember 로 직접 저장한 항목
    auto.json     — AI 응답 분석으로 자동 추출된 항목
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from znc.core.config import ZNC_DIR, ensure_dirs

MEMORY_DIR = os.path.join(ZNC_DIR, "memory")
MANUAL_PATH = os.path.join(MEMORY_DIR, "manual.json")
AUTO_PATH = os.path.join(MEMORY_DIR, "auto.json")

# 프롬프트에 삽입할 최대 메모리 항목 수
MAX_CONTEXT_ITEMS = 10


@dataclass
class MemoryItem:
    key: str
    value: str
    source: str = "manual"   # "manual" | "auto"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryItem":
        return cls(
            key=d["key"],
            value=d["value"],
            source=d.get("source", "manual"),
            created_at=d.get("created_at", datetime.now().isoformat()),
        )


def _ensure_memory_dir() -> None:
    ensure_dirs()
    os.makedirs(MEMORY_DIR, exist_ok=True)


def _load(path: str) -> list[MemoryItem]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [MemoryItem.from_dict(d) for d in raw]


def _save(path: str, items: list[MemoryItem]) -> None:
    _ensure_memory_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump([i.to_dict() for i in items], f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_manual() -> list[MemoryItem]:
    return _load(MANUAL_PATH)


def load_auto() -> list[MemoryItem]:
    return _load(AUTO_PATH)


def load_all() -> list[MemoryItem]:
    return load_manual() + load_auto()


def add_manual(key: str, value: str) -> MemoryItem:
    items = load_manual()
    # 같은 key 가 있으면 덮어씀
    items = [i for i in items if i.key != key]
    item = MemoryItem(key=key, value=value, source="manual")
    items.append(item)
    _save(MANUAL_PATH, items)
    return item


def remove_manual(key: str) -> bool:
    items = load_manual()
    new_items = [i for i in items if i.key != key]
    if len(new_items) == len(items):
        return False
    _save(MANUAL_PATH, new_items)
    return True


def add_auto(key: str, value: str) -> MemoryItem:
    items = load_auto()
    items = [i for i in items if i.key != key]
    item = MemoryItem(key=key, value=value, source="auto")
    items.append(item)
    _save(AUTO_PATH, items)
    return item


def clear_all() -> None:
    _save(MANUAL_PATH, [])
    _save(AUTO_PATH, [])


def build_memory_context(query: str = "") -> str:
    """
    현재 메모리를 시스템 프롬프트에 삽입할 텍스트로 변환.
    query 가 주어지면 키워드 관련도 기준으로 상위 항목만 포함.
    """
    items = load_all()
    if not items:
        return ""

    if query:
        q = query.lower()
        scored = [
            (sum(w in (i.key + " " + i.value).lower() for w in q.split()), i)
            for i in items
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        items = [i for _, i in scored if _ > 0] or items
    items = items[:MAX_CONTEXT_ITEMS]

    lines = ["[기억]"] + [f"- {i.key}: {i.value}" for i in items]
    return "\n".join(lines)


def extract_and_save_auto(ai_response: str, backend) -> list[MemoryItem]:
    """
    AI 응답에서 기억할 만한 사실을 추출해 auto 메모리에 저장.
    백엔드에 짧은 분석 요청을 보냄.
    """
    prompt = (
        "아래 AI 응답에서 사용자에 대해 기억해둘 만한 사실(이름, 직업, 선호, 환경 등)이 있으면 "
        "JSON 배열로 추출해줘. 없으면 빈 배열 []을 반환해.\n"
        '형식: [{"key": "...", "value": "..."}]\n\n'
        f"응답:\n{ai_response[:1000]}\n\n결과:"
    )
    try:
        raw = backend.generate(prompt)
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        facts = json.loads(raw[start:end])
        saved = []
        for fact in facts[:5]:
            if isinstance(fact, dict) and "key" in fact and "value" in fact:
                saved.append(add_auto(fact["key"], fact["value"]))
        return saved
    except Exception:
        return []
