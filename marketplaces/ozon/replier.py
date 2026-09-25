"""Отправка ответов на отзывы Ozon."""

import random
import time
from pathlib import Path
from typing import Dict, List, Optional

from config.ozon_config import REQUEST_DELAY
from config.templates import OZON_CANCELED_ORDER_HIGH_RATING_TEMPLATES, OZON_REPLY_TEMPLATES
from marketplaces.ozon.api_client import OzonAPIClient
from shared.article_parsing import resolve_sub_brand
from shared.drive_stocks_client import load_stocks_from_drive
from shared.gemini_client import generate_issue_reply
from shared.logger import logger
from shared.recommendations import (
    generate_reply_text,
    find_recommendations,
    load_product_cards,
    build_offer_index,
)
from shared.review_heuristics import ISSUE_LABELS, detect_review_issue
from shared.storage import JSONStorage


class OzonReviewReplier:
    """Отправка ответов на отзывы Ozon."""

    def __init__(
        self,
        cookies_file,
        company_id: str,
        data_dir,
        drive_folder: str,
        brand_name: str,
        sub_brands: Optional[Dict[str, str]] = None,
    ):
        """
        Инициализация.

        Args:
            cookies_file: Путь к файлу с cookies
            company_id: ID компании в Ozon
            data_dir: Директория с данными
            drive_folder: Название папки на Google Drive с файлом остатков для этого кабинета
            brand_name: Название бренда для подстановки в текст ответов
            sub_brands: Словарь {префикс_дизайна: подпись_бренда} для кабинетов,
                торгующих несколькими брендами (см. `resolve_sub_brand`)
        """
        self.api_client = OzonAPIClient(cookies_file, company_id)
        self.storage = JSONStorage(data_dir)
        self.data_dir = data_dir
        self.brand_name = brand_name
        self.sub_brands = sub_brands or {}

        # Загружаем остатки и карточки товаров для алгоритма рекомендаций
        logger.info("📦 Загрузка данных для алгоритма рекомендаций...")
        try:
            self.stocks = load_stocks_from_drive(drive_folder)
            self.cards = load_product_cards(self.stocks)
            self.offer_index = build_offer_index(self.cards)

            # Создаём индекс offer_id -> product_id
            self.offer_to_product: Dict[str, int] = {
                card.offer_id: card.product_id
                for card in self.cards.values()
            }

            logger.info(f"✅ Загружено {len(self.cards)} карточек товаров\n")
        except Exception as e:
            logger.warning(f"⚠️  Не удалось загрузить данные для рекомендаций: {e}")
            logger.warning("   Будут использоваться стандартные шаблоны\n")
            self.stocks = {}
            self.cards = {}
            self.offer_index = {}
            self.offer_to_product = {}

    def reply_to_reviews(self, reviews_file: Optional[Path] = None) -> Dict[str, int]:
        """
        Отправить ответы на отзывы.

        Args:
            reviews_file: Путь к файлу с отзывами (если None - берётся последний)

        Returns:
            Статистика: {success: int, failed: int, skipped: int}
        """
        logger.info("🚀 Запуск отправки ответов на отзывы Ozon\n")

        # Загружаем отзывы
        if reviews_file is None:
            reviews_file = self._find_latest_reviews_file()

        if not reviews_file or not reviews_file.exists():
            logger.error("❌ Файл с отзывами не найден")
            return {"success": 0, "failed": 0, "skipped": 0}

        logger.info(f"📁 Загрузка отзывов из {reviews_file.name}")

        reviews = self.storage.load_reviews(reviews_file)

        if not reviews:
            logger.info("⚠️  Нет отзывов для обработки\n")
            return {"success": 0, "failed": 0, "skipped": 0}

        logger.info(f"📊 Найдено отзывов: {len(reviews)}\n")

        # Отправляем ответы
        stats = {"success": 0, "failed": 0, "skipped": 0}

        for i, review in enumerate(reviews, 1):
            logger.info(f"[{i}/{len(reviews)}] Обработка отзыва...")

            result = self._reply_to_single_review(review)

            if result == "success":
                stats["success"] += 1
            elif result == "failed":
                stats["failed"] += 1
            else:
                stats["skipped"] += 1

            # Задержка между запросами
            if i < len(reviews):
                time.sleep(REQUEST_DELAY)

        # Итоги
        logger.info("\n" + "=" * 50)
        logger.info("📊 Итоговая статистика:")
        logger.info(f"   ✅ Успешно отправлено: {stats['success']}")
        logger.info(f"   ❌ Ошибок: {stats['failed']}")
        logger.info(f"   ⏭️  Пропущено: {stats['skipped']}")
        logger.info("=" * 50 + "\n")

        return stats

    def _reply_to_single_review(self, review: Dict) -> str:
        """
        Отправить ответ на один отзыв.

        Args:
            review: Объект отзыва

        Returns:
            Статус: "success", "failed", "skipped"
        """
        uuid = review.get("uuid")
        rating = review.get("rating", 5)
        offer_id = review.get("product", {}).get("offer_id")
        review_text = review.get("text", "")
        order_canceled = review.get("orderDeliveryType") == "REVIEW_ORDER_DELIVERY_CANCELED"

        if not uuid:
            logger.warning("   ⚠️  UUID отсутствует, пропускаем")
            return "skipped"

        # Выбираем шаблон / генерируем ответ
        reply_text = self._generate_reply(rating, offer_id, review_text, order_canceled)

        logger.info(f"   UUID: {uuid}")
        logger.info(f"   Рейтинг: {rating}⭐")
        logger.info(f"   Ответ: {reply_text[:50]}...")

        # Отправляем
        success = self.api_client.send_reply(uuid, reply_text)

        if success:
            logger.info("   ✅ Ответ отправлен")
            return "success"
        else:
            logger.error("   ❌ Ошибка отправки")
            return "failed"

    def _generate_reply(
        self, rating: int, offer_id: Optional[str], review_text: str, order_canceled: bool = False
    ) -> str:
        """
        Генерирует ответ на отзыв.

        Args:
            rating: Рейтинг отзыва (1-5)
            offer_id: Артикул продавца (offer_id)
            review_text: Текст отзыва
            order_canceled: Заказ был отменён (покупатель поставил оценку, но не купил товар)

        Returns:
            Текст ответа
        """
        # Нормализуем рейтинг
        rating = max(1, min(5, rating))

        # Подпись бренда для этого конкретного товара (кабинет skazka продаёт
        # и «Сказку», и «Анна Мария» под разными дизайнами — см. config/accounts.py)
        brand_name = resolve_sub_brand(offer_id, self.sub_brands, self.brand_name)

        # Высокая оценка (4-5) при отменённом заказе — без рекомендаций и советов по уходу,
        # товар покупателю не доехал. 1-3★ отвечаем как обычно.
        if order_canceled and rating >= 4:
            return random.choice(OZON_CANCELED_ORDER_HIGH_RATING_TEMPLATES)

        # Для 5★ пытаемся использовать алгоритм рекомендаций
        if rating == 5 and offer_id and self.cards and self.offer_index:
            # Находим product_id по offer_id
            product_id = self.offer_to_product.get(offer_id)
            if not product_id:
                logger.warning(f"   ⚠️  Product ID не найден для offer_id: {offer_id}")
            else:
                try:
                    recommendations = find_recommendations(
                        product_id, self.cards, self.offer_index, max_reco=8
                    )

                    if recommendations:
                        reply = generate_reply_text(review_text, recommendations, brand_name=brand_name)
                        logger.info(f"   🎯 Найдено рекомендаций: {len(recommendations)}")
                        return reply
                except Exception as e:
                    logger.warning(f"   ⚠️  Ошибка генерации рекомендаций: {e}")

        # Для 1-4★ с явной, узнаваемой проблемой в тексте — адресный ответ через Gemini
        # вместо общего шаблона (см. shared/gemini_client.py). Любая ошибка API —
        # тихий fallback на фиксированный шаблон.
        if rating < 5:
            issue = detect_review_issue(review_text)
            if issue in ISSUE_LABELS:
                try:
                    reply = generate_issue_reply(rating, review_text, issue, brand_name)
                    if reply:
                        logger.info(f"   🤖 Ответ сгенерирован через Gemini (категория: {issue})")
                        return reply
                except Exception as e:
                    logger.warning(f"   ⚠️  Ошибка генерации ответа через Gemini: {e}")

        # Fallback: используем старый метод с шаблонами
        return self._select_template(rating)

    def _select_template(self, rating: int) -> str:
        """
        Выбрать шаблон для рейтинга.

        Args:
            rating: Рейтинг отзыва (1-5)

        Returns:
            Текст ответа
        """
        # Нормализуем рейтинг
        rating = max(1, min(5, rating))

        # Для 1-3 звёзд используем один общий шаблон
        if rating <= 3:
            templates = OZON_REPLY_TEMPLATES[1]  # Все 1-3 используют одинаковый текст
        else:
            templates = OZON_REPLY_TEMPLATES.get(rating, OZON_REPLY_TEMPLATES[5])

        return random.choice(templates)

    def _find_latest_reviews_file(self) -> Optional[Path]:
        """Найти последний файл с отзывами."""
        review_files = sorted(self.data_dir.glob("reviews_*.json"), reverse=True)

        # Исключаем временные файлы
        review_files = [f for f in review_files if "_temp_" not in f.name]

        return review_files[0] if review_files else None
