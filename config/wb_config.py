"""Конфигурация для Wildberries."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

FEEDBACKS_BASE_URL = "https://feedbacks-api.wildberries.ru"
API_FEEDBACKS_LIST_ENDPOINT = "/api/v1/feedbacks"
API_FEEDBACKS_ANSWER_ENDPOINT = "/api/v1/feedbacks/answer"

FEEDBACKS_DELAY = 0.34  # секунд между запросами к Feedbacks API

REQUEST_TIMEOUT = 30
RATE_LIMIT_RETRIES = 5
RATE_LIMIT_EXTRA_DELAY = 0.75

# Настройки сбора отзывов
FEEDBACK_DAYS_BACK = 30
FEEDBACK_TAKE = 1000
MAX_FEEDBACK_TOTAL = 1000

# Настройки отправки ответов
MAX_REPLIES_PER_RUN = 100
MAX_REPLY_LEN = 5000
