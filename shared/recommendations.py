"""Логика формирования рекомендаций товаров для ответов на 5★ отзывы (Ozon)."""

import json
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from shared.article_parsing import parse_article_key, parse_key_triplet
from shared.review_heuristics import (
    GROUP_TITLES,
    GROUPS_ORDER,
    MAX_REPLY_LEN,
    build_grouped_text,
    build_intro,
    looks_negative_5star,
    pick_standard_reply,
)

SIZE_DESCRIPTIONS_FILE = Path(__file__).parent.parent / "config" / "size_descriptions.json"


@dataclass
class ProductCard:
    """Карточка товара с остатками."""
    product_id: int
    offer_id: str
    design_key: str  # Например, PT140
    article_key: str  # Например, 0-0-56
    offer_group: str  # Например, Наволочки
    stock: int


def classify_offer_group(article_key: Optional[str]) -> str:
    """
    Определяет группу товара по ключу размера.

    Args:
        article_key: Например, "0-0-56" или "5-16-28"

    Returns:
        Группа: Наволочки, Простыня натяжная, Простыня классическая, Пододеяльник, Другое
    """
    a, b, c = parse_key_triplet(article_key)

    # Наволочки: только c != 0
    if a == 0 and b == 0 and c and c > 0:
        return 'Наволочки'

    # Пододеяльник: только a != 0
    if a and a > 0 and b == 0 and c == 0:
        return 'Пододеяльник'

    # Простыни: b != 0
    if a == 0 and b and b > 0 and c == 0:
        # Натяжные: 13-17
        if 13 <= b <= 17:
            return 'Простыня натяжная'
        # Классические: 18-20
        if 18 <= b <= 20:
            return 'Простыня классическая'
        return 'Простыня классическая'  # По умолчанию

    # Комплекты: все ненулевые
    if a and a > 0 and b and b > 0 and c and c > 0:
        return 'Комплект'

    return 'Другое'


def load_product_cards(
    stocks: Dict[str, tuple[int, int]]
) -> Dict[int, ProductCard]:
    """
    Загружает карточки товаров из данных с остатками.

    Args:
        stocks: Словарь {offer_id: (product_id, total_stock)}

    Returns:
        Словарь {product_id: ProductCard}
    """
    cards: Dict[int, ProductCard] = {}

    for offer_id, (product_id, stock) in stocks.items():
        design_key, article_key = parse_article_key(offer_id)
        if not design_key or not article_key:
            continue

        offer_group = classify_offer_group(article_key)

        cards[product_id] = ProductCard(
            product_id=product_id,
            offer_id=offer_id,
            design_key=design_key,
            article_key=article_key,
            offer_group=offer_group,
            stock=stock,
        )

    return cards


def build_offer_index(cards: Dict[int, ProductCard]) -> Dict[str, List[ProductCard]]:
    """
    Строит индекс: design_key -> список карточек с остатком > 0.

    Args:
        cards: Все карточки товаров

    Returns:
        Индекс {design_key: [ProductCard, ...]}
    """
    index: Dict[str, List[ProductCard]] = defaultdict(list)

    for card in cards.values():
        if card.stock <= 0:
            continue
        if card.offer_group in {'Наволочки', 'Простыня натяжная', 'Простыня классическая', 'Пододеяльник'}:
            index[card.design_key].append(card)

    # Сортируем по убыванию остатка
    for design_key in index:
        index[design_key].sort(key=lambda x: (-x.stock, x.article_key, x.product_id))

    return dict(index)


def find_recommendations(
    purchased_product_id: int,
    cards: Dict[int, ProductCard],
    offer_index: Dict[str, List[ProductCard]],
    max_reco: int = 8,
) -> List[ProductCard]:
    """
    Подбирает рекомендации товаров того же дизайна.

    Args:
        purchased_product_id: ID купленного товара
        cards: Все карточки
        offer_index: Индекс по дизайнам
        max_reco: Максимальное количество рекомендаций

    Returns:
        Список рекомендованных карточек
    """
    purchased = cards.get(purchased_product_id)
    if not purchased:
        return []

    candidates = offer_index.get(purchased.design_key, [])
    if not candidates:
        return []

    # Исключаем купленный товар
    result: List[ProductCard] = []
    for card in candidates:
        if card.product_id == purchased_product_id:
            continue
        if card.article_key == purchased.article_key:
            continue
        result.append(card)

    # Группируем по типам
    by_group: Dict[str, List[ProductCard]] = defaultdict(list)
    for card in result:
        by_group[card.offer_group].append(card)

    # Берём по 3 из каждой группы
    final: List[ProductCard] = []
    for group in GROUPS_ORDER:
        for card in by_group.get(group, [])[:3]:
            final.append(card)
            if len(final) >= max_reco:
                break
        if len(final) >= max_reco:
            break

    return final[:max_reco]


@lru_cache(maxsize=1)
def load_size_descriptions() -> Dict[str, str]:
    """
    Загружает человекочитаемые описания размеров по article_key.

    Файл собран из справочника "ключи, описание.xlsx" (см. config/size_descriptions.json).

    Returns:
        Словарь {article_key: описание}, например {"0-0-56": "50х70см, 1шт классическая, на молнии"}
    """
    if not SIZE_DESCRIPTIONS_FILE.exists():
        return {}

    with open(SIZE_DESCRIPTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_recommendations_text(recommendations: List[ProductCard], marketplace_label: str = 'Ozon') -> str:
    """
    Формирует текст с рекомендациями для ответа.

    Args:
        recommendations: Список рекомендованных карточек
        marketplace_label: Подпись маркетплейса в артикуле ("Ozon" или "WB")

    Returns:
        Текст типа "Простынь на резинке: 180х200см (1,5 спальная) (арт. Ozon 123), ..."
    """
    if not recommendations:
        return ''

    size_descriptions = load_size_descriptions()
    by_group: Dict[str, List[str]] = defaultdict(list)

    for card in recommendations:
        group = card.offer_group
        # Фолбэк на сырой ключ, если для него нет описания в справочнике
        label = size_descriptions.get(card.article_key, card.article_key.replace('-', 'х'))
        by_group[group].append(f'{label} (арт. {marketplace_label} {card.product_id})')

    return build_grouped_text(by_group)


def generate_reply_text(
    review_text: Optional[str],
    recommendations: List[ProductCard],
    brand_name: str = '«МилкиГарден»',
    marketplace_label: str = 'Ozon',
) -> str:
    """
    Генерирует текст ответа на 5★ отзыв.

    Args:
        review_text: Текст отзыва
        recommendations: Рекомендованные товары
        brand_name: Название бренда
        marketplace_label: Подпись маркетплейса в артикуле рекомендаций
            ("Ozon" -> "арт. Ozon 123", "WB" -> "арт. WB 123")

    Returns:
        Текст ответа (макс 5000 символов)
    """
    # Негативный 5★ -> стандартный ответ
    if looks_negative_5star(review_text):
        return pick_standard_reply()[:MAX_REPLY_LEN]

    # Нет рекомендаций -> стандартный ответ
    if not recommendations:
        return pick_standard_reply()[:MAX_REPLY_LEN]

    # Формируем ответ с рекомендациями
    intro = build_intro(brand_name)
    reco_text = build_recommendations_text(recommendations, marketplace_label=marketplace_label)

    if not reco_text:
        return pick_standard_reply()[:MAX_REPLY_LEN]

    reply = f'{intro} Если захотите дополнить дизайн, можно посмотреть ✨:\n{reco_text} 🙂'
    return reply[:MAX_REPLY_LEN]
