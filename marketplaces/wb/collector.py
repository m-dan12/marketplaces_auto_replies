"""Сборщик отзывов Wildberries."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from config.wb_config import FEEDBACK_TAKE, FEEDBACK_DAYS_BACK, FEEDBACKS_DELAY, MAX_FEEDBACK_TOTAL
from marketplaces.wb.api_client import WBAPIClient
from shared.logger import logger
from shared.storage import JSONStorage


class WBReviewCollector:
    """Сборщик неотвеченных отзывов Wildberries."""

    def __init__(self, token_file: Path, data_dir: Path):
        """
        Инициализация сборщика.

        Args:
            token_file: Путь к JSON-файлу с токеном WB (feedback_token)
            data_dir: Директория для сохранения данных
        """
        self.api_client = WBAPIClient(token_file)
        self.storage = JSONStorage(data_dir)
        self.data_dir = data_dir

    def collect_reviews(self, max_total: int = MAX_FEEDBACK_TOTAL) -> List[Dict[str, Any]]:
        """
        Сбор неотвеченных отзывов за последние FEEDBACK_DAYS_BACK дней.

        В отличие от Ozon, Wildberries сам фильтрует неотвеченные отзывы через
        параметр isAnswered=false, поэтому доп. постобработка не нужна.

        Args:
            max_total: Максимум отзывов за один запуск

        Returns:
            Список сырых объектов отзывов (как есть из API Wildberries)
        """
        now = datetime.now(timezone.utc)
        date_to = int(now.timestamp())
        date_from = int((now - timedelta(days=FEEDBACK_DAYS_BACK)).timestamp())

        logger.info(f"🔍 Собираем неотвеченные отзывы WB (период: последние {FEEDBACK_DAYS_BACK} дней)...\n")

        collected: List[Dict[str, Any]] = []
        skip = 0

        while len(collected) < max_total:
            take = min(FEEDBACK_TAKE, max_total - len(collected))
            logger.info(f"📄 Запрос: skip={skip}, take={take}...")

            payload = self.api_client.get_feedbacks(
                is_answered=False,
                take=take,
                skip=skip,
                date_from=date_from,
                date_to=date_to,
                min_delay=FEEDBACKS_DELAY,
            )
            items = ((payload or {}).get("data") or {}).get("feedbacks") or []

            if not items:
                break

            collected.extend(items)
            logger.info(f"   Получено: {len(items)} отзывов (всего: {len(collected)})")

            if len(items) < take:
                break
            skip += take

        logger.info(f"\n✅ Собрано отзывов, ожидающих ответа: {len(collected)}")
        return collected
