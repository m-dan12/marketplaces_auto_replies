"""Сборщик отзывов Ozon."""

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config.ozon_config import (
    API_REVIEW_LIST_ENDPOINT,
    COMPANY_ID,
    DATA_DIR,
    DEFAULT_DAYS_BACK,
    REQUEST_DELAY,
    USE_SMART_PERIOD,
)
from marketplaces.ozon.api_client import OzonAPIClient
from shared.logger import logger
from shared.storage import JSONStorage


class OzonReviewCollector:
    """Сборщик неотвеченных отзывов Ozon."""

    def __init__(self, cookies_file, company_id: str, data_dir):
        """
        Инициализация сборщика.

        Args:
            cookies_file: Путь к файлу с cookies
            company_id: ID компании в Ozon
            data_dir: Директория для сохранения данных
        """
        self.api_client = OzonAPIClient(cookies_file, company_id)
        self.company_id = company_id
        self.storage = JSONStorage(data_dir)
        self.data_dir = data_dir

    def determine_date_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Определение периода сбора отзывов.

        Returns:
            Кортеж (date_from, date_to)
        """
        if not USE_SMART_PERIOD:
            # Используем фиксированный период
            date_from = datetime.now() - timedelta(days=DEFAULT_DAYS_BACK)
            date_to = datetime.now()
            logger.info(f"📅 Период: последние {DEFAULT_DAYS_BACK} дней")
            return date_from, date_to

        # Умное определение периода через анализ истории
        logger.info("🔎 Анализируем предыдущие выгрузки для определения периода...")

        from marketplaces.ozon.history_analyzer import HistoryAnalyzer
        analyzer = HistoryAnalyzer(self.data_dir)
        last_answered = analyzer.find_last_answered_review()

        if last_answered:
            # Нашли последний отзыв с ответом
            published_at = last_answered.get("published_at")
            rating = last_answered.get("rating")
            text_preview = last_answered.get("text", "")[:50]

            logger.info(f"✅ Найден последний отзыв с ответом:")
            logger.info(f"   Дата: {published_at}")
            logger.info(f"   Рейтинг: {rating}⭐")
            if text_preview:
                logger.info(f"   Текст: {text_preview}...")

            # Парсим дату
            try:
                date_from = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                date_to = datetime.now()
                logger.info(
                    f"📅 Соберём отзывы с {date_from.strftime('%Y-%m-%d')} по настоящее время"
                )
                return date_from, date_to
            except Exception:
                logger.warning(
                    f"⚠️  Не удалось распарсить дату, используем период по умолчанию"
                )

        # Если не нашли - используем период по умолчанию
        date_from = datetime.now() - timedelta(days=DEFAULT_DAYS_BACK)
        date_to = datetime.now()
        logger.info(
            f"📅 Предыдущих выгрузок нет, используем последние {DEFAULT_DAYS_BACK} дней"
        )

        return date_from, date_to

    def collect_reviews(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Сбор неотвеченных отзывов с инкрементальным сохранением.

        Args:
            date_from: Начальная дата для фильтрации (включительно)
            date_to: Конечная дата для фильтрации (включительно)

        Returns:
            Список неотвеченных отзывов
        """
        all_reviews: List[Dict[str, Any]] = []
        page = 1
        last_review: Optional[Dict[str, Any]] = None

        # Информация о периоде
        period_info = "все отзывы"
        if date_from and date_to:
            period_info = (
                f"с {date_from.strftime('%Y-%m-%d')} по {date_to.strftime('%Y-%m-%d')}"
            )
        elif date_from:
            period_info = f"с {date_from.strftime('%Y-%m-%d')}"
        elif date_to:
            period_info = f"до {date_to.strftime('%Y-%m-%d')}"

        logger.info(f"🔍 Собираем отзывы (период: {period_info})...\n")

        while True:
            # Формирование payload
            payload: Dict[str, Any] = {
                "company_id": self.company_id,
                "company_type": "seller",
                "filter": {
                    "published_at": self._build_date_filter(date_from, date_to),
                    "interaction_status": ["ALL"],
                    "awaiting_reply": True,  # Фильтр "Ждут ответа" на стороне сервера
                },
            }

            if last_review:
                payload["last_review"] = last_review

            # Запрос к API
            logger.info(f"📄 Страница {page}...")

            timer_start = time.time()
            response = self.api_client.make_request(API_REVIEW_LIST_ENDPOINT, payload)
            api_time = time.time() - timer_start

            # Извлечение данных
            result = response.get("result", [])
            has_next = response.get("hasNext", False)

            all_reviews.extend(result)

            logger.info(
                f"   Получено: {len(result)} отзывов "
                f"(всего: {len(all_reviews)}) "
                f"⏱️ {api_time:.2f}s"
            )

            # Инкрементальное сохранение каждые 5 страниц
            if page % 5 == 0 and all_reviews:
                timer_start = time.time()
                logger.info(
                    f"💾 Промежуточное сохранение {len(all_reviews)} отзывов..."
                )
                self.storage.save_reviews(all_reviews, temp=True, page=page)
                save_time = time.time() - timer_start
                logger.info(f"   ⏱️ {save_time:.2f}s")

            # Проверка окончания пагинации
            if not has_next:
                logger.info(f"\n✅ Пагинация завершена. Всего страниц: {page}")
                break

            # Подготовка к следующей странице
            last_review = response.get("last_review")
            if not last_review:
                logger.warning(
                    "\n⚠️  hasNext=true, но last_review отсутствует. Останавливаем."
                )
                break

            page += 1

            # Задержка между запросами
            time.sleep(REQUEST_DELAY)

        # Отзывы уже отфильтрованы сервером (awaiting_reply: true)
        logger.info(f"\n✅ Собрано отзывов, ожидающих ответа: {len(all_reviews)}")

        return all_reviews

    def _build_date_filter(
        self, date_from: Optional[datetime], date_to: Optional[datetime]
    ) -> Dict[str, str]:
        """
        Построение фильтра по дате.

        Args:
            date_from: Начальная дата
            date_to: Конечная дата

        Returns:
            Словарь фильтра
        """
        if not date_from and not date_to:
            return {}

        filter_dict = {}

        if date_from:
            # Начало дня
            filter_dict["from"] = date_from.replace(
                hour=0, minute=0, second=0, microsecond=0
            ).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        if date_to:
            # Конец дня
            filter_dict["to"] = date_to.replace(
                hour=23, minute=59, second=59, microsecond=999000
            ).strftime("%Y-%m-%dT%H:%M:%S.999Z")

        return filter_dict
