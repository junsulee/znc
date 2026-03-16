# znc — 개인용 AI CLI

대화 저장 · 프로젝트 단위 관리 · 다중 백엔드 지원

## 설치

### 방법 1 — GitHub에서 직접 설치 (권장)

```bash
pip install git+https://github.com/junsulee/znc.git
```

OpenAI 백엔드도 함께 설치하려면:

```bash
pip install "znc[openai] @ git+https://github.com/junsulee/znc.git"
```

### 방법 2 — 소스 클론 후 설치 (개발용)

```bash
git clone https://github.com/junsulee/znc.git
cd znc
pip install -e .          # 기본 (Ollama 백엔드)
pip install -e ".[openai]" # OpenAI 백엔드 포함
```

### PATH 설정

설치 후 `znc` 명령이 없다는 오류가 나오면 pip의 스크립트 경로를 PATH에 추가합니다.

```bash
# ~/.bashrc 또는 ~/.zshrc 에 추가
export PATH="$HOME/.local/bin:$PATH"
source ~/.bashrc
```

### 요구 사항

- Python 3.11 이상
- Ollama 백엔드: [Ollama](https://ollama.com) 설치 및 모델 다운로드 필요
- OpenAI 백엔드: `pip install openai` 및 API 키 필요

## 사용법

### 새 대화 시작

```bash
znc new                        # 대화 후 자동 저장
znc new --save my-chat         # 이름 지정 저장
znc new --project work         # 프로젝트에 연결
znc new --system "넌 시니어 개발자야"   # 세션 단위 시스템 프롬프트
```

대화 중 `/exit` 또는 `Ctrl+C` 로 종료합니다.

### 세션 불러오기 (이어서 대화)

```bash
znc load my-chat               # 이어서 대화
znc load my-chat --view        # 이전 대화 내용만 출력
znc load my-chat -p work       # 프로젝트 안의 세션 불러오기
```

### 세션 목록/삭제/내보내기

```bash
znc ls                         # 전체 세션 목록
znc ls -p work                 # 프로젝트별 목록
znc rm my-chat                 # 세션 삭제
znc export my-chat -f out.txt  # plain text 내보내기
```

### 프로젝트 관리

ChatGPT의 "프로젝트" 개념과 유사합니다. 프로젝트 단위로 시스템 프롬프트와 설정을 분리할 수 있습니다.

```bash
znc project new work --desc "업무용" --system "넌 시니어 개발 어시스턴트야"
znc project ls
znc project info work
znc project rm work

# 프로젝트 단위 백엔드/모델 덮어쓰기
znc project settings work --backend openai --model gpt-4o
znc project settings work --system "새 시스템 프롬프트"
```

### 설정

```bash
znc settings --show                           # 현재 설정 출력

# Ollama 백엔드
znc settings --backend ollama
znc settings --model llama3.1:70b-instruct-q3_K_M
znc settings --server-url http://localhost:11434/api/generate

# OpenAI 백엔드
znc settings --backend openai
znc settings --openai-api-key sk-...
znc settings --openai-model gpt-4o
znc settings --openai-base-url https://api.openai.com/v1

# 기타
znc settings --lang ko          # 언어: ko / en
znc settings --ai-name "내비서"  # AI 표시 이름
```

## 디렉토리 구조

```
~/.znc/
├── settings.json          # 전역 설정
├── sessions/              # 전역 세션 저장
│   └── my-chat.json
└── projects/
    └── work/
        ├── project.json   # 프로젝트 메타데이터
        ├── settings.json  # 프로젝트 단위 설정 덮어쓰기
        └── sessions/      # 프로젝트 세션 저장
            └── ...
```

## 지원 백엔드

| 백엔드  | 설명                                   |
|---------|----------------------------------------|
| ollama  | 로컬 Ollama 서버 (기본값)              |
| openai  | OpenAI API / Azure / LocalAI 호환 서버 |

## 코드 구조

```
znc/
├── __init__.py
├── backends/
│   ├── base.py       # 백엔드 추상 기본 클래스
│   ├── ollama.py     # Ollama 구현
│   └── openai.py     # OpenAI 호환 구현
├── core/
│   ├── config.py     # 설정 로드/저장, 경로 상수
│   ├── i18n.py       # 다국어 메시지 (ko/en)
│   ├── models.py     # Message, Session, Project 데이터 모델
│   └── repository.py # 프로젝트 저장소
└── cli/
    ├── main.py          # CLI 진입점 (click group)
    ├── session_cmds.py  # new, load, ls, rm, export
    ├── settings_cmds.py # settings
    ├── project_cmds.py  # project new/ls/rm/info/settings
    └── utils.py         # safe_input, run_chat_loop 등
```
