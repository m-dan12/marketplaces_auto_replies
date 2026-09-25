"""
Unit-тесты для OzonReplier - генерация ответов на отзывы.
"""

import sys
from pathlib import Path

# Настройка UTF-8 для Windows консоли
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from config.accounts import get_account_config
from marketplaces.ozon.replier import OzonReviewReplier


@pytest.fixture
def replier():
    """Создаёт экземпляр OzonReviewReplier с загруженными данными Milky Garden."""
    config = get_account_config("milky_garden")
    return OzonReviewReplier(
        cookies_file=config["cookies_file"],
        company_id=config["company_id"],
        data_dir=config["data_dir"],
        drive_folder=config["drive_folder"],
        brand_name=config["brand_name"],
    )


@pytest.fixture
def test_review_5_star():
    """Реальный 5★ отзыв для тестирования алгоритма рекомендаций."""
    return {
        "uuid": "01a0c3bf-3cc6-7b03-86eb-ff73c0eba79f",
        "product": {
            "title": 'Наволочка 2шт сатин Milky Garden Милки Гарден "Розы" 70х70 см на молнии',
            "url": "https://www.ozon.ru/product/690286310/",
            "offer_id": "MY4359/0-0-28/1",
            "cover_image": "https://ir.ozone.ru/s3/multimedia-1-f/8888616699.jpg",
            "sku": "690286310",
            "brand_info": {"id": "85930784", "name": "Milky Garden"},
        },
        "orderDeliveryType": "REVIEW_ORDER_DELIVERY_DONE",
        "text": "Качественно и нежно.",
        "interaction_status": "VIEWED",
        "rating": 5,
        "photos_count": 0,
        "videos_count": 0,
        "comments_count": 0,
        "published_at": "2026-09-21T11:34:48.325045Z",
        "is_pinned": False,
        "is_quality_control": False,
        "is_delivery_review": False,
        "is_commentable": True,
        "is_commentable_2": True,
        "publish_delayed_info": None,
        "is_empty": False,
    }


def test_generate_reply_for_5_star_with_recommendations(replier, test_review_5_star):
    """
    Тест: генерация персонального ответа на 5★ отзыв с рекомендациями.

    Ожидаемое поведение:
    1. Должен найти product_id по offer_id через индекс
    2. Должен подобрать рекомендации того же дизайна (Розы)
    3. Должен сгенерировать ответ с благодарностью + рекомендациями
    4. НЕ должен использовать шаблонные ответы
    """
    rating = test_review_5_star["rating"]
    offer_id = test_review_5_star["product"]["offer_id"]
    review_text = test_review_5_star["text"]

    reply = replier._generate_reply(rating, offer_id, review_text)

    # Проверяем что ответ не пустой
    assert reply, "Ответ не должен быть пустым"

    # Проверяем что это не шаблонный ответ
    template_phrases = [
        "постоянных покупателей",
        "Спасибо за отзыв! Мы очень рады",
        "Надеемся увидеть вас снова",
    ]
    is_template = any(phrase in reply for phrase in template_phrases)
    assert not is_template, f"Не должен использовать шаблон, но получили: {reply[:100]}..."

    # Проверяем наличие благодарности
    assert "спасибо" in reply.lower() or "благодарим" in reply.lower(), \
        "Ответ должен содержать благодарность"

    # Проверяем наличие рекомендаций (маркеры: "дизайн", "арт. Ozon", размеры)
    recommendation_markers = ["дизайн", "арт. ozon", "простынь", "наволочк", "пододеяльник"]
    has_recommendations = any(marker in reply.lower() for marker in recommendation_markers)
    assert has_recommendations, f"Ответ должен содержать рекомендации, но получили: {reply}"

    # Проверяем что есть хотя бы один артикул Ozon в рекомендациях
    assert "арт. ozon" in reply.lower() or "арт. Ozon" in reply, \
        "Ответ должен содержать артикулы Ozon в рекомендациях"

    print(f"\n✅ Сгенерированный ответ:\n{reply}\n")


