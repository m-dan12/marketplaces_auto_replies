# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Автоматизированная система для работы с отзывами Ozon и Wildberries:
1. **Сбор неотвеченных отзывов** — через внутренний API фронтенда seller.ozon.ru (Ozon)
   и Seller API Wildberries (feedbacks-api.wildberries.ru)
2. **Умная отправка ответов** с алгоритмом рекомендаций похожих товаров для 5★ отзывов —
   свой на каждый маркетплейс, но по общей логике (`shared/review_heuristics.py`,
   `shared/article_parsing.py`)
3. **CLI-интерфейс** для управления всем процессом

## Commands

### Install dependencies
```bash
pip install -r requirements.txt
```

### CLI Commands

**Поддержка нескольких аккаунтов:**
Система поддерживает работу с тремя аккаунтами одновременно (у каждого свой кабинет
и на Ozon, и на Wildberries): `skazka`, `milky_garden`, `timeless`.

```bash
# Обновить cookies Ozon через CDP (требует заранее залогиненного профиля Chrome, см. Authentication)
# Обычно не требуется отдельно - происходит автоматически в команде auto
python -m cli.main update-cookies ozon --account skazka

# Собрать неотвеченные отзывы для конкретного аккаунта
python -m cli.main collect ozon --account milky_garden
python -m cli.main collect wb --account milky_garden

# Отправить ответы (последний файл с отзывами)
python -m cli.main reply ozon --account timeless
python -m cli.main reply wb --account timeless

# Отправить ответы из конкретного файла
python -m cli.main reply ozon --account skazka --file data/skazka/reviews_2024-01-15_10-30.json

# Полный цикл (для Ozon: update-cookies → collect → reply; для WB: collect → reply)
python -m cli.main auto ozon --account milky_garden
python -m cli.main auto wb --account milky_garden

# То же самое сразу для всех трёх аккаунтов
python -m cli.main auto ozon --all-accounts
python -m cli.main auto wb --all-accounts

# Статистика по собранным отзывам (Ozon + WB, для всех аккаунтов)
python -m cli.main status

# Статистика для конкретного аккаунта
python -m cli.main status --account skazka
```

**Важно:** Параметр `--account` (или `--all-accounts`) обязателен для всех команд кроме `status`.
Маркетплейс — второй позиционный аргумент: `ozon` или `wb`/`wildberries`.

### Test imports
```bash
python -c "from shared.drive_stocks_client import load_stocks_from_drive, load_wb_stocks_from_drive; from shared.recommendations import generate_reply_text; print('OK')"
python -c "from marketplaces.wb.api_client import WBAPIClient; from marketplaces.wb.replier import WBReviewReplier; print('OK')"
python -c "from shared.llm_client import generate_issue_reply; print('OK')"
```

## Architecture

