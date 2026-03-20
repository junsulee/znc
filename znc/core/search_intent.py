"""
최신 정보 필요 의도 감지 모듈.

사용자 메시지에서 웹 검색이 필요한 시간 민감 의도를 감지한다.

감지 기준 (AND/OR 조합):
  1. 명시적 현재성 키워드 (오늘, 지금, 최신, today, now, ...)
  2. 시간 민감 주제 (날씨, 뉴스, 환율, 주가, ...)
  3. 질문 형태 (얼마야, 어때, 알려줘, what is, ...)

규칙:
  - 명시적 현재성 키워드 + (민감 주제 OR 질문 형태)  → 검색
  - 고빈도 시간민감 주제 (날씨·뉴스·환율) + 질문 형태 → 검색
  - 단독 현재성 키워드 + 고빈도 민감 주제             → 검색
"""
from __future__ import annotations

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
    # 한국어 질문/요청 어미
    "얼마야", "얼마임", "얼마에요", "얼마죠",
    "어때", "어때요", "어때요", "어떻게 됐", "어떻게 돼",
    "뭐야", "뭔가요", "뭐임", "무엇", "무슨",
    "언제야", "언제죠", "언제예요",
    "어디야", "어디죠",
    "누구야", "누구죠",
    "알려줘", "알려주세요", "알고 싶", "궁금", "좀 알",
    "검색해", "찾아봐", "찾아줘", "조회",
    # 영어
    "what is", "what's", "how much", "what time", "when is",
    "where is", "who is", "tell me", "i want to know",
    "look up", "search for", "find out",
}


def detect_search_intent(text: str) -> tuple[bool, str]:
    """
    최신 정보 검색이 필요한 의도를 감지한다.

    Returns:
        (should_search, reason)  — reason 은 로그/UI 표시용 설명 문자열
    """
    t = text.lower()

    has_temporal   = any(kw in t for kw in _TEMPORAL)
    has_high_sens  = any(kw in t for kw in _HIGH_SENSITIVITY)
    has_topic      = any(kw in t for kw in _SENSITIVE_TOPICS)
    has_question   = any(kw in t for kw in _QUESTION_FORMS)

    # 규칙 1: 명시적 현재성 + (민감 주제 OR 질문 형태)
    if has_temporal and (has_topic or has_question):
        return True, "명시적 현재성 키워드 + 질문/주제 감지"

    # 규칙 2: 고빈도 민감 주제 (날씨·뉴스·환율 등) + 질문 형태
    if has_high_sens and has_question:
        return True, "시간 민감 주제 + 질문 형태 감지"

    # 규칙 3: 명시적 현재성 + 고빈도 민감 주제 (질문 아니어도 충분)
    if has_temporal and has_high_sens:
        return True, "명시적 현재성 + 시간 민감 주제 감지"

    # 규칙 4: 고빈도 민감 주제 단독으로도 검색 트리거
    #   (날씨·뉴스·환율·주가·코인은 거의 항상 최신 정보가 필요)
    if has_high_sens:
        return True, "시간 민감 주제 단독 감지"

    return False, ""
