"""Отправка ответов на отзывы Wildberries."""

import random
import time
from pathlib import Path
from typing import Dict, Optional

from config.templates import WB_REPLY_TEMPLATES
from config.wb_config import FEEDBACKS_DELAY, MAX_REPLIES_PER_RUN
from marketplaces.wb.api_client import WBAPIClient
from shared.article_parsing import resolve_sub_brand
from shared.drive_stocks_client import load_wb_stocks_from_drive
from shared.llm_client import generate_issue_reply
from shared.logger import logger
from shared.recommendations import (
    build_offer_index,
    find_recommendations,
    generate_reply_text,
    load_product_cards,
)
from shared.review_heuristics import ISSUE_LABELS, detect_review_issue
from shared.storage import JSONStorage


class WBReviewReplier:
    """Отправка ответов на отзывы Wildberries."""

    def __init__(
        self,
        token_file: Path,
        data_dir: Path,
        brand_name: str,
        drive_folder: str,
        sub_brands: Optional[Dict[str, str]] = None,
    ):
        """
        Инициализация.

        Args:
            token_file: Путь к JSON-файлу с токеном WB (feedback_token)
            data_dir: Директория с данными
            brand_name: Название бренда для подстановки в текст ответов (например, «Сказка»)
            drive_folder: Название папки на Google Drive с файлом остатков этого кабинета
                (см. `wb_drive_folder` в `config/accounts.py`)
            sub_brands: Словарь {префикс_дизайна: подпись_бренда} для кабинетов,
                торгующих несколькими брендами (см. `resolve_sub_brand`)
        """
        self.api_client = WBAPIClient(token_file)
        self.storage = JSONStorage(data_dir)
        self.data_dir = data_dir
        self.brand_name = brand_name
        self.sub_brands = sub_brands or {}

        # Тот же алгоритм рекомендаций, что у Ozon — только остатки читаются
        # из WB-папки на Google Drive (nmId/vendorCode вместо product_id/offer_id)
        logger.info("📦 Загрузка данных для алгоритма рекомендаций...")
        try:
            self.stocks = load_wb_stocks_from_drive(drive_folder)
            self.cards = load_product_cards(self.stocks)
            self.offer_index = build_offer_index(self.cards)

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
            reviews_file: Путь к файлу с отзывами (если None — берётся последний)

        Returns:
            Статистика: {success: int, failed: int, skipped: int}
        """
        logger.info("🚀 Запуск отправки ответов на отзывы Wildberries\n")

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

        stats = {"success": 0, "failed": 0, "skipped": 0}

        for i, review in enumerate(reviews, 1):
            if stats["success"] >= MAX_REPLIES_PER_RUN:
                logger.info(f"⏭️  Достигнут лимит {MAX_REPLIES_PER_RUN} ответов за запуск, останавливаемся")
                break

            logger.info(f"[{i}/{len(reviews)}] Обработка отзыва...")
            result = self._reply_to_single_review(review)

            if result == "success":
                stats["success"] += 1
            elif result == "failed":
                stats["failed"] += 1
            else:
                stats["skipped"] += 1

            if i < len(reviews):
                time.sleep(FEEDBACKS_DELAY)

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
            review: Сырой объект отзыва (как получен от API Wildberries)

        Returns:
            Статус: "success", "failed", "skipped"
        """
        feedback_id = review.get("id")
        rating = int(review.get("productValuation") or 0)
        product_details = review.get("productDetails") or {}
        supplier_article = product_details.get("supplierArticle")
        review_text = " | ".join(
            part for part in (review.get("text"), review.get("pros"), review.get("cons")) if part
        )

        if not feedback_id:
            logger.warning("   ⚠️  ID отзыва отсутствует, пропускаем")
            return "skipped"

        if rating not in (1, 2, 3, 4, 5):
            logger.warning(f"   ⚠️  Неожиданный рейтинг {rating}, пропускаем")
            return "skipped"

        reply_text = self._generate_reply(rating, supplier_article, review_text)

        logger.info(f"   ID: {feedback_id}")
        logger.info(f"   Рейтинг: {rating}⭐")
        logger.info(f"   Ответ: {reply_text[:50]}...")

        try:
            self.api_client.answer_feedback(feedback_id, reply_text, min_delay=FEEDBACKS_DELAY)
            logger.info("   ✅ Ответ отправлен")
            return "success"
        except Exception as e:
            logger.error(f"   ❌ Ошибка отправки: {e}")
            return "failed"

    def _generate_reply(self, rating: int, supplier_article: Optional[str], review_text: str) -> str:
        """
        Генерирует ответ на отзыв.

        Args:
            rating: Рейтинг отзыва (1-5)
            supplier_article: Артикул продавца (vendorCode), например "PT140/0-0-56/1"
            review_text: Текст отзыва (text + pros + cons)

        Returns:
            Текст ответа
        """
        brand_name = resolve_sub_brand(supplier_article, self.sub_brands, self.brand_name)

        if rating == 5 and supplier_article and self.cards and self.offer_index:
            product_id = self.offer_to_product.get(supplier_article)
            if not product_id:
                logger.warning(f"   ⚠️  Товар не найден в каталоге остатков для артикула: {supplier_article}")
            else:
                try:
                    recommendations = find_recommendations(
                        product_id, self.cards, self.offer_index, max_reco=8
                    )

                    if recommendations:
                        reply = generate_reply_text(
                            review_text, recommendations, brand_name=brand_name, marketplace_label="WB"
                        )
                        logger.info(f"   🎯 Найдено рекомендаций: {len(recommendations)}")
                        return reply
                except Exception as e:
                    logger.warning(f"   ⚠️  Ошибка генерации рекомендаций: {e}")

        # Для 1-4★ с явной, узнаваемой проблемой в тексте — адресный ответ через Gemini
        # вместо общего шаблона (см. shared/llm_client.py).
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

        return self._select_template(rating)

    def _select_template(self, rating: int) -> str:
        """
        Выбрать фиксированный шаблон для рейтинга 1-4 (для 5★ см. _generate_reply).

        Args:
            rating: Рейтинг отзыва (1-5)

        Returns:
            Текст ответа
        """
        templates = WB_REPLY_TEMPLATES.get(rating, WB_REPLY_TEMPLATES[1])
        return random.choice(templates)

    def _find_latest_reviews_file(self) -> Optional[Path]:
        """Найти последний файл с отзывами."""
        review_files = sorted(self.data_dir.glob("reviews_*.json"), reverse=True)
        review_files = [f for f in review_files if "_temp_" not in f.name]
        return review_files[0] if review_files else None
