"""Анализ истории для определения периода сбора."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.logger import logger


class HistoryAnalyzer:
    """Анализатор истории выгрузок для определения периода и обработанных отзывов."""

    def __init__(self, data_dir: Path):
        """
        Инициализация анализатора.

        Args:
            data_dir: Директория с предыдущими выгрузками
        """
        self.data_dir = data_dir

    def _load_previous_exports(self) -> List[Dict[str, Any]]:
        """
        Загрузка всех предыдущих выгрузок.

        Returns:
            Список данных из всех JSON-файлов
        """
        if not self.data_dir.exists():
            return []

        exports = []
        for json_file in sorted(self.data_dir.glob("reviews_*.json")):
            # Пропускаем временные файлы
            if "_temp_" in json_file.name:
                continue

            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    exports.append(data)
            except Exception as e:
                logger.warning(f"⚠️  Не удалось загрузить {json_file.name}: {e}")
                continue

        return exports

    def find_last_answered_review(self) -> Optional[Dict[str, Any]]:
        """
        Находит последний отзыв, на который был дан ответ.

        Returns:
            Словарь с информацией о последнем отзыве с ответом или None
        """
        exports = self._load_previous_exports()
        if not exports:
            logger.info("📭 Предыдущих выгрузок не найдено")
            return None

        last_answered = None
        last_date = None

        for export in exports:
            # Поддержка двух форматов: {metadata, reviews} и просто массив
            if isinstance(export, dict):
                reviews = export.get("reviews", [])
            elif isinstance(export, list):
                reviews = export
            else:
                continue

            for review in reviews:
                # Проверяем наличие ответа
                has_answer = self._has_answer(review)

                if has_answer:
                    # Парсим дату публикации отзыва
                    review_date = self._parse_date(review.get("published_at"))

                    if review_date and (last_date is None or review_date > last_date):
                        last_date = review_date
                        last_answered = {
                            "uuid": review.get("uuid"),
                            "published_at": review.get("published_at"),
                            "rating": review.get("rating"),
                            "text": review.get("text", "")[:100],
                        }

        return last_answered

    def _has_answer(self, review: Dict[str, Any]) -> bool:
        """
        Проверяет, есть ли ответ на отзыв.

        Args:
            review: Данные отзыва

        Returns:
            True если есть ответ
        """
        # Проверяем comments (основное поле для ответов)
        if review.get("comments"):
            comments = review["comments"]
            if isinstance(comments, list) and len(comments) > 0:
                # Проверяем, есть ли хотя бы один комментарий от продавца
                for comment in comments:
                    if isinstance(comment, dict):
                        if comment.get("type") == "seller":
                            return True
                        if comment.get("author_type") == "seller":
                            return True
                        if comment.get("role") == "seller":
                            return True
                # Если есть хоть какие-то комментарии, скорее всего это ответ
                return True

        if review.get("seller_comment"):
            return True

        if review.get("answers") and len(review["answers"]) > 0:
            return True

        if review.get("answer_text"):
            return True

        if review.get("has_answer") is True:
            return True

        if review.get("reply"):
            return True

        # Также проверяем interaction_status
        interaction_status = review.get("interaction_status")
        if interaction_status in ("ANSWERED", "REPLIED", "COMMENTED"):
            return True

        return False

    def _parse_date(self, date_string: Optional[str]) -> Optional[datetime]:
        """
        Парсинг даты из строки.

        Args:
            date_string: Строка с датой

        Returns:
            Объект datetime или None
        """
        if not date_string:
            return None

        try:
            # Пробуем разные форматы
            formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_string, fmt)
                except ValueError:
                    continue

            # Если не подошёл ни один формат, пробуем ISO
            return datetime.fromisoformat(date_string.replace("Z", "+00:00"))

        except Exception:
            return None

    def get_unanswered_reviews(
        self, reviews: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Фильтрует отзывы, оставляя только те, на которые нет ответа.

        Args:
            reviews: Список всех отзывов

        Returns:
            Список отзывов без ответов
        """
        unanswered = []
        answered_count = 0

        for review in reviews:
            if not self._has_answer(review):
                unanswered.append(review)
            else:
                answered_count += 1

        logger.info(f"📊 Отфильтровано: неотвеченных {len(unanswered)}, отвеченных {answered_count}")

        return unanswered
