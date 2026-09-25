"""Разбор артикулов продавца формата `PT140/0-0-56/1` (общий для Ozon и Wildberries).

Структура артикула:
    design_key  — дизайн/принт, первая часть до "/" (например, PT140)
    article_key — ключ размера/варианта, вторая часть (например, 0-0-56)
"""

import re
from typing import Optional, Tuple


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

    design_digits = re.sub(r"[^0-9]", "", design_raw)
    design_key = design_digits if design_digits else design_raw.upper().replace(" ", "")

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
