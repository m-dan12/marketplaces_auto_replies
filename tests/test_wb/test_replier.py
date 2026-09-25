"""
Unit-тесты для WBReviewReplier - генерация ответов на отзывы Wildberries.

Зеркалирует tests/test_ozon/test_replier.py: тот же сценарий (5★ отзыв ->
алгоритм рекомендаций похожих товаров того же дизайна) и тот же общий
алгоритм из recommendations.py — только остатки читаются из WB-папки на
Google Drive (nmId/vendorCode) вместо Ozon-папки (product_id/offer_id).
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
from marketplaces.wb.replier import WBReviewReplier


@pytest.fixture
def replier():
    """Создаёт WBReviewReplier с загруженными остатками кабинета Сказка."""
    config = get_account_config("skazka")
    return WBReviewReplier(
        token_file=config["wb_token_file"],
        data_dir=config["wb_data_dir"],
        brand_name=config["wb_brand_name"],
        drive_folder=config["wb_drive_folder"],
    )


@pytest.fixture
def test_review_5_star():
    """
    Реальный 5★ отзыв Wildberries (наволочки дизайна PT1422) для теста алгоритма
    рекомендаций. Структура полей — как в ответе GET /api/v1/feedbacks.
    """
    return {
        "id": "1BxCJqsW-test-fixture-0000",
        "productValuation": 5,
        "text": "Очень качественные наволочки, спасибо!",
        "pros": "",
        "cons": "",
        "productDetails": {
            "productName": "Наволочка 2шт сатин Сказка PT1422",
            "supplierArticle": "PT1422/0-0-28/1",
            "nmId": 166685943,
        },
        "answer": None,
    }


def test_generate_reply_for_5_star_with_recommendations(replier, test_review_5_star):
    """
    Тест: генерация персонального ответа на 5★ отзыв с рекомендациями.

    Ожидаемое поведение:
    1. Должен найти product_id (nm_id) по артикулу через индекс
    2. Должен подобрать рекомендации того же дизайна (PT1422)
    3. Должен сгенерировать ответ с благодарностью + рекомендациями
    4. НЕ должен использовать фиксированные шаблоны 1-4★
    """
    rating = test_review_5_star["productValuation"]
    supplier_article = test_review_5_star["productDetails"]["supplierArticle"]
    review_text = test_review_5_star["text"]

    reply = replier._generate_reply(rating, supplier_article, review_text)

    assert reply, "Ответ не должен быть пустым"

    template_phrases = ["рекомендуем оформить", "деликатную стирку до 40"]
    is_template = any(phrase in reply for phrase in template_phrases)
    assert not is_template, f"Не должен использовать шаблон 1-4★, но получили: {reply[:150]}..."

    assert "спасибо" in reply.lower() or "благодар" in reply.lower(), \
        "Ответ должен содержать благодарность"

    assert "арт. wb" in reply.lower(), \
        f"Ответ должен содержать артикулы WB в рекомендациях, но получили: {reply}"

    print(f"\n✅ Сгенерированный ответ:\n{reply}\n")


def test_supplier_article_to_product_id_mapping(replier, test_review_5_star):
    """
    Тест: проверка маппинга supplierArticle (vendorCode) -> product_id (nmId).
    """
    supplier_article = test_review_5_star["productDetails"]["supplierArticle"]

    assert replier.offer_to_product, "Индекс артикул -> nmId должен быть загружен"

    product_id = replier.offer_to_product.get(supplier_article)
    assert product_id is not None, f"nmId не найден для артикула: {supplier_article}"
    assert product_id in replier.cards, f"nmId {product_id} должен существовать в cards"

    card = replier.cards[product_id]
    assert card.offer_id == supplier_article, \
        f"Обратный маппинг не совпадает: {card.offer_id} != {supplier_article}"

    print(f"\n✅ Маппинг: артикул={supplier_article} -> nmId={product_id}")
    print(f"   Карточка: {card.article_key} ({card.offer_group})")


def test_recommendations_exist_for_design(replier, test_review_5_star):
    """
    Тест: для дизайна PT1422 (наволочки) должны находиться рекомендации
    других типов товаров того же дизайна с остатком в наличии.
    """
    from shared.recommendations import find_recommendations

    supplier_article = test_review_5_star["productDetails"]["supplierArticle"]
    product_id = replier.offer_to_product.get(supplier_article)

    assert product_id, f"nmId не найден для артикула: {supplier_article}"

    recommendations = find_recommendations(product_id, replier.cards, replier.offer_index, max_reco=8)

    assert recommendations, f"Для product_id={product_id} (дизайн PT1422) должны быть рекомендации"

    purchased_card = replier.cards[product_id]
    for reco in recommendations:
        assert reco.design_key == purchased_card.design_key, \
            f"Рекомендация {reco.article_key} имеет другой дизайн"

    print(f"\n✅ Найдено {len(recommendations)} рекомендаций для дизайна '{purchased_card.design_key}':")
    for reco in recommendations:
        print(f"   - {reco.article_key} ({reco.offer_group}) - остаток: {reco.stock}")


if __name__ == "__main__":
    _config = get_account_config("skazka")
    _replier = WBReviewReplier(
        token_file=_config["wb_token_file"],
        data_dir=_config["wb_data_dir"],
        brand_name=_config["wb_brand_name"],
        drive_folder=_config["wb_drive_folder"],
    )

    _test_review = {
        "id": "1BxCJqsW-test-fixture-0000",
        "productValuation": 5,
        "text": "Очень качественные наволочки, спасибо!",
        "pros": "",
        "cons": "",
        "productDetails": {
            "productName": "Наволочка 2шт сатин Сказка PT1422",
            "supplierArticle": "PT1422/0-0-28/1",
            "nmId": 166685943,
        },
        "answer": None,
    }

    print("=" * 60)
    print("Тест генерации ответа для 5★ отзыва")
    print("=" * 60)
    test_generate_reply_for_5_star_with_recommendations(_replier, _test_review)

    print("\n" + "=" * 60)
    print("Тест маппинга артикул -> nmId")
    print("=" * 60)
    test_supplier_article_to_product_id_mapping(_replier, _test_review)

    print("\n" + "=" * 60)
    print("Тест наличия рекомендаций")
    print("=" * 60)
    test_recommendations_exist_for_design(_replier, _test_review)