### Module Structure
```
├── cli/                          # CLI-интерфейс
│   ├── main.py                   # Точка входа
│   └── commands.py               # Команды (collect, reply, auto, status, update-cookies)
├── marketplaces/
│   ├── ozon/
│   │   ├── collector.py          # Сбор отзывов (OzonReviewCollector)
│   │   ├── replier.py            # Отправка ответов (OzonReviewReplier)
│   │   ├── api_client.py         # HTTP-клиент API
│   │   ├── cdp_cookie_fetcher.py # Получение cookies через Chrome DevTools Protocol
│   │   └── history_analyzer.py   # Анализ истории отзывов
│   └── wb/
│       ├── collector.py          # Сбор отзывов (WBReviewCollector)
│       ├── replier.py            # Отправка ответов (WBReviewReplier) — использует общий shared/recommendations.py
│       └── api_client.py         # HTTP-клиент Feedbacks API (список/ответ на отзывы)
├── config/
│   ├── accounts.py               # Конфигурация аккаунтов (skazka, milky_garden, timeless;
│   │                             #   sub_brands — доп. бренды внутри кабинета, см. resolve_sub_brand)
│   ├── ozon_config.py            # Конфигурация Ozon API
│   ├── wb_config.py              # Конфигурация Wildberries Feedbacks API
│   ├── llm_config.py             # Конфигурация GigaChat (см. shared/llm_client.py)
│   └── templates.py              # Шаблоны ответов (Ozon и WB)
├── shared/
│   ├── storage.py                # Работа с JSON
│   ├── logger.py                 # Логирование
│   ├── article_parsing.py        # Разбор артикула "PT140/0-0-56/1" (общий Ozon+WB);
│   │                             #   resolve_sub_brand — подпись бренда по префиксу дизайна
│   ├── review_heuristics.py      # Детект негатива в 5★ и категорий проблем в 1-4★ (общий Ozon+WB)
│   ├── drive_stocks_client.py    # Получение остатков из Google Drive (Ozon и WB — разные форматы файла)
│   ├── recommendations.py        # Алгоритм рекомендаций товаров — общий для Ozon и WB
│   └── llm_client.py             # Адресный ответ на 1-4★ с явной проблемой через GigaChat
├── cookies/                      # Cookies/токены по аккаунтам (не в git)
│   ├── skazka_cookies.json          # Ozon
│   ├── milky_garden_cookies.json    # Ozon
│   ├── timeless_cookies.json        # Ozon
│   ├── skazka_wb_token.json         # Wildberries (feedback_token — только для отзывов)
│   ├── milky_garden_wb_token.json   # Wildberries
│   └── timeless_wb_token.json       # Wildberries
├── drive_service_account.json    # Сервисный аккаунт Google Drive (не в git)
└── russian_trusted_root_ca.pem   # Сертификат НУЦ Минцифры для TLS к api.gigachat (публичный, в git)
```

### Smart Reply Algorithm (для 5★ отзывов)

**Цель:** Рекомендовать покупателю похожие товары из ассортимента, которые есть в наличии.

**Принцип работы:**
1. **Парсинг артикула** из отзыва (offer_id вида `PT140/0-0-56/1`)
   - Дизайн: `PT140` (первая часть до `/`)
   - Размеры: `0-0-56` (средняя часть)
   - Вариант: `1` (последняя цифра)

2. **Поиск похожих товаров:**
   - **Дизайн-группа:** Другие варианты того же дизайна (`PT140/*/` с разными размерами/вариантами)
   - **Размер-группа:** Тот же размер на других дизайнах (`*/0-0-56/*`)
   - Приоритет: дизайн-группа > размер-группа

3. **Фильтрация по остаткам:**
   - Загружаются актуальные остатки из Google Drive файла "Остатки.xlsx"
   - Папка на Drive зависит от аккаунта (`drive_folder` в `config/accounts.py`):
     - `skazka` → "Выгрузка авто" / Ozon / "Кабинет 1 (Профтекс)" / Остатки.xlsx
     - `milky_garden` → "Выгрузка авто" / Ozon / "Кабинет 3 (Milky Garden)" / Остатки.xlsx
     - `timeless` → "Выгрузка авто" / Ozon / "Кабинет 2 (Timeless)" / Остатки.xlsx
   - Используется сервисный аккаунт (drive_service_account.json)
   - Рекомендуются только товары с остатками > 0

4. **Генерация текста ответа:**
   - Благодарность за отзыв
   - Персонализированный список рекомендаций (до 8 товаров)
   - Размер каждой рекомендации расшифровывается в человекочитаемый вид через
     `config/size_descriptions.json` (`article_key -> "180х200см, борт 26см, евро"` и т.п.);
     если для ключа нет описания — используется сырой `article_key` как fallback
     (`shared.recommendations.load_size_descriptions`)
   - Подпись бренда — берётся из `brand_name` аккаунта в `config/accounts.py`
     (например «МилкиГарден», «Сказка», «Timeless»)

**Fallback:** Если не удалось загрузить остатки / найти рекомендации — используются стандартные шаблоны из `config/templates.py`.

**Отменённые заказы:** Если отзыв с оценкой 4-5★ оставлен на отменённый заказ
(`orderDeliveryType == "REVIEW_ORDER_DELIVERY_CANCELED"`, например покупатель "нашёл дешевле"),
рекомендации и советы по уходу не показываются — используется отдельный короткий шаблон
благодарности `OZON_CANCELED_ORDER_HIGH_RATING_TEMPLATES` (`config/templates.py`).
Для 1-3★ отменённые заказы обрабатываются как обычно.

