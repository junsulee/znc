"""
다국어 메시지 관리
"""
from __future__ import annotations

MESSAGES: dict[str, dict[str, str]] = {
    "ko": {
        "help_header": """\
╭─────────────────────────────────────────────────────────────╮
│  znc — 개인용 AI CLI                                         │
│─────────────────────────────────────────────────────────────│
│  대화 저장 · 프로젝트 단위 관리 · 다중 백엔드 지원           │
╰─────────────────────────────────────────────────────────────╯

Commands:
  new       새 대화 세션 시작
  load      기존 세션 불러오기 (이어서 대화)
  ls        저장된 세션 리스트
  rm        세션 삭제
  export    세션 내보내기 (plain text)
  project   프로젝트 관리 (new/ls/rm/use)
  settings  전역 설정 관리

Examples:
  znc new --save my-session
  znc new --project work --save report-draft
  znc load my-session
  znc export my-session -f out.txt
  znc project new myproject --desc "업무 관련 AI"
  znc settings --backend openai --openai-api-key sk-...
""",
        "welcome": "znc — 개인용 AI CLI",
        "desc": "대화 저장 · 프로젝트 단위 관리 · 다중 백엔드 지원",
        "exit_tip": "💡 /exit 입력 또는 Ctrl+C 로 종료",
        "new_help": "새 대화 세션 시작",
        "load_help": "기존 세션 불러오기 (이어서 대화)",
        "ls_help": "저장된 세션 리스트 보기",
        "rm_help": "세션 삭제",
        "settings_help": "전역 설정 관리",
        "export_help": "세션 내보내기 (plain text)",
        "project_help": "프로젝트 관리",
        "session_loaded": "✅ 세션 불러옴: {path}",
        "session_saved": "✅ 세션 저장됨: {path}",
        "session_deleted": "🗑️  세션 삭제 완료: {path}",
        "session_not_found": "❌ 세션이 존재하지 않습니다: {name}",
        "session_list_header": "🗂️  저장된 세션 목록:",
        "no_sessions": "ℹ️  저장된 세션이 없습니다.",
        "settings_updated": "✅ 설정이 업데이트되었습니다.",
        "lang_set": "✅ 언어 설정: {lang}",
        "ai_name_set": "✅ AI 이름 설정: {name}",
        "export_done": "✅ {file} 로 내보내기 완료",
        "export_error": "❌ 세션이 존재하지 않습니다: {name}",
        "project_created": "✅ 프로젝트 생성됨: {name}",
        "project_deleted": "🗑️  프로젝트 삭제 완료: {name}",
        "project_not_found": "❌ 프로젝트가 존재하지 않습니다: {name}",
        "project_list_header": "📁  프로젝트 목록:",
        "no_projects": "ℹ️  프로젝트가 없습니다.",
        "project_using": "✅ 현재 프로젝트: {name}",
        "backend_set": "✅ 백엔드 설정: {backend}",
        "model_set": "✅ 모델 설정: {model}",
        "server_url_set": "✅ 서버 URL 설정: {url}",
        "openai_key_set": "✅ OpenAI API 키 설정 완료",
        "openai_model_set": "✅ OpenAI 모델 설정: {model}",
        "session_continue": "이어서 대화합니다. 이전 메시지 수: {count}",
    },
    "en": {
        "help_header": """\
╭─────────────────────────────────────────────────────────────╮
│  znc — Personal AI CLI                                       │
│─────────────────────────────────────────────────────────────│
│  Chat history · Project management · Multi-backend support  │
╰─────────────────────────────────────────────────────────────╯

Commands:
  new       Start a new chat session
  load      Load existing session (continue conversation)
  ls        List saved sessions
  rm        Delete session
  export    Export session (plain text)
  project   Project management (new/ls/rm)
  settings  Manage global settings

Examples:
  znc new --save my-session
  znc new --project work --save report-draft
  znc load my-session
  znc export my-session -f out.txt
  znc project new myproject --desc "Work-related AI"
  znc settings --backend openai --openai-api-key sk-...
""",
        "welcome": "znc — Personal AI CLI",
        "desc": "Chat history · Project management · Multi-backend support",
        "exit_tip": "💡 Type /exit or Ctrl+C to quit",
        "new_help": "Start a new chat session",
        "load_help": "Load existing session (continue conversation)",
        "ls_help": "List saved sessions",
        "rm_help": "Delete session",
        "settings_help": "Manage global settings",
        "export_help": "Export session (plain text)",
        "project_help": "Project management",
        "session_loaded": "✅ Session loaded: {path}",
        "session_saved": "✅ Session saved: {path}",
        "session_deleted": "🗑️  Session deleted: {path}",
        "session_not_found": "❌ Session not found: {name}",
        "session_list_header": "🗂️  Saved sessions:",
        "no_sessions": "ℹ️  No saved sessions.",
        "settings_updated": "✅ Settings updated.",
        "lang_set": "✅ Language set: {lang}",
        "ai_name_set": "✅ AI name set: {name}",
        "export_done": "✅ Exported to {file}",
        "export_error": "❌ Session not found: {name}",
        "project_created": "✅ Project created: {name}",
        "project_deleted": "🗑️  Project deleted: {name}",
        "project_not_found": "❌ Project not found: {name}",
        "project_list_header": "📁  Projects:",
        "no_projects": "ℹ️  No projects found.",
        "project_using": "✅ Current project: {name}",
        "backend_set": "✅ Backend set: {backend}",
        "model_set": "✅ Model set: {model}",
        "server_url_set": "✅ Server URL set: {url}",
        "openai_key_set": "✅ OpenAI API key updated",
        "openai_model_set": "✅ OpenAI model set: {model}",
        "session_continue": "Continuing conversation. Previous messages: {count}",
    },
}


def get_message(locale: str, key: str, **kwargs) -> str:
    lang_msgs = MESSAGES.get(locale, MESSAGES["en"])
    template = lang_msgs.get(key, MESSAGES["en"].get(key, key))
    return template.format(**kwargs)
