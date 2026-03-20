"""
한글 IME ghost 문자 처리 유틸리티.

일부 SSH 클라이언트(iOS Termius 등)는 한글 조합 중간 상태를 모두 전송한다.

  안녕  →  ㅇ아안ㄴ녀녕
  너는  →  ㄴ너넌너느는
  누구니 →  ㄴ누눅누구군구니

세 가지 ghost 패턴을 제거:

  Case 1  compat 자모 → 해당 자모를 초성으로 가진 음절
          ㄴ → 너

  Case 2  종성 없는 음절 → 같은 초+중성 + 종성이 추가된 음절
          너(ㄴ+ㅓ) → 넌(ㄴ+ㅓ+ㄴ)

  Case 3  종성 있는 음절 → 같은 초+중성 + 종성 없는 음절
          (IME가 종성을 다음 음절 초성으로 이동)
          넌(ㄴ+ㅓ+ㄴ) → 너  단, 다음 문자의 초성이 넌의 종성과 일치할 때만 제거
          (오탐 방지: "않아"처럼 복잡 종성이거나 다음 초성이 다르면 유지)
"""
from __future__ import annotations

import unicodedata

_CHO  = ["ㄱ","ㄲ","ㄴ","ㄷ","ㄸ","ㄹ","ㅁ","ㅂ","ㅃ","ㅅ","ㅆ","ㅇ","ㅈ","ㅉ","ㅊ","ㅋ","ㅌ","ㅍ","ㅎ"]
_JONG = ["","ㄱ","ㄲ","ㄳ","ㄴ","ㄵ","ㄶ","ㄷ","ㄹ","ㄺ","ㄻ","ㄼ","ㄽ","ㄾ","ㄿ","ㅀ","ㅁ","ㅂ","ㅄ","ㅅ","ㅆ","ㅇ","ㅈ","ㅊ","ㅋ","ㅌ","ㅍ","ㅎ"]
_CHO_IDX = {c: i for i, c in enumerate(_CHO)}

_SYL_S, _SYL_E = 0xAC00, 0xD7A3
_JAM_S, _JAM_E = 0x3131, 0x314E


def _syl(ch: str):
    """(초성idx, 중성idx, 종성idx). 음절 아니면 None."""
    cp = ord(ch)
    if not (_SYL_S <= cp <= _SYL_E):
        return None
    o = cp - _SYL_S
    return o // (21 * 28), (o // 28) % 21, o % 28


def _is_jamo(ch: str) -> bool:
    return _JAM_S <= ord(ch) <= _JAM_E


def _is_ghost(a: str, b: str, after: str | None) -> bool:
    # Case 1: compat 자모 → 음절 (해당 자모가 초성)
    if _is_jamo(a):
        bp = _syl(b)
        return bool(bp) and _CHO_IDX.get(a, -1) == bp[0]

    ap, bp = _syl(a), _syl(b)
    if not (ap and bp):
        return False

    # 초성·중성이 같아야 함
    if ap[0] != bp[0] or ap[1] != bp[1]:
        return False

    # Case 2: 종성 없음 → 종성 있음  (너→넌)
    if ap[2] == 0 and bp[2] != 0:
        return True

    # Case 3: 종성 있음 → 종성 없음  (넌→너)
    # 단순 종성만, 다음 문자 초성과 일치할 때만 제거
    if ap[2] != 0 and bp[2] == 0:
        jong = _JONG[ap[2]]
        if not jong or len(jong) > 1:   # 복잡 종성(ㄳ,ㄶ 등) 제외
            return False
        cho_idx = _CHO_IDX.get(jong, -1)
        if cho_idx == -1 or after is None:
            return False
        after_p = _syl(after)
        if after_p:
            return after_p[0] == cho_idx
        if _is_jamo(after):
            return after == jong
        return False

    return False


def remove_composition_ghosts(text: str) -> str:
    """
    IME 조합 중간 상태(ghost) 문자 제거.

    ㅇ아안ㄴ녀녕      → 안녕
    ㄴ너넌너느는      → 너는
    ㄴ누눅누구군구니  → 누구니
    """
    if len(text) < 2:
        return text
    chars = list(text)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(chars) - 1:
            after = chars[i + 2] if i + 2 < len(chars) else None
            if _is_ghost(chars[i], chars[i + 1], after):
                chars.pop(i)
                changed = True
            else:
                i += 1
    return "".join(chars)


def sanitize_korean(text: str) -> str:
    """NFC 정규화 + ghost 제거."""
    return remove_composition_ghosts(unicodedata.normalize("NFC", text))
