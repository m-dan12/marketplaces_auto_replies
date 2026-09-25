# Ozon Reviews - Мультиаккаунтная система автоответов

Автоматизированная система для работы с отзывами Ozon с поддержкой нескольких аккаунтов.

## Поддерживаемые аккаунты

- **Сказка** (`skazka`)
- **Milky Garden** (`milky_garden`)
- **Timeless** (`timeless`)

## Установка

```bash
pip install -r requirements.txt
```

## Быстрый старт

### 1. Обновление cookies для аккаунта

Один раз на каждый аккаунт: запустите Chrome с его профилем и портом (см.
`config/accounts.py`: `cdp_profile_dir`, `cdp_port`) и войдите в нужный кабинет
seller.ozon.ru руками. Пример для Milky Garden (PowerShell):

```powershell
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList '--user-data-dir="C:\ChromeProfiles\milky_garden" --remote-debugging-port=9223 --remote-allow-origins=* --no-first-run --no-default-browser-check'
```

Дальше cookies обновляются командой (без участия человека, пока сессия в профиле жива):

```bash
python -m cli.main update-cookies ozon --account skazka
python -m cli.main update-cookies ozon --account milky_garden
python -m cli.main update-cookies ozon --account timeless
```

### 2. Полный цикл (обновить cookies + сбор + ответы)

```bash
# Один аккаунт (для Ozon: update-cookies → collect → reply)
python -m cli.main auto ozon --account skazka

# Все аккаунты последовательно
python -m cli.main auto ozon --all-accounts

# Для Wildberries (только collect → reply, без update-cookies)
python -m cli.main auto wb --account skazka
python -m cli.main auto wb --all-accounts
```

### 3. Сбор отзывов (без отправки ответов)

```bash
python -m cli.main collect ozon --account milky_garden
```

### 4. Отправка ответов (на последний собранный файл)

```bash
python -m cli.main reply ozon --account timeless
```

## Команды

### Основные команды

```bash
# Полный цикл (для Ozon: update-cookies → collect → reply; для WB: collect → reply)
python -m cli.main auto ozon --account <name>
python -m cli.main auto wb --account <name>

# Только сбор отзывов
python -m cli.main collect ozon --account <name>
python -m cli.main collect wb --account <name>

# Только отправка ответов
python -m cli.main reply ozon --account <name>
python -m cli.main reply wb --account <name>

# Обновить cookies через браузер (только Ozon)
python -m cli.main update-cookies ozon --account <name>

# Статистика
python -m cli.main status
```

### Опции

- `--account <name>` - выбрать аккаунт (skazka, milky_garden, timeless)
- `--all-accounts` - выполнить команду для всех аккаунтов последовательно

### Примеры

```bash
# Обновить cookies (ручное обновление, обычно не требуется - происходит автоматически в auto)
python -m cli.main update-cookies ozon --account skazka

# Автоматический цикл для всех аккаунтов (update-cookies + collect + reply)
python -m cli.main auto ozon --all-accounts

# Автоматический цикл для Wildberries (collect + reply)
python -m cli.main auto wb --all-accounts

# Собрать отзывы для одного аккаунта
python -m cli.main collect ozon --account skazka

# Отправить ответы
python -m cli.main reply ozon --account skazka
```

## Структура проекта

```
├── cli/                          # CLI-интерфейс
│   └── main.py                   # Точка входа с мультиаккаунтами
├── config/
│   └── accounts.py               # Конфигурация аккаунтов (в т.ч. cdp_profile_dir, cdp_port)
├── marketplaces/ozon/
│   ├── collector.py              # Сбор отзывов
│   ├── replier.py                # Отправка ответов
│   └── cdp_cookie_fetcher.py     # Получение cookies через Chrome DevTools Protocol
├── cookies/                      # Cookies для каждого аккаунта
│   ├── skazka_cookies.json
│   ├── milky_garden_cookies.json
│   └── timeless_cookies.json
└── data/                         # Данные по аккаунтам
    ├── skazka/
    ├── milky_garden/
    └── timeless/
```

Профили Chrome для получения cookies (`C:\ChromeProfiles\<account>`) намеренно лежат
вне проекта — создаются один раз вручную и живут независимо от кода.

## Как работает получение cookies

1. **Один раз на аккаунт:** вручную запускаете Chrome с его профилем и портом
   (`--user-data-dir`, `--remote-debugging-port` — см. выше) и входите в кабинет.
2. **При каждом обновлении:** `update-cookies` сам запускает Chrome с этим же
   профилем и портом, забирает cookies ozon.ru через CDP (`Network.getAllCookies`)
   и закрывает Chrome — без участия человека, пока сессия в профиле остаётся живой.
3. **Параметр `--account` обязателен** для всех команд кроме `status` (для нескольких аккаунтов сразу
   используйте `--all-accounts` вместо перечисления).

## Алгоритм умных ответов (5★ отзывы)

Для 5-звёздочных отзывов система автоматически рекомендует похожие товары:

1. Парсит артикул из отзыва (формат: `PT140/0-0-56/1`)
2. Ищет похожие товары по дизайну и размеру
3. Фильтрует по остаткам из Google Drive ("Остатки.xlsx")
4. Генерирует персонализированный ответ с рекомендациями

## Troubleshooting

### Cookies протухли

```bash
python -m cli.main update-cookies ozon --account <name>
```

### "Профиль браузера не найден" / "Нет открытых вкладок на порту"

Профиль `C:\ChromeProfiles\<account>` ещё не создан — запустите Chrome с этим
профилем и портом вручную (см. "Обновление cookies для аккаунта" выше) и войдите в кабинет.

### Не работает для конкретного аккаунта

Убедитесь, что вы всё ещё залогинены в правильный кабинет в профиле
`C:\ChromeProfiles\<account>` (запустите Chrome с этим профилем и портом и проверьте
глазами), затем повторите `update-cookies`.

## License

MIT
