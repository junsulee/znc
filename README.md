# znc

개인용 AI CLI. 풀스크린 TUI, 대화 저장, 프로젝트 단위 관리, Persona 세미튜닝, 장기 메모리, 웹 검색 크롤링을 지원합니다.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ znc  | default  | ollama:llama3.1:70b  | session: my-chat                  │
├──────────────┬──────────────────────────────────────────────────────────────┤
│ znc          │                                                              │
│              │  you                                                         │
│ PROJECTS     │    Python 3.13 새 기능 뭐가 있어?                            │
│  [all]       │                                                              │
│  work        │    searching: "Python 3.13 new features"                    │
│  personal    │    crawling docs.python.org/3/whatsnew/3.13...              │
│              │                                                              │
│ SESSIONS     │  znc                                                         │
│  my-chat     │    Python 3.13 주요 변경사항:                                │
│  api-review  │    - JIT 컴파일러 실험적 도입                                │
│  draft-doc   │    - 개선된 오류 메시지                                      │
│              │    - GIL 선택적 비활성화 (PEP 703)                          │
│              │                                                              │
│              ├──────────────────────────────────────────────────────────────┤
│              │ > _                                                          │
└──────────────┴──────────────────────────────────────────────────────────────┘
 ^N new  ^S settings  ^P persona  ^M memory  Tab panel  ^Q quit
```

## 버전

| 버전 | 내용 |
|------|------|
| 0.2.0 | 풀스크린 TUI, Persona, 장기 메모리, 웹 검색 크롤링 |
| 0.1.0 | 기본 CLI, 세션 관리, 프로젝트, Ollama/OpenAI 백엔드 |

## 설치

### 의존성

- Python 3.11+
- Ollama 백엔드: [ollama.com](https://ollama.com) 설치 필요
- OpenAI 백엔드: `pip install openai` 및 API 키 필요

### 소스 설치 (개발용)

```bash
git clone git@github.com:junsulee/znc.git
cd znc
pip install -e .
pip install -e ".[openai]"   # OpenAI 백엔드 포함
```

### GitHub에서 직접 설치 (public 이후)

```bash
pip install git+https://github.com/junsulee/znc.git
```

### pipx 설치 (CLI 툴 권장)

```bash
pipx install .
pipx inject znc openai    # OpenAI 백엔드 추가
```

### PATH 설정

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### externally-managed-environment 오류 시

```bash
# 방법 1: pipx (권장)
sudo apt install pipx && pipx ensurepath
pipx install .

# 방법 2: 시스템 전역 (컨테이너/전용 VM)
pip install --break-system-packages .

# 방법 3: 임시 디렉토리 지정
mkdir -p ~/tmp
TMPDIR=~/tmp pip install --break-system-packages .
```

## 실행

```bash
znc          # 풀스크린 TUI 실행
znc --help   # CLI headless 모드 도움말
```

## TUI 키 바인딩

| 키 | 동작 |
|----|------|
| `Ctrl+N` | 새 세션 시작 |
| `Ctrl+S` | 설정 팝업 |
| `Ctrl+P` | Persona 관리 팝업 |
| `Ctrl+M` | 메모리 관리 팝업 |
| `Tab` | 사이드바 ↔ 채팅창 전환 |
| `Ctrl+Q` | 종료 (미저장 세션 자동 저장) |
| `Esc` | 팝업 닫기 / 입력창 포커스 |

## 슬래시 명령어

채팅 입력창에서 `/` 를 입력하면 자동완성이 표시됩니다.

| 명령어 | 설명 |
|--------|------|
| `/search <query>` | DuckDuckGo 검색 + 크롤링 후 AI에게 컨텍스트 전달 |
| `/remember <key>: <value>` | 장기 메모리에 저장 |
| `/forget <key>` | 장기 메모리에서 삭제 |
| `/persona <name>` | 페르소나 즉시 전환 |
| `/clear` | 현재 대화 초기화 |
| `/save <name>` | 세션 저장 |
| `/export <filepath>` | 세션 텍스트 파일로 내보내기 |
| `/memory` | 메모리 관리 팝업 열기 |
| `/settings` | 설정 팝업 열기 |

## Persona (프롬프트 세미튜닝)

모델 가중치를 변경하지 않고 **시스템 프롬프트 + Few-shot 예시**로 모델의 역할/스타일을 고정합니다.

`Ctrl+P` 팝업에서 생성하거나 `~/.znc/personas/` 에 JSON 파일로 직접 작성합니다.

```json
{
  "name": "senior-dev",
  "description": "10년차 시니어 개발자",
  "system_prompt": "너는 10년차 백엔드 개발자야. Python, Go를 주로 쓰고 코드 리뷰 시엔 보안/성능/가독성 순으로 평가해.",
  "few_shots": [
    {
      "user": "이 코드 리뷰해줘",
      "assistant": "전체 구조를 먼저 보면..."
    }
  ],
  "style": {"tone": "직설적", "lang": "ko", "format": "markdown"}
}
```

페르소나 전환:

```bash
# TUI 내
/persona senior-dev

