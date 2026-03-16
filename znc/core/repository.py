"""
프로젝트 저장소 — 프로젝트 생성/조회/삭제
"""
from __future__ import annotations

import json
import os
from typing import Optional

from znc.core.config import (
    PROJECTS_DIR,
    get_project_dir,
    get_project_settings_path,
    load_project_settings,
    save_project_settings,
    ensure_dirs,
)
from znc.core.models import Project, Session


class ProjectRepository:
    @staticmethod
    def create(name: str, description: str = "", system_prompt: str = "") -> Project:
        ensure_dirs()
        proj_dir = get_project_dir(name)
        os.makedirs(os.path.join(proj_dir, "sessions"), exist_ok=True)

        meta_path = os.path.join(proj_dir, "project.json")
        project = Project(name=name, description=description, system_prompt=system_prompt)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(project.to_dict(), f, indent=2, ensure_ascii=False)
        return project

    @staticmethod
    def get(name: str) -> Optional[Project]:
        meta_path = os.path.join(get_project_dir(name), "project.json")
        if not os.path.exists(meta_path):
            return None
        with open(meta_path, "r", encoding="utf-8") as f:
            return Project.from_dict(json.load(f))

    @staticmethod
    def list_all() -> list[Project]:
        ensure_dirs()
        projects = []
        if not os.path.exists(PROJECTS_DIR):
            return projects
        for entry in sorted(os.listdir(PROJECTS_DIR)):
            proj = ProjectRepository.get(entry)
            if proj:
                projects.append(proj)
        return projects

    @staticmethod
    def delete(name: str) -> bool:
        import shutil
        proj_dir = get_project_dir(name)
        if not os.path.exists(proj_dir):
            return False
        shutil.rmtree(proj_dir)
        return True

    @staticmethod
    def sessions_dir(name: str) -> str:
        return os.path.join(get_project_dir(name), "sessions")

    @staticmethod
    def list_sessions(name: str) -> list[str]:
        return Session.list_names(ProjectRepository.sessions_dir(name))
