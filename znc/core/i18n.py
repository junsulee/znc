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


# ── TUI 위젯 전용 UI 문자열 ──────────────────────────────────────
_UI: dict[str, dict[str, str]] = {
    "ko": {
        # 사이드바
        "projects":             "프로젝트",
        "sessions":             "세션",
        "inbox":                "inbox",
        "filter_hint":          "검색...",
        "sidebar_hint":         "n:새로  t:임시  p:프로젝트  /:검색  d:삭제  r:이름",
        # 헤더
        "new_chat":             "새 채팅",
        "temp_chat":            "[임시]",
        # 버튼
        "btn_delete":           "삭제",
        "btn_cancel":           "취소",
        "btn_save":             "저장",
        "btn_close":            "닫기",
        "btn_add":              "추가",
        "btn_clear_all":        "전체 삭제",
        "btn_use":              "사용",
        "btn_create":           "생성",
        "btn_rename":           "이름 변경",
        # 확인 팝업
        "confirm_title_del":    "삭제 확인",
        "confirm_del_session":  "'{name}' 세션을 삭제하시겠습니까?",
        "confirm_del_project":  "'{name}' 프로젝트와 모든 세션을 삭제하시겠습니까?",
        # 상태 메시지
        "deleted":              "삭제됨: {name}",
        "saved":                "저장됨: {path}",
        "stopped":              "중단됨",
        "no_messages":          "저장할 메시지가 없습니다",
        "no_session":           "세션이 없습니다",
        # 설정 탭
        "tab_ai":               "AI 백엔드",
        "tab_general":          "일반",
        "setting_lang":         "언어",
        "setting_theme":        "테마",
        "setting_engines":      "검색 엔진 (다중 선택 가능)",
        "theme_dark":           "다크 모드",
        "theme_light":          "라이트 모드",
        "setting_backend":      "백엔드",
        "setting_model_ollama": "모델  (Ollama)",
        "setting_server_url":   "서버 URL  (Ollama)",
        "setting_oai_key":      "OpenAI API 키",
        "setting_oai_model":    "OpenAI 모델",
        "setting_oai_base":     "OpenAI 기본 URL",
        "setting_ai_name":      "AI 표시 이름",
        "setting_serper_key":   "Google Serper API 키  (무료 2500회/월)",
        # MessageSaver
        "save_msg_title":       "메시지 저장",
        "select_message":       "저장할 메시지를 선택하세요:",
        "detected_label":       "감지됨: {display}  →  .{ext}",
        "format_label":         "포맷:",
        "filename_label":       "파일명:",
        "no_msg_selected":      "메시지를 먼저 선택해주세요.",
        # 메모리
        "memory_title":         "메모리",
        "memory_add_hint":      "key: value 형식으로 입력",
        "memory_stored":        "저장된 메모리  (m=수동:파란색  a=자동:노란색)",
        # Persona
        "persona_title":        "페르소나",
        "persona_name":         "이름",
        "persona_desc":         "설명",
        "persona_system":       "시스템 프롬프트",
        # 프로젝트 생성
        "new_project_title":    "새 프로젝트",
        "project_name":         "이름",
        "project_desc":         "설명",
        "project_system":       "기본 시스템 프롬프트 (선택)",
        # 이름 변경
        "rename_title":         "이름 변경",
        "rename_current":       "현재: {name}",
        "rename_new":           "새 이름",
        # About
        "about_features":       "기능",
        "about_footer":         "F1 도움말   ^G 정보   github.com/junsulee/znc",
        # 하단 바 항목 (Korean: 설명(^Key) 형식)
        "kbar_save":            "저장(^W)",
        "kbar_new":             "새채팅(^N)",
        "kbar_temp":            "임시(^T)",
        "kbar_panel":           "패널(^B)",
        "kbar_settings":        "설정(^S)",
        "kbar_persona":         "페르소나(^P)",
        "kbar_memory":          "메모리(^E)",
        "kbar_log":             "로그(^L)",
        "kbar_about":           "정보(^G)",
        "kbar_help":            "도움(F1)",
        "kbar_focus":           "포커스(Tab)",
        "kbar_quit":            "종료(^Q)",
        "kbar_sb_new":          "n:새로",
        "kbar_sb_temp":         "t:임시",
        "kbar_sb_proj":         "p:프로젝트",
        "kbar_sb_search":       "/:검색",
        "kbar_sb_del":          "d:삭제",
        "kbar_sb_rename":       "r:이름변경",
        "kbar_sb_esc":          "Esc:닫기",
        "kbar_sb_prefix":       "사이드바 >",
    },
    "en": {
        # sidebar
        "projects":             "PROJECTS",
        "sessions":             "SESSIONS",
        "inbox":                "inbox",
        "filter_hint":          "filter...",
        "sidebar_hint":         "n:new  t:temp  p:project  /:search  d:del  r:rename",
        # header
        "new_chat":             "new chat",
        "temp_chat":            "[temp]",
        # buttons
        "btn_delete":           "Delete",
        "btn_cancel":           "Cancel",
        "btn_save":             "Save",
        "btn_close":            "Close",
        "btn_add":              "Add",
        "btn_clear_all":        "Clear All",
        "btn_use":              "Use",
        "btn_create":           "Create",
        "btn_rename":           "Rename",
        # confirm
        "confirm_title_del":    "Confirm Delete",
        "confirm_del_session":  "Delete session '{name}'?",
        "confirm_del_project":  "Delete project '{name}' and all its sessions?",
        # status
        "deleted":              "deleted: {name}",
        "saved":                "saved: {path}",
        "stopped":              "stopped",
        "no_messages":          "no messages to save",
        "no_session":           "no active session",
        # settings tabs
        "tab_ai":               "AI Backend",
        "tab_general":          "General",
        "setting_lang":         "Language",
        "setting_theme":        "Theme",
        "setting_engines":      "Search Engines (multi-select)",
        "theme_dark":           "Dark Mode",
        "theme_light":          "Light Mode",
        "setting_backend":      "Backend",
        "setting_model_ollama": "Model  (Ollama)",
        "setting_server_url":   "Server URL  (Ollama)",
        "setting_oai_key":      "OpenAI API Key",
        "setting_oai_model":    "OpenAI Model",
        "setting_oai_base":     "OpenAI Base URL",
        "setting_ai_name":      "AI Display Name",
        "setting_serper_key":   "Google Serper API Key  (free 2500/month)",
        # MessageSaver
        "save_msg_title":       "Save Message",
        "select_message":       "Select a message to save:",
        "detected_label":       "Detected: {display}  →  .{ext}",
        "format_label":         "Format:",
        "filename_label":       "Filename:",
        "no_msg_selected":      "Please select a message first.",
        # memory
        "memory_title":         "Memory",
        "memory_add_hint":      "key: value",
        "memory_stored":        "Stored memories  (m=manual:blue  a=auto:yellow)",
        # Persona
        "persona_title":        "Persona",
        "persona_name":         "Name",
        "persona_desc":         "Description",
        "persona_system":       "System Prompt",
        # new project
        "new_project_title":    "New Project",
        "project_name":         "Name",
        "project_desc":         "Description",
        "project_system":       "Default system prompt (optional)",
        # rename
        "rename_title":         "Rename",
        "rename_current":       "Current: {name}",
        "rename_new":           "New name",
        # About
        "about_features":       "FEATURES",
        "about_footer":         "F1 help   ^G about   github.com/junsulee/znc",
        # keybind bar items (English: ^Key Desc format)
        "kbar_save":            "^W Save",
        "kbar_new":             "^N New",
        "kbar_temp":            "^T Temp",
        "kbar_panel":           "^B Panel",
        "kbar_settings":        "^S Settings",
        "kbar_persona":         "^P Persona",
        "kbar_memory":          "^E Memory",
        "kbar_log":             "^L Log",
        "kbar_about":           "^G About",
        "kbar_help":            "F1 Help",
        "kbar_focus":           "Tab Focus",
        "kbar_quit":            "^Q Quit",
        "kbar_sb_new":          "n:new",
        "kbar_sb_temp":         "t:temp",
        "kbar_sb_proj":         "p:project",
        "kbar_sb_search":       "/:search",
        "kbar_sb_del":          "d:del",
        "kbar_sb_rename":       "r:rename",
        "kbar_sb_esc":          "Esc:close",
        "kbar_sb_prefix":       "sidebar >",
    },
}


def ui(lang: str, key: str, **kwargs) -> str:
    """TUI 위젯용 UI 문자열 반환."""
    d = _UI.get(lang, _UI["en"])
    template = d.get(key, _UI["en"].get(key, key))
    return template.format(**kwargs) if kwargs else template