# 또는 Ctrl+P 팝업에서 선택
```

## 장기 메모리

세션이 바뀌어도 사용자 정보를 기억합니다. 모든 대화에 자동으로 컨텍스트로 삽입됩니다.

```bash
# TUI 내 슬래시 명령어
/remember 언어: Python, Go
/remember 서버: Ubuntu 22.04, AWS
/forget 서버
/memory      # 전체 목록 팝업

# 또는 Ctrl+M 팝업
```

메모리는 두 가지 유형으로 저장됩니다.

- **manual** (파란색): `/remember` 로 직접 저장
- **auto** (노란색): AI 응답 분석으로 자동 추출

저장 위치: `~/.znc/memory/manual.json`, `~/.znc/memory/auto.json`

## 웹 검색

API 키 없이 DuckDuckGo HTML 검색 + BeautifulSoup 크롤링으로 최신 정보를 AI에게 전달합니다.

```bash
/search Python 3.13 새 기능
/search 오늘 환율
/search 최신 LLM 벤치마크 2026
```

동작 순서:

1. DuckDuckGo HTML 엔드포인트 검색 (API 없음)
2. 상위 5개 URL 본문 크롤링 (광고/nav 제거)
3. 추출 텍스트를 컨텍스트로 프롬프트에 삽입
4. AI가 해당 정보를 바탕으로 답변

## 백엔드 설정

### Ollama (기본값)

```bash
# TUI 내 Ctrl+S, 또는
znc settings --backend ollama
znc settings --model llama3.1:8b
znc settings --server-url http://localhost:11434/api/generate
```

### OpenAI / 호환 서버

```bash
znc settings --backend openai
znc settings --openai-api-key sk-...
znc settings --openai-model gpt-4o
znc settings --openai-base-url https://api.openai.com/v1   # 기본값
```

LocalAI, Ollama OpenAI 호환 엔드포인트도 `--openai-base-url` 로 연결 가능합니다.

## 프로젝트

ChatGPT의 "프로젝트" 개념과 동일합니다. 프로젝트 단위로 시스템 프롬프트와 백엔드 설정을 분리합니다.

```bash
# TUI 내 사이드바에서 p 키, 또는
znc project new work --desc "업무용" --system "넌 시니어 개발 어시스턴트야"
znc project ls
znc project info work
znc project settings work --backend openai --model gpt-4o
znc project rm work
```

## Headless CLI (서버/스크립트 환경)

TUI 없이 파이프라인에서 사용할 수 있습니다.

```bash
znc new --save my-chat
znc new --project work --save report
znc load my-chat --view          # 이전 대화 출력만
znc ls
znc ls -p work
znc export my-chat -f out.txt
znc rm my-chat
znc settings --show
```

## 데이터 디렉토리

```
~/.znc/
├── settings.json          전역 설정
├── memory/
│   ├── manual.json        수동 저장 메모리
│   └── auto.json          자동 추출 메모리
├── personas/
│   ├── default.json
│   └── senior-dev.json
├── sessions/              전역 세션
│   └── my-chat.json
└── projects/
    └── work/
        ├── project.json   프로젝트 메타데이터
        ├── settings.json  프로젝트 단위 설정 덮어쓰기
        └── sessions/
            └── report.json
```

## 코드 구조

```
znc/
├── __init__.py            (version)
├── backends/
│   ├── base.py            BaseBackend 인터페이스
│   ├── ollama.py          Ollama 스트리밍 구현
│   └── openai.py          OpenAI 호환 구현
├── core/
│   ├── config.py          설정 로드/저장, 경로 상수
│   ├── i18n.py            ko/en 메시지
│   ├── memory.py          장기 메모리 저장/조회/컨텍스트 빌드
│   ├── models.py          Message, Session, Project 데이터 모델
│   ├── persona.py         Persona + Few-shot 관리
│   ├── repository.py      프로젝트 저장소 CRUD
│   └── web_search.py      DuckDuckGo 검색 + BeautifulSoup 크롤링
├── tui/
│   ├── app.py             Textual 메인 앱
│   ├── znc.tcss           TUI 스타일시트
│   ├── screens/
│   │   ├── settings.py    설정 팝업
│   │   ├── memory.py      메모리 관리 팝업
│   │   ├── persona.py     Persona 관리 팝업
│   │   └── new_project.py 새 프로젝트 팝업
│   └── widgets/
│       ├── sidebar.py     프로젝트/세션 사이드바
│       ├── chat_view.py   메시지 뷰 (마크다운 렌더링)
│       └── input_bar.py   입력창 + /명령어 자동완성
└── cli/
    ├── main.py            진입점 (인수 없음 → TUI, 서브커맨드 → headless)
    ├── session_cmds.py    new, load, ls, rm, export
    ├── settings_cmds.py   settings
    ├── project_cmds.py    project 서브커맨드
    └── utils.py           대화 루프, 유틸
```
