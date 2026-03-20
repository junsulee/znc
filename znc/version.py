"""
znc 버전 및 빌드 정보.

빌드 번호는 git rev-list --count HEAD 로 자동 계산된다.
git 저장소 없이 설치된 환경에서는 pkg_resources 에서 읽는다.
"""
from __future__ import annotations

import os
import subprocess

VERSION = "0.3.0"


def _compute_build() -> str:
    # 1) git 커밋 수
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

    # 2) 설치된 패키지 메타데이터 폴백
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
