"""
ProcessState — 단계 정의 및 상태 관리 모델.
app.py 와 위젯 양쪽에서 공유하기 위해 별도 모듈로 분리.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import monotonic
from typing import Optional


class Stage(str, Enum):
    IDLE       = "idle"
    LOADING    = "loading"
    MEMORY     = "memory"
    SEARCH     = "search"
    CRAWL      = "crawl"
    THINKING   = "thinking"
    GENERATING = "generating"
    DONE       = "done"
    ERROR      = "error"


# 각 단계에 표시할 레이블
STAGE_LABEL: dict[Stage, str] = {
    Stage.IDLE:       "",
    Stage.LOADING:    "preparing",
    Stage.MEMORY:     "memory",
    Stage.SEARCH:     "searching",
    Stage.CRAWL:      "crawling",
    Stage.THINKING:   "thinking",
    Stage.GENERATING: "generating",
    Stage.DONE:       "done",
    Stage.ERROR:      "error",
}

# 단계별 색상 (Rich style)
STAGE_STYLE: dict[Stage, str] = {
    Stage.IDLE:       "dim",
    Stage.LOADING:    "#8b949e",
    Stage.MEMORY:     "#58a6ff",
    Stage.SEARCH:     "#d29922",
    Stage.CRAWL:      "#d29922",
    Stage.THINKING:   "#79c0ff",
    Stage.GENERATING: "#3fb950",
    Stage.DONE:       "dim #3fb950",
    Stage.ERROR:      "#f85149",
}


@dataclass
class StepRecord:
    """ProcessLog 에 기록될 단일 단계 로그 항목."""
    stage: Stage
    detail: str = ""
    elapsed: float = 0.0     # 이 단계가 시작된 시점의 전체 경과 시간


@dataclass
class ProcessState:
    """한 번의 응답 생성 전체 상태."""
    stage: Stage = Stage.IDLE
    detail: str = ""
    steps: list[StepRecord] = field(default_factory=list)
    _start: float = field(default_factory=monotonic, repr=False)
    _stage_start: float = field(default_factory=monotonic, repr=False)

    def transition(self, stage: Stage, detail: str = "") -> StepRecord:
        now = monotonic()
        elapsed = now - self._start
        record = StepRecord(stage=stage, detail=detail, elapsed=elapsed)
        self.steps.append(record)
        self.stage = stage
        self.detail = detail
        self._stage_start = now
        return record

    @property
    def total_elapsed(self) -> float:
        return monotonic() - self._start

    @property
    def stage_elapsed(self) -> float:
        return monotonic() - self._stage_start

    def reset(self) -> None:
        now = monotonic()
        self.stage = Stage.IDLE
        self.detail = ""
        self.steps.clear()
        self._start = now
        self._stage_start = now
