"""Конфигурация LLM для генерации ответов на нестандартные 1-4★ отзывы (GigaChat).

Раньше использовался Gemini API, но заменён на GigaChat: у GigaChat-2 (Lite)
250 млн бесплатных токенов на 12 месяцев (у Gemini — 20 запросов/день на
флагманской модели), плюс GigaChat не тратит токены на скрытые "размышления"
и явно лучше звучит на русском — естественный язык для этой задачи.
Проверено эмпирически 2026-09-25.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS", "")
GIGACHAT_MODEL = "GigaChat-2"
GIGACHAT_TIMEOUT = 20  # секунд на запрос

# Сертификат НУЦ Минцифры — нужен для проверки TLS при обращении к api.gigachat.
# Публичный корневой сертификат, не секрет, лежит в репозитории.
# Скачан с https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt
GIGACHAT_CA_BUNDLE_FILE = str(PROJECT_ROOT / "russian_trusted_root_ca.pem")
