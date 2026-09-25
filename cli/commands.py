"""CLI команды для работы с маркетплейсами."""

import json
from pathlib import Path

from config.accounts import get_account_config
from marketplaces.ozon.cdp_cookie_fetcher import CDPCookieFetcher
from marketplaces.ozon.collector import OzonReviewCollector
from marketplaces.ozon.replier import OzonReviewReplier
from marketplaces.wb.collector import WBReviewCollector
from marketplaces.wb.replier import WBReviewReplier
from shared.logger import logger

WB_ALIASES = ("wildberries", "wb", "вб")


def _fetch_cookies_via_cdp(config: dict) -> bool:
    """
    Забирает cookies ozon.ru через CDP и сохраняет их в файл аккаунта.

    Args:
        config: Конфигурация аккаунта (get_account_config)

    Returns:
        True если cookies получены и сохранены
    """
    fetcher = CDPCookieFetcher(config['cdp_profile_dir'], config['cdp_port'])
    cookie_string = fetcher.fetch_ozon_cookies()

    if not cookie_string:
        logger.error(
            f"❌ Не удалось получить cookies. Убедитесь, что профиль {config['cdp_profile_dir']} "
            f"существует и в нём выполнен вход в кабинет seller.ozon.ru\n"
        )
        return False

    cookies_file = config['cookies_file']
    cookies_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cookies_file, "w", encoding="utf-8") as f:
        json.dump({"cookies": cookie_string}, f, ensure_ascii=False, indent=2)

    logger.info(f"💾 Cookies сохранены в {cookies_file.name}\n")
    return True


def cmd_collect(marketplace: str, account: str) -> int:
    """
    Собрать неотвеченные отзывы.

    Args:
        marketplace: Название маркетплейса (ozon, wildberries)
        account: Название аккаунта (skazka, milky_garden, timeless)

    Returns:
        Код возврата (0 - успех, 1 - ошибка)
    """
    if marketplace.lower() in ["ozon", "озон"]:
        # Получаем конфигурацию аккаунта
        config = get_account_config(account)

        logger.info("=" * 60)
        logger.info(f"  Сборщик неотвеченных отзывов Ozon: {config['display_name']}")
        logger.info("=" * 60 + "\n")

        collector = OzonReviewCollector(
            cookies_file=config['cookies_file'],
            company_id=config['company_id'],
            data_dir=config['data_dir']
        )

        # Определяем период
        date_from, date_to = collector.determine_date_range()

        # Собираем отзывы
        reviews = collector.collect_reviews(date_from, date_to)

        if reviews:
            # Сохраняем
            filepath = collector.storage.save_reviews(reviews)
            logger.info(f"\n💾 Отзывы сохранены: {filepath.name}\n")
            logger.info("✅ Сбор отзывов завершён успешно\n")
            return 0
        else:
            logger.info("⚠️  Нет новых отзывов для сохранения\n")
            return 0

    elif marketplace.lower() in WB_ALIASES:
        config = get_account_config(account)

        logger.info("=" * 60)
        logger.info(f"  Сборщик неотвеченных отзывов Wildberries: {config['display_name']}")
        logger.info("=" * 60 + "\n")

        collector = WBReviewCollector(
            token_file=config["wb_token_file"],
            data_dir=config["wb_data_dir"],
        )

        reviews = collector.collect_reviews()

        if reviews:
            filepath = collector.storage.save_reviews(reviews)
            logger.info(f"\n💾 Отзывы сохранены: {filepath.name}\n")
            logger.info("✅ Сбор отзывов завершён успешно\n")
            return 0
        else:
            logger.info("⚠️  Нет новых отзывов для сохранения\n")
            return 0

    else:
        logger.error(f"❌ Неизвестный маркетплейс: {marketplace}\n")
        logger.info("Доступные: ozon, wildberries\n")
        return 1


