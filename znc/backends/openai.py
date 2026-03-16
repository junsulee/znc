"""
OpenAI 호환 백엔드 구현 (OpenAI, Azure OpenAI, LocalAI 등)
"""
from __future__ import annotations

from typing import Generator, Optional

from znc.backends.base import BaseBackend


class OpenAIBackend(BaseBackend):
    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _get_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "openai 패키지가 필요합니다. `pip install openai` 로 설치하세요."
            ) from exc
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _build_messages(self, prompt: str, system_prompt: Optional[str]) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        client = self._get_client()
        messages = self._build_messages(prompt, system_prompt)
        with client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
        ) as stream:
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        client = self._get_client()
        messages = self._build_messages(prompt, system_prompt)
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content or ""
