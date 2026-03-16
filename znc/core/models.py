"""
대화 메시지 및 세션 모델 정의
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class Message:
    role: str          # "user" | "assistant" | "system"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(
            role=d["role"],
            content=d["content"],
            timestamp=d.get("timestamp", datetime.now().isoformat()),
        )


@dataclass
class Session:
    name: str
    messages: list[Message] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    project: Optional[str] = None
    system_prompt: Optional[str] = None

    def append(self, message: Message) -> None:
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "project": self.project,
            "system_prompt": self.system_prompt,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        messages = [Message.from_dict(m) for m in d.get("messages", [])]
        return cls(
            name=d["name"],
            messages=messages,
            created_at=d.get("created_at", datetime.now().isoformat()),
            updated_at=d.get("updated_at", datetime.now().isoformat()),
            project=d.get("project"),
            system_prompt=d.get("system_prompt"),
        )

    def save(self, sessions_dir: str) -> str:
        os.makedirs(sessions_dir, exist_ok=True)
        path = os.path.join(sessions_dir, f"{self.name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return path

    @classmethod
    def load(cls, sessions_dir: str, name: str) -> "Session":
        if not name.endswith(".json"):
            name += ".json"
        path = os.path.join(sessions_dir, name)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    @staticmethod
    def list_names(sessions_dir: str) -> list[str]:
        if not os.path.exists(sessions_dir):
            return []
        return [f[:-5] for f in sorted(os.listdir(sessions_dir)) if f.endswith(".json")]


@dataclass
class Project:
    name: str
    description: str = ""
    system_prompt: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            system_prompt=d.get("system_prompt", ""),
            created_at=d.get("created_at", datetime.now().isoformat()),
        )
