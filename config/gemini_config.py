"""Конфигурация Gemini API (генерация ответов на нестандартные 1-4★ отзывы)."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# gemini-2.5-flash и gemini-2.5-flash-lite больше не доступны новым пользователям
# (Google перевёл на линейку 3.x), проверено эмпирически 2026-09-25.
# gemini-3.8-flash (флагман) на Free Tier ограничена 20 запросами/день — этого не
# хватает для регулярного прогона по отзывам. gemini-3.5-flash-lite — та же Free Tier,
# но лимит заметно выше (Google не публикует точные RPD в доках, только в личном
# кабинете aistudio.google.com/rate-limit — можно уточнить точное число там).
# Задача простая (короткий вежливый ответ 2-4 предложения), lite для неё достаточно.
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_TIMEOUT = 20  # секунд на запрос
# "Размышления" (thinking) едят часть бюджета до финального текста — thinking_budget=0
# в generation_config это не отменяет (проверено эмпирически 2026-09-25: ~200-550
# "thought"-токенов на короткий промпт даже у flash). Берём с запасом, чтобы не
# обрезать финальный ответ (status="incomplete").
GEMINI_MAX_OUTPUT_TOKENS = 2048
