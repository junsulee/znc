"""
Ollama 백엔드 구현
"""
from __future__ import annotations

import json
from typing import Generator, Optional

import requests

from znc.backends.base import BaseBackend


class OllamaBackend(BaseBackend):
    def __init__(self, server_url: str, model: str) -> None:
        self.server_url = server_url
        self.model = model

    def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        payload: dict = {"model": self.model, "prompt": prompt, "stream": True}
        if system_prompt:
            payload["system"] = system_prompt

        with requests.post(self.server_url, json=payload, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode("utf-8"))
                        text = data.get("response", "")
                        if text:
                            yield text
                    except json.JSONDecodeError:
                        continue

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        payload: dict = {"model": self.model, "prompt": prompt, "stream": False}
        if system_prompt:
            payload["system"] = system_prompt

        resp = requests.post(self.server_url, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