def cmd_reply(marketplace: str, account: str, reviews_file: str = None) -> int:
    """
    Отправить ответы на отзывы.

    Args:
        marketplace: Название маркетплейса (ozon, wildberries)
        account: Название аккаунта (skazka, milky_garden, timeless)
        reviews_file: Путь к файлу с отзывами (опционально)

    Returns:
        Код возврата (0 - успех, 1 - ошибка)
    """
    if marketplace.lower() in ["ozon", "озон"]:
        # Получаем конфигурацию аккаунта
        config = get_account_config(account)

        logger.info("=" * 60)
        logger.info(f"  Отправка ответов Ozon: {config['display_name']}")
        logger.info("=" * 60 + "\n")

        replier = OzonReviewReplier(
            cookies_file=config['cookies_file'],
            company_id=config['company_id'],
            data_dir=config['data_dir'],
            drive_folder=config['drive_folder'],
            brand_name=config['brand_name'],
        )

        file_path = Path(reviews_file) if reviews_file else None
        stats = replier.reply_to_reviews(file_path)

        if stats["failed"] == 0:
            logger.info("✅ Отправка ответов завершена успешно\n")
            return 0
        else:
            logger.error("⚠️  Отправка ответов завершена с ошибками\n")
            return 1

    elif marketplace.lower() in WB_ALIASES:
        config = get_account_config(account)

        logger.info("=" * 60)
        logger.info(f"  Отправка ответов Wildberries: {config['display_name']}")
        logger.info("=" * 60 + "\n")

        replier = WBReviewReplier(
            token_file=config["wb_token_file"],
            data_dir=config["wb_data_dir"],
            brand_name=config["wb_brand_name"],
            drive_folder=config["wb_drive_folder"],
        )

        file_path = Path(reviews_file) if reviews_file else None
        stats = replier.reply_to_reviews(file_path)

        if stats["failed"] == 0:
            logger.info("✅ Отправка ответов завершена успешно\n")
            return 0
        else:
            logger.error("⚠️  Отправка ответов завершена с ошибками\n")
            return 1

    else:
        logger.error(f"❌ Неизвестный маркетплейс: {marketplace}\n")
        logger.info("Доступные: ozon, wildberries\n")
        return 1


def cmd_auto(marketplace: str, account: str) -> int:
    """
    Полный цикл: обновить cookies (Ozon) + собрать отзывы + отправить ответы.

    Для Ozon: update-cookies → collect → reply
    Для WB: collect → reply

    Args:
        marketplace: Название маркетплейса (ozon, wildberries)
        account: Название аккаунта (skazka, milky_garden, timeless)

    Returns:
        Код возврата (0 - успех, 1 - ошибка)
    """
    logger.info("🚀 Запуск полного цикла\n")

    if marketplace.lower() in ["ozon", "озон"]:
        # Получаем конфигурацию аккаунта
        config = get_account_config(account)

        # Шаг 0: Обновление cookies через CDP (обязательно для Ozon)
        logger.info("=" * 50)
        logger.info(f"Шаг 0: Обновление cookies через CDP ({config['display_name']})")
        logger.info("=" * 50 + "\n")

        if not _fetch_cookies_via_cdp(config):
            logger.error("❌ Не удалось получить cookies, цикл прерван\n")
            return 1

        logger.info("")

        # Сбор
        logger.info("=" * 50)
        logger.info(f"Шаг 1: Сбор неотвеченных отзывов ({config['display_name']})")
        logger.info("=" * 50 + "\n")

        collector = OzonReviewCollector(
            cookies_file=config['cookies_file'],
            company_id=config['company_id'],
            data_dir=config['data_dir']
        )

        date_from, date_to = collector.determine_date_range()
        reviews = collector.collect_reviews(date_from, date_to)

        if not reviews:
            logger.info("⚠️  Нет новых отзывов для обработки\n")
            return 0

        reviews_file = collector.storage.save_reviews(reviews)
        logger.info(f"\n💾 Отзывы сохранены: {reviews_file.name}\n")

        # Ответы
        logger.info("\n" + "=" * 50)
        logger.info("Шаг 2: Отправка ответов")
        logger.info("=" * 50 + "\n")

        replier = OzonReviewReplier(
            cookies_file=config['cookies_file'],
            company_id=config['company_id'],
            data_dir=config['data_dir'],
            drive_folder=config['drive_folder'],
            brand_name=config['brand_name'],
        )
        reply_stats = replier.reply_to_reviews(reviews_file)

        # Итоговая статистика
        logger.info("\n" + "=" * 50)
        logger.info("🎉 Полный цикл завершён!")
        logger.info("=" * 50)
        logger.info(f"📥 Собрано отзывов: {len(reviews)}")
        logger.info(f"✅ Отправлено ответов: {reply_stats['success']}")
        logger.info(f"❌ Ошибок: {reply_stats['failed']}")
        logger.info(f"⏭️  Пропущено: {reply_stats['skipped']}")
        logger.info("=" * 50 + "\n")

        return 0 if reply_stats["failed"] == 0 else 1

    elif marketplace.lower() in WB_ALIASES:
        config = get_account_config(account)

        # Сбор
        logger.info("=" * 50)
        logger.info(f"Шаг 1: Сбор неотвеченных отзывов WB ({config['display_name']})")
        logger.info("=" * 50 + "\n")

        collector = WBReviewCollector(
            token_file=config["wb_token_file"],
            data_dir=config["wb_data_dir"],
        )
        reviews = collector.collect_reviews()

        if not reviews:
            logger.info("⚠️  Нет новых отзывов для обработки\n")
            return 0

        reviews_file = collector.storage.save_reviews(reviews)
        logger.info(f"\n💾 Отзывы сохранены: {reviews_file.name}\n")

        # Ответы
        logger.info("\n" + "=" * 50)
        logger.info("Шаг 2: Отправка ответов")
        logger.info("=" * 50 + "\n")

        replier = WBReviewReplier(
            token_file=config["wb_token_file"],
            data_dir=config["wb_data_dir"],
            brand_name=config["wb_brand_name"],
            drive_folder=config["wb_drive_folder"],
        )
        reply_stats = replier.reply_to_reviews(reviews_file)

        logger.info("\n" + "=" * 50)
        logger.info("🎉 Полный цикл завершён!")
        logger.info("=" * 50)
        logger.info(f"📥 Собрано отзывов: {len(reviews)}")
        logger.info(f"✅ Отправлено ответов: {reply_stats['success']}")
        logger.info(f"❌ Ошибок: {reply_stats['failed']}")
        logger.info(f"⏭️  Пропущено: {reply_stats['skipped']}")
        logger.info("=" * 50 + "\n")

        return 0 if reply_stats["failed"] == 0 else 1

    else:
        logger.error(f"❌ Неизвестный маркетплейс: {marketplace}\n")
        logger.info("Доступные: ozon, wildberries\n")
        return 1


