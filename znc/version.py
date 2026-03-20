"""
znc 버전 및 빌드 정보.

빌드 번호 우선순위:
  1. znc/_build_info.py (pipx install . --force 시 자동 생성)
  2. git rev-list --count HEAD (소스에서 직접 실행 시)
  3. importlib.metadata 의 X-Build-Number 헤더
  4. "0" (fallback)

버전 정책:
  - MAJOR.MINOR.PATCH
  - 기능 추가/변경 시 MINOR 또는 PATCH 증가 (커밋 전 수동 업데이트)
  - 빌드 번호는 git 커밋 수로 자동 결정
"""
from __future__ import annotations

import os
import subprocess

VERSION = "0.3.1"


def _compute_build() -> str:
    # 1) 패키지 빌드 시 생성된 _build_info.py (설치 환경에서도 동작)
    try:
        from znc._build_info import BUILD_NUMBER  # type: ignore
        return str(BUILD_NUMBER)
    except ImportError:
        pass

    # 2) git 커밋 수 (소스 실행 환경)
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=here,
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            count = result.stdout.strip()
            if count:
                return count
    except Exception:
        pass

    # 3) importlib.metadata
    try:
        from importlib.metadata import metadata as _meta
        m = _meta("znc")
        build = m.get("X-Build-Number", "")
        if build:
            return build
    except Exception:
        pass

    return "0"


BUILD: str = _compute_build()
