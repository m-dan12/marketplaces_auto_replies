"""CLI - единая точка входа для автоматизации маркетплейсов."""

import sys

from cli.commands import (
    WB_ALIASES,
    cmd_collect,
    cmd_reply,
    cmd_auto,
    cmd_status,
    cmd_update_cookies,
)
from config.accounts import get_all_accounts, get_account_config
from shared.logger import logger

MARKETPLACE_ALIASES = ("ozon", "озон") + WB_ALIASES


def print_usage():
    """Показать справку по использованию."""
    logger.info("Использование:")
    logger.info("  python -m cli.main <command> <marketplace> --account <name>")
    logger.info("")
    logger.info("Команды:")
    logger.info("  collect <marketplace> --account <name>     - собрать отзывы")
    logger.info("  reply <marketplace> --account <name>       - отправить ответы")
    logger.info("  auto <marketplace> --account <name>        - полный цикл (Ozon: update + collect + reply; WB: collect + reply)")
    logger.info("  update-cookies <marketplace> --account <name> - обновить cookies Ozon через CDP")
    logger.info("  status [--account <name>]                  - показать статистику")
    logger.info("")
    logger.info("Опции:")
    logger.info("  --account <name>          - выбрать аккаунт (skazka, milky_garden, timeless)")
    logger.info("  --all-accounts            - выполнить для всех аккаунтов последовательно")
    logger.info("  --file <path>             - путь к файлу с отзывами (для reply)")
    logger.info("")
    logger.info("Маркетплейсы:")
    logger.info("  ozon                      - Ozon")
    logger.info("  wb / wildberries          - Wildberries")
    logger.info("")
    logger.info("Примеры:")
    logger.info("  python -m cli.main collect ozon --account skazka")
    logger.info("  python -m cli.main reply ozon --account milky_garden")
    logger.info("  python -m cli.main auto ozon --account timeless")
    logger.info("  python -m cli.main auto ozon --all-accounts  # update-cookies + collect + reply")
    logger.info("  python -m cli.main update-cookies ozon --account skazka")
    logger.info("  python -m cli.main collect wb --account skazka")
    logger.info("  python -m cli.main auto wb --all-accounts  # collect + reply")
    logger.info("  python -m cli.main status --account skazka")
    logger.info("  python -m cli.main status  # для всех аккаунтов")


def main():
    """Главная функция CLI."""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1].lower()

    # Команда status может работать без маркетплейса
    if command == "status":
        # Парсинг --account для status
        account = None
        for i in range(2, len(sys.argv)):
            if sys.argv[i] == "--account" and i + 1 < len(sys.argv):
                account = sys.argv[i + 1]

        cmd_status(account=account)
        sys.exit(0)

    # Остальные команды требуют маркетплейс
    if len(sys.argv) < 3:
        logger.error("❌ Не указан маркетплейс")
        print_usage()
        sys.exit(1)

    marketplace = sys.argv[2].lower()

    # Парсинг опций
    account = None
    reviews_file = None
    all_accounts = False

    for i in range(3, len(sys.argv)):
        if sys.argv[i] == "--account" and i + 1 < len(sys.argv):
            account = sys.argv[i + 1]
        elif sys.argv[i] == "--file" and i + 1 < len(sys.argv):
            reviews_file = sys.argv[i + 1]
        elif sys.argv[i] == "--all-accounts":
            all_accounts = True

    if account and all_accounts:
        logger.error("❌ Нельзя одновременно указать --account и --all-accounts")
        sys.exit(1)

    # Проверка обязательного параметра --account/--all-accounts для большинства команд
    if command != "status" and not account and not all_accounts:
        logger.error("❌ Не указан аккаунт. Используйте --account <name> или --all-accounts")
        logger.info(f"   Доступные аккаунты: {', '.join(get_all_accounts())}")
        print_usage()
        sys.exit(1)

    if marketplace not in MARKETPLACE_ALIASES:
        logger.error(f"❌ Неизвестный маркетплейс: {marketplace}")
        print_usage()
        sys.exit(1)

    command_by_name = {
        "collect": lambda acc: cmd_collect(marketplace, acc),
        "reply": lambda acc: cmd_reply(marketplace, acc, reviews_file),
        "auto": lambda acc: cmd_auto(marketplace, acc),
        "update-cookies": lambda acc: cmd_update_cookies(marketplace, acc),
    }

    if command not in command_by_name:
        logger.error(f"❌ Неизвестная команда: {command}")
        print_usage()
        sys.exit(1)

    def run_command_safe(acc: str) -> int:
        """Запускает команду для аккаунта, не давая исключению оборвать весь процесс."""
        try:
            return run_command(acc)
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}\n")
            if "cookies" in str(e).lower() or "авториз" in str(e).lower():
                logger.info(f"💡 Запустите: python -m cli.main update-cookies {marketplace} --account {acc}\n")
            return 1

    run_command = command_by_name[command]

    if all_accounts:
        accounts = get_all_accounts()
        results = {}

        for acc in accounts:
            display_name = get_account_config(acc)["display_name"]
            logger.info(f"\n{'#' * 60}")
            logger.info(f"# Аккаунт: {display_name}")
            logger.info(f"{'#' * 60}\n")
            results[acc] = run_command_safe(acc)

        logger.info(f"\n{'=' * 60}")
        logger.info("  Итог по всем аккаунтам")
        logger.info(f"{'=' * 60}")
        for acc, code in results.items():
            icon = "✅" if code == 0 else "❌"
            logger.info(f"  {icon} {get_account_config(acc)['display_name']}")

        sys.exit(0 if all(code == 0 for code in results.values()) else 1)
    else:
        sys.exit(run_command_safe(account))


if __name__ == "__main__":
    main()
