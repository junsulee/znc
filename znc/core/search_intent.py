"""
최신 정보 필요 의도 감지 모듈.

사용자 메시지에서 웹 검색이 필요한 시간 민감 의도를 감지한다.

감지 기준:
  1. 명시적 현재성 키워드 (오늘/지금/최신...) + 질문 형태 OR '?' OR 시간민감 주제
  2. 고빈도 시간민감 주제 (날씨·뉴스·환율·날짜 등) + 질문 형태 또는 '?'
  3. 고빈도 시간민감 주제 단독 (날씨·뉴스 등 항상 최신 필요)
"""
from __future__ import annotations
import re

# ── 명시적 현재성 표현 ────────────────────────────────────────
_TEMPORAL = {
    # 한국어
    "오늘", "지금", "현재", "최신", "실시간", "방금", "지금 당장",
    "이번 주", "이번주", "이번 달", "이번달", "이번 분기",
    "올해", "이번년도", "올해 들어", "최근",
    # 영어
    "today", "right now", "currently", "latest", "real-time",
    "just now", "this week", "this month", "this year",
    "recent", "at the moment", "as of now",
}

# ── 항상 시간 민감한 고빈도 주제 ─────────────────────────────
_HIGH_SENSITIVITY = {
    # 날씨
    "날씨", "기온", "강수", "예보", "기상", "폭염", "태풍", "장마",
    "weather", "forecast", "temperature",
    # 날짜·시간 (항상 현재 기준이 필요)
    "날짜", "요일", "시각", "연도", "년도",
    "몇월", "몇일", "몇번째", "몇 번째", "며칠", "무슨 날",
    "date", "day of week", "what day", "what time", "current time",
    # 뉴스
    "뉴스", "속보", "기사", "헤드라인",
    "news", "breaking", "headline",
    # 금융
    "환율", "달러", "엔화", "유로", "원화",
    "주가", "주식", "코스피", "코스닥", "나스닥", "s&p",
    "코인", "비트코인", "이더리움", "암호화폐",
    "유가", "금값", "원자재",
    "exchange rate", "stock price", "bitcoin", "crypto", "oil price",
}

# ── 시간 민감할 수 있는 보조 주제 ────────────────────────────
_SENSITIVE_TOPICS = _HIGH_SENSITIVITY | {
    "트렌드", "유행", "인기", "랭킹", "순위", "1위",
    "신제품", "출시", "발표", "업데이트", "패치",
    "선거", "투표", "정치", "정책",
    "코로나", "감염", "확진",
    "trending", "viral", "ranking", "new release", "announcement",
}

# ── 질문 / 조회 의도 표현 ─────────────────────────────────────
_QUESTION_FORMS = {
    # 한국어 질문·요청
    "얼마야", "얼마임", "얼마에요", "얼마죠",
    "어때", "어때요", "어떻게 됐", "어떻게 돼",
    "뭐야", "뭔가요", "뭐임", "무엇", "무슨",
    "언제야", "언제죠", "언제예요",
    "어디야", "어디죠",
    "누구야", "누구죠",
    "알려줘", "알려주세요", "알고 싶", "궁금", "좀 알",
    "알 수 있", "알아", "알지", "가르쳐",
    "체크", "확인해", "확인해줘", "확인",
    "검색해", "찾아봐", "찾아줘", "조회",
    "몇이야", "몇인지",
    # 영어
    "what is", "what's", "how much", "what time", "when is",
    "where is", "who is", "tell me", "i want to know",
    "look up", "search for", "find out", "check",
}

# 한국어 질문 어미 패턴: ~야?, ~나?, ~지?, ~이야? 등
_KO_QUESTION_RE = re.compile(
    r"(이야|이에요|인가요|이지|이냐|이니|인지|야|나|냐|지|니|어|아|요|까)[?!？！]?\s*$"
)


def _is_question(text: str) -> bool:
    """질문 형태 감지: 키워드 매칭 OR '?' OR 한국어 질문 어미."""
    t = text.lower()
    if "?" in t or "？" in t:
        return True
    if any(q in t for q in _QUESTION_FORMS):
        return True
    if _KO_QUESTION_RE.search(text.strip()):
        return True
    return False


def detect_search_intent(text: str) -> tuple[bool, str]:
    """
    최신 정보 검색이 필요한 의도를 감지한다.

    Returns:
        (should_search, reason)
    """
    t = text.lower()

    has_temporal  = any(kw in t for kw in _TEMPORAL)
    has_high_sens = any(kw in t for kw in _HIGH_SENSITIVITY)
    has_topic     = any(kw in t for kw in _SENSITIVE_TOPICS)
    is_question   = _is_question(text)

    # 규칙 1: 명시적 현재성 + (질문 OR 시간민감 주제)
    if has_temporal and (is_question or has_topic):
        return True, "명시적 현재성 키워드 + 질문/주제 감지"

    # 규칙 2: 고빈도 민감 주제 + 질문
    if has_high_sens and is_question:
        return True, "시간 민감 주제 + 질문 형태 감지"

    # 규칙 3: 명시적 현재성 + 고빈도 민감 주제
    if has_temporal and has_high_sens:
        return True, "명시적 현재성 + 시간 민감 주제 감지"

    # 규칙 4: 고빈도 민감 주제 단독
    if has_high_sens:
        return True, "시간 민감 주제 단독 감지"

    return False, ""
