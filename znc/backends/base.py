"""
AI 백엔드 추상화 기본 클래스
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generator, Optional


class BaseBackend(ABC):
    """모든 AI 백엔드가 구현해야 하는 인터페이스."""

    @abstractmethod
    def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """스트리밍 텍스트 생성. 토큰 단위로 yield."""
        ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """단일 응답 생성."""
        ...

    @classmethod
    def from_settings(cls, settings: dict) -> "BaseBackend":
        backend = settings.get("backend", "ollama")
        if backend == "ollama":
            from znc.backends.ollama import OllamaBackend
            return OllamaBackend(
                server_url=settings["server_url"],
                model=settings["model"],
            )
        elif backend == "openai":
            from znc.backends.openai import OpenAIBackend
            return OpenAIBackend(
                api_key=settings.get("openai_api_key", ""),
                model=settings.get("openai_model", "gpt-4o"),
                base_url=settings.get("openai_base_url", "https://api.openai.com/v1"),
            )
        else:
            raise ValueError(f"알 수 없는 백엔드: {backend}")