### Smart Reply Algorithm для Wildberries (5★)

**Использует тот же движок, что и Ozon** — `shared/recommendations.py` (тот же
`load_product_cards`/`build_offer_index`/`find_recommendations`/`generate_reply_text`,
та же логика групп и парсинг артикула). Отличается только источник остатков и подпись:

1. **Остатки — тоже из Google Drive**, но из отдельной папки `Wildberries/<кабинет>`
   (`wb_drive_folder` в `config/accounts.py`; нумерация кабинетов на WB **не совпадает**
   с Ozon — см. значения в `config/accounts.py`). Файл там тоже называется `Остатки.xlsx`,
   но это собственная выгрузка WB с другими колонками: `nmId`, `vendorCode` и суммарный
   остаток по всем складам в колонке `"Всего находится на складах"`
   (`shared.drive_stocks_client.load_wb_stocks_from_drive` -> `_parse_wb_stocks_xlsx`).
   `nmId` играет роль `product_id`, `vendorCode` — роль `offer_id`.
2. **Подпись рекомендаций** — `generate_reply_text(..., marketplace_label="WB")` даёт
   `(арт. WB {nm_id})` вместо `(арт. Ozon {product_id})`.

Fallback при негативе/отсутствии остатков — те же `STANDARD_5STAR_REPLY_VARIANTS`
(`shared/review_heuristics.py`; `WB_REPLY_TEMPLATES[5]` в `config/templates.py`
ссылается на тот же список, что и `OZON_REPLY_TEMPLATES[5]`).

**Важно про поиск файла на Drive:** папки кабинетов называются одинаково под Ozon и
Wildberries (например, `"Кабинет 1 (...)"`), поэтому `DriveStocksClient` разрешает
`target_folder` по цепочке родителей: `<grandparent_folder>/<target_folder>/Остатки.xlsx`,
где `grandparent_folder` — `"Ozon"` или `"Wildberries"`. Без этого второго уровня поиск
по одному имени папки — неоднозначен.

### Адресные ответы на 1-4★ через GigaChat (shared/llm_client.py)

**Цель:** для 1-4★ отзывов с явной, узнаваемой проблемой в тексте — сгенерировать
ответ, адресованный именно этой проблеме, а не общий шаблон.

1. **Детект проблемы** — `shared.review_heuristics.detect_review_issue(text)` по
   ключевым словам определяет категорию: `size_mismatch`, `fabric_quality`, `defect`,
   `color_mismatch`, `wrong_item`, или `general_negative` (общий негатив без конкретики,
   не считается "явной нестыковкой"). Тот же список категорий (`_ISSUE_PATTERNS`)
   используется и для детекта скрытого негатива в 5★ (`looks_negative_5star`) — единый
   источник правды вместо двух раздельных списков стоп-слов.
2. **Вызов LLM** — только если категория есть в `ISSUE_LABELS` (т.е. не
   `general_negative`): `shared.llm_client.generate_issue_reply(rating, review_text,
   issue_category, brand_name)` формирует промпт и зовёт GigaChat
   (`GigaChat-2`/Lite, SDK `gigachat`).
3. **Graceful degradation** — любая ошибка (нет ключа, таймаут, лимит) → `None` →
   вызывающая сторона (`replier.py`) падает обратно на фиксированный шаблон
   (`config/templates.py`), как и раньше.
4. **Аутентификация** — `GIGACHAT_CREDENTIALS` в `.env` (Authorization key с
   developers.sber.ru, это уже `base64(client_id:client_secret)` — SDK сам обменивает
   его на access-token и обновляет каждые 30 минут).
5. **TLS-сертификат** — GigaChat API использует сертификат НУЦ Минцифры, не входящий
   в стандартные доверенные корни. Вместо отключения проверки (`verify_ssl_certs=False`)
   используется настоящий сертификат — `russian_trusted_root_ca.pem` в корне проекта
   (публичный файл, скачан с gu-st.ru, безопасно хранить в git).
