"""Конфигурация для Ozon."""

from pathlib import Path

# ID компании в Ozon
COMPANY_ID = "103012"

# Базовые настройки API
API_BASE_URL = "https://seller.ozon.ru"
API_REVIEW_LIST_ENDPOINT = "/api/v4/review/list"
API_REPLY_ENDPOINT = "/api/review/comment/create"

# Заголовки запроса
HEADERS = {
    "Content-Type": "application/json",
    "x-o3-company-id": COMPANY_ID,
    "x-o3-app-name": "seller-ui",
    "x-o3-language": "ru",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "Origin": "https://seller.ozon.ru",
    "Referer": "https://seller.ozon.ru/app/reviews",
}

# Пути к файлам
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "ozon"

# Настройки запросов
REQUEST_DELAY = 0.1  # секунд между запросами
REQUEST_TIMEOUT = 30  # таймаут запроса в секундах
RETRY_COUNT = 3
RETRY_DELAY = 2  # секунд между повторными попытками

# Настройки периода сбора
DEFAULT_DAYS_BACK = 30  # дней назад по умолчанию, если нет истории
USE_SMART_PERIOD = True  # искать последний отзыв с ответом в истории

# Автообновление cookies
AUTO_UPDATE_COOKIES = True  # пытаться извлекать cookies из браузера при запуске
