"""Конфигурация Gemini API (генерация ответов на нестандартные 1-4★ отзывы)."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# gemini-2.5-flash больше не доступна новым пользователям (Google перевёл на 3.8),
# проверено эмпирически 2026-09-25.
GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_TIMEOUT = 20  # секунд на запрос
# gemini-3.8-flash тратит часть бюджета на "размышления" (thinking) до того, как
# выдать финальный текст — thinking_budget=0 в generation_config это не отменяет
# (проверено эмпирически 2026-09-25: ~200-550 "thought"-токенов на короткий промпт).
# Берём с запасом, чтобы не обрезать финальный ответ (status="incomplete").
GEMINI_MAX_OUTPUT_TOKENS = 2048
