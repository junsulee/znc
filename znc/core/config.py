"""
znc 전역 설정 관리 모듈
"""
import json
import os
from typing import Any

HOME = os.path.expanduser("~")
ZNC_DIR = os.path.join(HOME, ".znc")
SESSIONS_DIR = os.path.join(ZNC_DIR, "sessions")
PROJECTS_DIR = os.path.join(ZNC_DIR, "projects")
SETTINGS_PATH = os.path.join(ZNC_DIR, "settings.json")

DEFAULT_SETTINGS: dict[str, Any] = {
    "lang": "ko",
    "backend": "ollama",
    "server_url": "http://localhost:11434/api/generate",
    "model": "llama3.1:70b-instruct-q3_K_M",
    "ai_name": "znc",
    "openai_api_key": "",
    "openai_model": "gpt-4o",
    "openai_base_url": "https://api.openai.com/v1",
    "search_engines": ["ddg", "naver"],
    "google_serper_key": "",
}


def ensure_dirs() -> None:
    for d in [ZNC_DIR, SESSIONS_DIR, PROJECTS_DIR]:
        os.makedirs(d, exist_ok=True)


def load_settings() -> dict[str, Any]:
    ensure_dirs()
    if not os.path.exists(SETTINGS_PATH):
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        saved = json.load(f)
    merged = dict(DEFAULT_SETTINGS)
    merged.update(saved)
    return merged


def save_settings(settings: dict[str, Any]) -> None:
    ensure_dirs()
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def get_project_dir(project_name: str) -> str:
    return os.path.join(PROJECTS_DIR, project_name)


def get_project_sessions_dir(project_name: str) -> str:
    return os.path.join(get_project_dir(project_name), "sessions")


def get_project_settings_path(project_name: str) -> str:
    return os.path.join(get_project_dir(project_name), "settings.json")


def load_project_settings(project_name: str) -> dict[str, Any]:
    """프로젝트 설정을 불러옴. 전역 설정을 기본으로 하고 프로젝트 설정으로 덮어씀."""
    base = load_settings()
    path = get_project_settings_path(project_name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            project_cfg = json.load(f)
        base.update(project_cfg)
    return base


def save_project_settings(project_name: str, settings: dict[str, Any]) -> None:
    proj_dir = get_project_dir(project_name)
    os.makedirs(proj_dir, exist_ok=True)
    path = get_project_settings_path(project_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
