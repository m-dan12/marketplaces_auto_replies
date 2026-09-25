"""Генерация адресных ответов на нестандартные 1-4★ отзывы через GigaChat API.

Используется только когда `shared.review_heuristics.detect_review_issue` нашла
в тексте отзыва конкретную, узнаваемую проблему (размер, ткань, брак, цвет,
не тот товар) — для остальных 1-4★ отзывов остаётся обычный фиксированный
шаблон (см. `config/templates.py`). Graceful degradation: любая ошибка API
(нет ключа, таймаут, лимит) возвращает None, вызывающая сторона в этом
случае тоже падает обратно на фиксированный шаблон.
"""

from functools import lru_cache
from typing import Optional

from gigachat import GigaChat

from config.llm_config import GIGACHAT_CA_BUNDLE_FILE, GIGACHAT_CREDENTIALS, GIGACHAT_MODEL, GIGACHAT_TIMEOUT
from shared.logger import logger
from shared.review_heuristics import ISSUE_LABELS, MAX_REPLY_LEN

PROMPT_TEMPLATE = """Ты — служба поддержки бренда постельного белья {brand_name} на маркетплейсе.
Покупатель оставил отзыв с оценкой {rating}★. Судя по тексту, основная проблема: {issue_label}.

Текст отзыва: "{review_text}"

Напиши короткий ответ от лица бренда (2-4 предложения, до 400 символов):
- Поблагодари за отзыв
- Извинись именно за названную проблему, без общих фраз про "не оправдали ожидания"
- Предложи оформить возврат или обмен через маркетплейс
- Не упоминай другие товары и рекомендации
- Один подходящий эмодзи, не более
- Пиши только сам текст ответа, без пояснений и кавычек вокруг него"""


def generate_issue_reply(rating: int, review_text: str, issue_category: str, brand_name: str) -> Optional[str]:
    """
    Генерирует адресный ответ на 1-4★ отзыв с конкретной проблемой.

    Args:
        rating: Оценка отзыва (1-4)
        review_text: Текст отзыва
        issue_category: Ключ категории из `shared.review_heuristics.ISSUE_LABELS`
        brand_name: Подпись бренда, например «Сказка» или «Анна Мария»

    Returns:
        Готовый текст ответа, или None при любой ошибке (см. модульный docstring)
    """
    issue_label = ISSUE_LABELS.get(issue_category)
    if not issue_label:
        return None

    prompt = PROMPT_TEMPLATE.format(
        brand_name=brand_name,
        rating=rating,
        issue_label=issue_label,
        review_text=review_text or "",
    )

    reply = _call_gigachat_api(prompt)
    if not reply:
        return None

    return reply.strip()[:MAX_REPLY_LEN]


@lru_cache(maxsize=1)
def _get_client() -> Optional[GigaChat]:
    """Ленивая инициализация клиента GigaChat SDK (один раз за процесс)."""
    if not GIGACHAT_CREDENTIALS:
        return None
    return GigaChat(
        credentials=GIGACHAT_CREDENTIALS,
        model=GIGACHAT_MODEL,
        ca_bundle_file=GIGACHAT_CA_BUNDLE_FILE,
        timeout=GIGACHAT_TIMEOUT,
    )


def _call_gigachat_api(prompt: str) -> Optional[str]:
    """Низкоуровневый вызов GigaChat через SDK. None при любой ошибке."""
    client = _get_client()
    if not client:
        logger.warning("⚠️  GIGACHAT_CREDENTIALS не задан, пропускаем генерацию ответа")
        return None

    try:
        response = client.chat(prompt)
        return response.choices[0].message.content
    except Exception as e:
        logger.warning(f"⚠️  GigaChat API ошибка: {e}")
        return None