def cmd_status(account: str = None) -> None:
    """
    Показать статистику по собранным отзывам.

    Args:
        account: Название аккаунта (опционально, если не указан - показать для всех)
    """
    from config.accounts import get_all_accounts

    logger.info("📊 Статистика собранных отзывов\n")

    accounts_to_check = [account] if account else get_all_accounts()

    from shared.storage import JSONStorage

    def _print_marketplace_stats(label: str, data_dir: Path) -> None:
        review_files = sorted(data_dir.glob("reviews_*.json"), reverse=True)
        review_files = [f for f in review_files if "_temp_" not in f.name]

        logger.info(f"--- {label} ---")

        if not review_files:
            logger.info("⚠️  Нет собранных отзывов\n")
            return

        logger.info(f"Найдено файлов: {len(review_files)}\n")

        storage = JSONStorage(data_dir)
        for i, file in enumerate(review_files[:5], 1):
            reviews = storage.load_reviews(file)
            logger.info(f"{i}. {file.name}")
            logger.info(f"   Отзывов: {len(reviews)}")
            logger.info(f"   Размер: {file.stat().st_size / 1024:.1f} KB\n")

        if len(review_files) > 5:
            logger.info(f"... и ещё {len(review_files) - 5} файлов\n")

    for acc in accounts_to_check:
        try:
            config = get_account_config(acc)

            logger.info(f"{'=' * 60}")
            logger.info(f"  {config['display_name']}")
            logger.info(f"{'=' * 60}\n")

            _print_marketplace_stats("Ozon", config['data_dir'])
            _print_marketplace_stats("Wildberries", config['wb_data_dir'])

        except ValueError:
            logger.error(f"❌ Неизвестный аккаунт: {acc}\n")
            continue


def cmd_update_cookies(marketplace: str, account: str) -> int:
    """
    Обновить cookies.

    Args:
        marketplace: Название маркетплейса (ozon, wildberries)
        account: Название аккаунта (skazka, milky_garden, timeless)

    Returns:
        Код возврата (0 - успех, 1 - ошибка)
    """
    if marketplace.lower() in ["ozon", "озон"]:
        # Получаем конфигурацию аккаунта
        config = get_account_config(account)

        logger.info("=" * 60)
        logger.info(f"  Забираем cookies через CDP: {config['display_name']}")
        logger.info("=" * 60 + "\n")

        if _fetch_cookies_via_cdp(config):
            logger.info("=" * 60)
            logger.info("✅ Cookies успешно обновлены!")
            logger.info("=" * 60 + "\n")
            return 0
        else:
            return 1

    elif marketplace.lower() in WB_ALIASES:
        config = get_account_config(account)

        logger.info("=" * 60)
        logger.info(f"  Токены Wildberries: {config['display_name']}")
        logger.info("=" * 60 + "\n")
        logger.info("ℹ️  У Wildberries нет автообновления — токены API")
        logger.info("   создаются вручную и не протухают за один заход, как cookies Ozon.")
        logger.info("")
        logger.info("   1. Зайдите в кабинет WB → Настройки → Доступ к API")
        logger.info("   2. Создайте (или найдите) токен с категорией «Вопросы и отзывы»")
        logger.info(f"   3. Заполните {config['wb_token_file']}:")
        logger.info('      {"feedback_token": "..."}')
        logger.info("   Остатки для рекомендаций к 5★ отзывам берутся отдельно — из Google Drive")
        logger.info(f"   (папка Wildberries/{config['wb_drive_folder']}), токен для них не нужен.")
        logger.info("=" * 60 + "\n")
        return 0

    else:
        logger.error(f"❌ Неизвестный маркетплейс: {marketplace}\n")
        logger.info("Доступные: ozon, wildberries\n")
        return 1
