"""Конфигурация аккаунтов для работы с несколькими кабинетами Ozon."""

from pathlib import Path
from typing import Dict, List

# Корневая директория проекта
PROJECT_ROOT = Path(__file__).parent.parent

# Корневая папка профилей Chrome для получения cookies через CDP (см.
# marketplaces/ozon/cdp_cookie_fetcher.py). Вне PROJECT_ROOT намеренно —
# профили создаются один раз вручную (человек логинится сам) и живут
# независимо от проекта.
CDP_PROFILES_ROOT = Path(r"C:\ChromeProfiles")

# Конфигурация аккаунтов
ACCOUNTS: Dict[str, Dict] = {
    "skazka": {
        "display_name": "Сказка",
        # OZON_CLIENT_ID_SKAZKA в .env (ООО "Профтекс") — заведён первым, до того как
        # для Milky Garden/Timeless появились именованные суффиксы, подтверждено.
        "company_id": "1128636",
        "cookies_file": PROJECT_ROOT / "cookies" / "skazka_cookies.json",
        "data_dir": PROJECT_ROOT / "data" / "skazka",
        "brand_name": "«Сказка»",
        "drive_folder": "Кабинет 1 (Профтекс)",
        "wb_token_file": PROJECT_ROOT / "cookies" / "skazka_wb_token.json",
        "wb_data_dir": PROJECT_ROOT / "data" / "skazka" / "wb",
        "wb_brand_name": "«Сказка»",
        "wb_drive_folder": "Кабинет 1 (Сказка)",
        "cdp_profile_dir": CDP_PROFILES_ROOT / "skazka",
        "cdp_port": 9222,
    },
    "milky_garden": {
        "display_name": "Milky Garden",
        "company_id": "103012",  # OZON_CLIENT_ID_MILKY в .env
        "cookies_file": PROJECT_ROOT / "cookies" / "milky_garden_cookies.json",
        "data_dir": PROJECT_ROOT / "data" / "milky_garden",
        "brand_name": "«МилкиГарден»",
        "drive_folder": "Кабинет 3 (Milky Garden)",
        "wb_token_file": PROJECT_ROOT / "cookies" / "milky_garden_wb_token.json",
        "wb_data_dir": PROJECT_ROOT / "data" / "milky_garden" / "wb",
        "wb_brand_name": "«МилкиГарден»",
        "wb_drive_folder": "Кабинет 2 (Milky Garden)",
        "cdp_profile_dir": CDP_PROFILES_ROOT / "milky_garden",
        "cdp_port": 9223,
    },
    "timeless": {
        "display_name": "Timeless",
        "company_id": "315335",  # OZON_CLIENT_ID_TIMELESS в .env
        "cookies_file": PROJECT_ROOT / "cookies" / "timeless_cookies.json",
        "data_dir": PROJECT_ROOT / "data" / "timeless",
        "brand_name": "«Timeless»",
        "drive_folder": "Кабинет 2 (Timeless)",
        "wb_token_file": PROJECT_ROOT / "cookies" / "timeless_wb_token.json",
        "wb_data_dir": PROJECT_ROOT / "data" / "timeless" / "wb",
        # На Wildberries у этого кабинета кириллическое название бренда
        # (в отличие от «Timeless» на Ozon) — так было заведено в WB Seller.
        "wb_brand_name": "«Таймлесс»",
        "wb_drive_folder": "Кабинет 3 (Timeless)",
        "cdp_profile_dir": CDP_PROFILES_ROOT / "timeless",
        "cdp_port": 9224,
    },
}


def get_account_config(account: str) -> Dict:
    """
    Получить конфигурацию аккаунта.

    Args:
        account: Название аккаунта (skazka, milky_garden, timeless)

    Returns:
        Словарь с конфигурацией

    Raises:
        ValueError: Если аккаунт не найден
    """
    if account not in ACCOUNTS:
        raise ValueError(
            f"Неизвестный аккаунт: {account}. "
            f"Доступные: {', '.join(ACCOUNTS.keys())}"
        )

    return ACCOUNTS[account]


def get_all_accounts() -> List[str]:
    """
    Получить список всех доступных аккаунтов.

    Returns:
        Список названий аккаунтов
    """
    return list(ACCOUNTS.keys())


def validate_account(account: str) -> bool:
    """
    Проверить, существует ли аккаунт.

    Args:
        account: Название аккаунта

    Returns:
        True если аккаунт существует
    """
    return account in ACCOUNTS