6. **Почему GigaChat, а не Gemini:** Free Tier Gemini на флагманской модели —
   20 запросов/день, и модель тратит 200-700 токенов на скрытые "размышления" перед
   ответом. GigaChat-2 даёт 250 млн бесплатных токенов на 12 месяцев, без "размышлений"
   и быстрее — для короткого адресного ответа этого более чем достаточно. Проверено
   эмпирически 2026-09-25.

### Core Flow: Collect Reviews

1. **history_analyzer.py** - определение периода сбора (с последнего отвеченного отзыва)
2. **api_client.py** - запросы к `POST /api/v4/review/list` с пагинацией
3. **collector.py** - оркестрация процесса, инкрементальное сохранение каждые 5 страниц
4. **storage.py** - сохранение в `data/reviews_YYYY-MM-DD_HH-MM.json`

(Cookies собираются отдельной командой `update-cookies` — см. Authentication ниже.)

### Core Flow: Reply to Reviews

1. **replier.py** - загрузка файла с неотвеченными отзывами
2. **shared/drive_stocks_client.py** - загрузка остатков из Google Drive файла "Остатки.xlsx"
3. **shared/recommendations.py** - для каждого 5★ отзыва:
   - Парсинг артикула из `product_id`
   - Поиск похожих товаров в наличии
   - Генерация персонализированного ответа
4. **api_client.py** - отправка ответа через `POST /api/review/reply`
5. Для 1-4★ отзывов используются фиксированные шаблоны

### Core Flow: Wildberries (Collect + Reply)

1. **collector.py** - `GET /api/v1/feedbacks?isAnswered=false`, пагинация по `skip`/`take`
   (сам WB фильтрует неотвеченные — доп. анализ истории, как у Ozon, не нужен)
2. **storage.py** - сохранение в `data/<account>/wb/reviews_YYYY-MM-DD_HH-MM.json`
   (тот же формат/класс `JSONStorage`, что у Ozon)
3. **replier.py** - при инициализации грузит остатки через
   `shared.drive_stocks_client.load_wb_stocks_from_drive`, дальше — общий `shared/recommendations.py`
   (секунды, не минуты — тот же путь, что у Ozon)
4. **shared/recommendations.py** (общий с Ozon) - для каждого 5★ отзыва: парсинг артикула
   из `supplierArticle`, поиск похожих товаров в наличии, генерация ответа
5. **api_client.py** - отправка через `POST /api/v1/feedbacks/answer`
6. Для 1-4★ отзывов — фиксированные шаблоны `WB_REPLY_TEMPLATES` (`config/templates.py`)

### API Integration

**Сбор отзывов:** `POST https://seller.ozon.ru/api/v4/review/list`
- Требует cookies из `cookies/<account>_cookies.json`
- Заголовки: `x-o3-company-id` (свой на каждый аккаунт), `x-o3-app-name`, Origin, Referer

**Отправка ответов:** `POST https://seller.ozon.ru/api/review/comment/create`
- Payload: `{"company_id": "...", "company_type": "seller", "text": "...", "review_uuid": "..."}`
- Требует те же cookies и заголовки

**Получение остатков Ozon:** Google Drive API
- Файл: "Выгрузка авто" / Ozon / `<drive_folder аккаунта>` / Остатки.xlsx
  (см. `drive_folder` в `config/accounts.py` — своя папка на каждый аккаунт)
- Формат: колонки `offer_id`, `sku` (колонка F — реальный артикул Ozon для ссылки/поиска
  товара; устаревшая `product_id` поддерживается как legacy-фолбэк, если `sku` в файле нет),
  `present`
- Авторизация через сервисный аккаунт (`drive_service_account.json`)

**Wildberries — сбор отзывов:** `GET https://feedbacks-api.wildberries.ru/api/v1/feedbacks`
- Требует `feedback_token` из `cookies/<account>_wb_token.json`

**Wildberries — отправка ответов:** `POST https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer`
- Payload: `{"id": "...", "text": "..."}`
- Требует тот же `feedback_token`

**Получение остатков Wildberries:** Google Drive API (тот же сервисный аккаунт, что у Ozon)
- Файл: "Выгрузка авто" / Wildberries / `<wb_drive_folder аккаунта>` / Остатки.xlsx
  (см. `wb_drive_folder` в `config/accounts.py` — своя папка и нумерация, отличная от Ozon)