def test_offer_id_to_product_id_mapping(replier, test_review_5_star):
    """
    Тест: проверка маппинга offer_id -> product_id.
    """
    offer_id = test_review_5_star["product"]["offer_id"]

    # Проверяем что индекс загружен
    assert replier.offer_to_product, "Индекс offer_id -> product_id должен быть загружен"

    # Проверяем что offer_id найден
    product_id = replier.offer_to_product.get(offer_id)
    assert product_id is not None, f"Product ID не найден для offer_id: {offer_id}"

    # Проверяем что product_id существует в cards
    assert product_id in replier.cards, \
        f"Product ID {product_id} должен существовать в cards"

    card = replier.cards[product_id]
    assert card.offer_id == offer_id, \
        f"Обратный маппинг не совпадает: {card.offer_id} != {offer_id}"

    print(f"\n✅ Маппинг: offer_id={offer_id} -> product_id={product_id}")
    print(f"   Карточка: {card.article_key} ({card.offer_group})")


def test_recommendations_exist_for_roses_design(replier, test_review_5_star):
    """
    Тест: проверка что для дизайна "Розы" есть рекомендации.
    """
    from shared.recommendations import find_recommendations

    offer_id = test_review_5_star["product"]["offer_id"]
    product_id = replier.offer_to_product.get(offer_id)

    assert product_id, f"Product ID не найден для offer_id: {offer_id}"

    # Ищем рекомендации
    recommendations = find_recommendations(
        product_id, replier.cards, replier.offer_index, max_reco=8
    )

    # Проверяем что рекомендации найдены
    assert recommendations, \
        f"Для product_id={product_id} (дизайн Розы) должны быть рекомендации"

    # Проверяем что все рекомендации того же дизайна
    purchased_card = replier.cards[product_id]
    for reco in recommendations:
        assert reco.design_key == purchased_card.design_key, \
            f"Рекомендация {reco.article_key} имеет другой дизайн"

    print(f"\n✅ Найдено {len(recommendations)} рекомендаций для дизайна '{purchased_card.design_key}':")
    for reco in recommendations:
        print(f"   - {reco.article_key} ({reco.offer_group}) - остаток: {reco.stock}")


if __name__ == "__main__":
    # Для быстрого запуска без pytest
    _config = get_account_config("milky_garden")
    replier = OzonReviewReplier(
        cookies_file=_config["cookies_file"],
        company_id=_config["company_id"],
        data_dir=_config["data_dir"],
        drive_folder=_config["drive_folder"],
        brand_name=_config["brand_name"],
    )

    test_review = {
        "uuid": "01a0c3bf-3cc6-7b03-86eb-ff73c0eba79f",
        "product": {
            "title": 'Наволочка 2шт сатин Milky Garden Милки Гарден "Розы" 70х70 см на молнии',
            "url": "https://www.ozon.ru/product/690286310/",
            "offer_id": "MY4359/0-0-28/1",
            "cover_image": "https://ir.ozone.ru/s3/multimedia-1-f/8888616699.jpg",
            "sku": "690286310",
            "brand_info": {"id": "85930784", "name": "Milky Garden"},
        },
        "text": "Качественно и нежно.",
        "rating": 5,
    }

    print("=" * 60)
    print("Тест генерации ответа для 5★ отзыва")
    print("=" * 60)
    test_generate_reply_for_5_star_with_recommendations(replier, test_review)

    print("\n" + "=" * 60)
    print("Тест маппинга offer_id -> product_id")
    print("=" * 60)
    test_offer_id_to_product_id_mapping(replier, test_review)

    print("\n" + "=" * 60)
    print("Тест наличия рекомендаций")
    print("=" * 60)
    test_recommendations_exist_for_roses_design(replier, test_review)
