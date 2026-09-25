"""Разбор артикулов продавца формата `PT140/0-0-56/1` (общий для Ozon и Wildberries).

Структура артикула:
    design_key  — дизайн/принт, первая часть до "/" (например, PT140)
    article_key — ключ размера/варианта, вторая часть (например, 0-0-56)
"""

import re
from typing import Dict, Optional, Tuple


def parse_article_key(article: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Парсит артикул продавца вида "PT140/0-0-56/1" или "59295930/6-17-26/1".

    Args:
        article: offer_id (Ozon) или vendorCode/supplierArticle (Wildberries)

    Returns:
        (design_key, article_key), например ("PT140", "0-0-56")
    """
    if not article:
        return None, None

    parts = article.strip().split("/")
    if len(parts) < 2:
        return None, None

    design_raw = parts[0].strip()
    article_key = parts[1].strip()

    # Сохраняем буквенный префикс бренда как есть (например, "AM4492" -> "AM4492"),
    # а не только цифры — иначе разные бренды с совпадающими цифрами (например,
    # "AM4492" у Анна Мария и гипотетический "4492" у Сказки) схлопнутся в один
    # design_key и получат рекомендации друг друга. Проверено эмпирически 2026-09-25.
    design_key = design_raw.upper().replace(" ", "")

    return (design_key or None, article_key or None)


def parse_key_triplet(key: Optional[str]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Парсит ключ размера вида "5-16-28" на три числа.

    Args:
        key: Ключ размера, например "0-0-56"

    Returns:
        (a, b, c), например (0, 0, 56); (None, None, None) если формат не подошёл
    """
    if not key:
        return None, None, None

    match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*", key.strip())
    if not match:
        return None, None, None

    a, b, c = (int(value) for value in match.groups())
    return a, b, c


def resolve_sub_brand(offer_id: Optional[str], sub_brands: Optional[Dict[str, str]], default_brand: str) -> str:
    """
    Определяет подпись бренда для товара по префиксу дизайна.

    Некоторые кабинеты продают товары нескольких брендов под одним договором
    (например, skazka: основной бренд «Сказка» + «Анна Мария» под дизайнами
    вида "AM4492/..."). См. `sub_brands` в `config/accounts.py`.

    Args:
        offer_id: Артикул продавца, например "AM4492/0-13-0/0"
        sub_brands: Словарь {префикс_дизайна: подпись_бренда}, например
            {"AM": "«Анна Мария»"}; None/пустой — просто вернёт default_brand
        default_brand: Подпись бренда по умолчанию для этого аккаунта

    Returns:
        Подпись бренда для этого конкретного товара
    """
    if not sub_brands:
        return default_brand

    design_key, _ = parse_article_key(offer_id)
    if not design_key:
        return default_brand

    for prefix, brand in sub_brands.items():
        if design_key.startswith(prefix.upper()):
            return brand

    return default_brand
