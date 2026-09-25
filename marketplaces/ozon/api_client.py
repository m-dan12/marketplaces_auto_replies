"""HTTP-клиент для работы с Ozon API."""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from config.ozon_config import (
    API_BASE_URL,
    HEADERS,
    RETRY_COUNT,
    RETRY_DELAY,
)
from shared.logger import logger


class OzonAPIClient:
    """HTTP-клиент для Ozon Seller API."""

    def __init__(self, cookies_file: Path, company_id: str):
        """
        Инициализация клиента.

        Args:
            cookies_file: Путь к файлу с cookies
            company_id: ID компании в Ozon
        """
        self.base_url = API_BASE_URL
        self.cookies_file = cookies_file
        self.company_id = company_id
        self.cookie_string = self._load_cookies()
        self.headers = self._prepare_headers()

    def _load_cookies(self) -> str:
        """
        Загрузка cookies из файла.

        Returns:
            Строка с cookies

        Raises:
            FileNotFoundError: Если файл cookies не найден
            ValueError: Если cookies не заполнены
        """
        if not self.cookies_file.exists():
            raise FileNotFoundError(
                f"Файл {self.cookies_file} не найден. "
                "Создайте его и вставьте cookies из браузера."
            )

        with open(self.cookies_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Поддержка обоих форматов: "cookie" и "cookies"
        cookie = data.get("cookies", data.get("cookie", "")).strip()
        if not cookie or cookie == "вставьте_сюда_полную_строку_Cookie_из_DevTools":
            raise ValueError(
                f"Cookies не заполнены в {self.cookies_file}. "
                "Скопируйте полную строку Cookie из DevTools браузера."
            )

        return cookie

    def _prepare_headers(self) -> Dict[str, str]:
        """
        Подготовка заголовков с cookies.

        Returns:
            Словарь заголовков
        """
        headers = HEADERS.copy()
        headers["Cookie"] = self.cookie_string
        headers["x-o3-company-id"] = self.company_id
        return headers

    def make_request(
        self, endpoint: str, payload: Dict[str, Any], retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Выполнение HTTP-запроса к API с обработкой ошибок.

        Args:
            endpoint: Эндпоинт API (например, /review/list)
            payload: Тело запроса
            retry_count: Номер текущей попытки

        Returns:
            Ответ API в виде словаря

        Raises:
            Exception: При ошибках авторизации или исчерпании попыток
        """
        url = f"{self.base_url}{endpoint}"

        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.post(url, json=payload, headers=self.headers)

                # Проверка на ошибки авторизации
                if response.status_code in (401, 403):
                    if response.headers.get("ozon-antibot") == "1":
                        raise Exception(
                            "❌ Запрос заблокирован антибот-защитой Ozon (заголовок ozon-antibot: 1), "
                            "а не протухшими cookies. Это НЕ решается обновлением cookies — "
                            "JS-челлендж проходит только настоящий браузер. Скорее всего, сработал "
                            "rate-limit из-за большого числа запросов подряд. Подождите и попробуйте позже."
                        )
                    raise Exception(
                        "❌ Ошибка авторизации! Cookies протухли или невалидны.\n"
                        f"Обновите cookies в файле {self.cookies_file}.\n"
                        "Как получить cookies:\n"
                        "1. Откройте seller.ozon.ru в браузере\n"
                        "2. Нажмите F12 → вкладка Network\n"
                        "3. Обновите страницу\n"
                        "4. Найдите любой запрос к seller.ozon.ru\n"
                        "5. Скопируйте значение заголовка Cookie целиком"
                    )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            if retry_count < RETRY_COUNT:
                logger.warning(
                    f"⚠️  Ошибка HTTP {e.response.status_code}. "
                    f"Повторная попытка {retry_count + 1}/{RETRY_COUNT}..."
                )
                time.sleep(RETRY_DELAY)
                return self.make_request(endpoint, payload, retry_count + 1)
            raise Exception(f"Ошибка HTTP после {RETRY_COUNT} попыток: {e}")

        except httpx.RequestError as e:
            if retry_count < RETRY_COUNT:
                logger.warning(
                    f"⚠️  Ошибка сети: {e}. "
                    f"Повторная попытка {retry_count + 1}/{RETRY_COUNT}..."
                )
                time.sleep(RETRY_DELAY)
                return self.make_request(endpoint, payload, retry_count + 1)
            raise Exception(f"Ошибка сети после {RETRY_COUNT} попыток: {e}")

    def send_reply(self, review_uuid: str, reply_text: str) -> bool:
        """
        Отправить ответ на отзыв.

        Args:
            review_uuid: UUID отзыва
            reply_text: Текст ответа

        Returns:
            True если успешно отправлено
        """
        from config.ozon_config import API_REPLY_ENDPOINT

        payload = {
            "company_id": self.company_id,
            "company_type": "seller",
            "text": reply_text,
            "review_uuid": review_uuid,
        }

        try:
            response = self.make_request(API_REPLY_ENDPOINT, payload)
            # Проверяем успешность
            return response is not None
        except Exception as e:
            logger.error(f"Ошибка при отправке ответа: {e}")
            return False