- Формат: колонки `nmId`, `vendorCode`, `"Всего находится на складах"` (+ колонки по складам)

### Authentication

**Cookies (для seller.ozon.ru), отдельно на каждый аккаунт:**
- **Через CDP (Chrome DevTools Protocol), основной способ:**
  - Один раз вручную: запустить Chrome как обычный процесс с `--user-data-dir` и
    `--remote-debugging-port` своими для каждого аккаунта (см. `cdp_profile_dir`,
    `cdp_port` в `config/accounts.py`; профили лежат вне репозитория, в `C:\ChromeProfiles\<account>`)
    и войти в нужный кабинет seller.ozon.ru руками
  - Дальше: `python -m cli.main update-cookies ozon --account <name>` — сам запускает Chrome
    с этим же профилем и портом, забирает cookies ozon.ru через CDP-команду
    `Network.getAllCookies` (`marketplaces/ozon/cdp_cookie_fetcher.py`) и закрывает Chrome —
    без участия человека, пока сессия в профиле остаётся живой
  - Также используется в `auto ozon --account <name> --from-browser` как шаг 0 перед сбором
- **Ручное обновление (legacy):**
  - DevTools → Network → скопировать Cookie → вставить в `cookies/<account>_cookies.json`
- Формат: `{"cookies": "abt_data=...; access_token=..."}`
- **Важно — access-token живёт недолго (порядка часа):** `update-cookies` нужно запускать
  непосредственно перед `collect`/`reply`/`auto`, а не заранее «про запас».

**API-токен Wildberries (для отзывов), отдельно на каждый аккаунт:**
- Создаётся вручную в кабинете WB → Настройки → Доступ к API, категория «Вопросы и отзывы»
  (автообновления для WB нет — токен долгоживущий, в отличие от cookies Ozon)
- Хранится в `cookies/<account>_wb_token.json`: `{"feedback_token": "..."}`
- Подсказка с инструкцией: `python -m cli.main update-cookies wb --account <name>`

**Google Drive (для получения остатков и Ozon, и Wildberries):**
- Сервисный аккаунт: `drive_service_account.json` (общий для всех аккаунтов и обоих маркетплейсов)
- Доступ к папкам "Выгрузка авто" / Ozon / "Кабинет 1 (Профтекс)", "Кабинет 2 (Timeless)", "Кабинет 3 (Milky Garden)"
- Доступ к папкам "Выгрузка авто" / Wildberries / "Кабинет 1 (Сказка)", "Кабинет 2 (Milky Garden)", "Кабинет 3 (Timeless)"
  (нумерация кабинетов здесь своя, не совпадает с Ozon)

**GigaChat (для адресных ответов на 1-4★, см. `shared/llm_client.py`), общий для всех аккаунтов:**
- `GIGACHAT_CREDENTIALS` в `.env` — Authorization key с developers.sber.ru
  (Freemium: 250 млн бесплатных токенов на 12 месяцев для GigaChat-2/Lite)
- TLS: `russian_trusted_root_ca.pem` в корне проекта (публичный сертификат НУЦ
  Минцифры, безопасно хранить в git — не секрет)
- Graceful degradation: без ключа или при ошибке API — просто фиксированный шаблон,
  ничего не ломается

## Code Conventions

- Type hints обязательны для всех функций
- Docstrings в формате Google Style для классов и публичных методов
- Использовать Path вместо строк для путей к файлам
- httpx предпочтительнее requests
- Консольный вывод с эмодзи для UX (🔍 📄 ✅ ❌ ⚠️ 💾 📊 📁 🎯 🚀)
- Сохранять полные объекты отзывов как есть (не модифицировать структуру API)

## Project Constraints

- **Не добавлять** async/await - скрипт однопоточный и простой
- **Не добавлять** базы данных - JSON достаточно для цели проекта
- **Не менять** структуру ответа API в сохранённых файлах
- **Сохранять** обратную совместимость формата metadata при изменениях
- **Graceful degradation** - если алгоритм рекомендаций не работает, fallback на шаблоны
