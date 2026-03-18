"""
Persona 관리 — 시스템 프롬프트 템플릿 + Few-shot 예시 묶음.

~/.znc/personas/
    default.json
    senior-dev.json
    ...
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from znc.core.config import ZNC_DIR, ensure_dirs

PERSONAS_DIR = os.path.join(ZNC_DIR, "personas")

DEFAULT_PERSONA_NAME = "default"

DEFAULT_PERSONA_DATA = {
    "name": "default",
    "description": "기본 어시스턴트",
    "system_prompt": "You are a helpful assistant.",
    "few_shots": [],
    "style": {"tone": "neutral", "lang": "ko", "format": "markdown"},
    "created_at": "",
}


@dataclass
class FewShot:
    user: str
    assistant: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FewShot":
        return cls(user=d["user"], assistant=d["assistant"])


@dataclass
class Persona:
    name: str
    description: str = ""
    system_prompt: str = "You are a helpful assistant."
    few_shots: list[FewShot] = field(default_factory=list)
    style: dict = field(default_factory=lambda: {"tone": "neutral", "lang": "ko", "format": "markdown"})
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["few_shots"] = [fs.to_dict() for fs in self.few_shots]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Persona":
        few_shots = [FewShot.from_dict(fs) for fs in d.get("few_shots", [])]
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            system_prompt=d.get("system_prompt", "You are a helpful assistant."),
            few_shots=few_shots,
            style=d.get("style", {}),
            created_at=d.get("created_at", datetime.now().isoformat()),
        )

    def build_system_prompt(self, extra_context: str = "") -> str:
        """few-shot 예시와 메모리 컨텍스트를 포함한 완성 시스템 프롬프트 반환."""
        parts = [self.system_prompt]
        if extra_context:
            parts.append(extra_context)
        if self.few_shots:
            parts.append("\n--- 예시 대화 ---")
            for fs in self.few_shots:
                parts.append(f"User: {fs.user}")
                parts.append(f"Assistant: {fs.assistant}")
            parts.append("--- 예시 끝 ---")
        return "\n".join(parts)

    def save(self) -> None:
        _ensure_personas_dir()
        path = os.path.join(PERSONAS_DIR, f"{self.name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


def _ensure_personas_dir() -> None:
    ensure_dirs()
    os.makedirs(PERSONAS_DIR, exist_ok=True)


def load_persona(name: str) -> Optional[Persona]:
    path = os.path.join(PERSONAS_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return Persona.from_dict(json.load(f))


def load_default_persona() -> Persona:
    p = load_persona(DEFAULT_PERSONA_NAME)
    if p is None:
        p = Persona(name=DEFAULT_PERSONA_NAME, description="기본 어시스턴트")
        p.save()
    return p


def list_personas() -> list[Persona]:
    _ensure_personas_dir()
    result = []
    for fname in sorted(os.listdir(PERSONAS_DIR)):
        if fname.endswith(".json"):
            p = load_persona(fname[:-5])
            if p:
                result.append(p)
    if not result:
        result.append(load_default_persona())
    return result


def delete_persona(name: str) -> bool:
    path = os.path.join(PERSONAS_DIR, f"{name}.json")
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True
