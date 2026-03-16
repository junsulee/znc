"""znc.backends — AI 백엔드 추상화"""
from znc.backends.base import BaseBackend
from znc.backends.ollama import OllamaBackend
from znc.backends.openai import OpenAIBackend

__all__ = ["BaseBackend", "OllamaBackend", "OpenAIBackend"]
