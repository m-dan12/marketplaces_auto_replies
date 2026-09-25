"""HTTP-клиент для работы с Feedbacks API Wildberries (отзывы)."""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from config.wb_config import (
    API_FEEDBACKS_ANSWER_ENDPOINT,
    API_FEEDBACKS_LIST_ENDPOINT,
    FEEDBACKS_BASE_URL,
    RATE_LIMIT_EXTRA_DELAY,
    RATE_LIMIT_RETRIES,
    REQUEST_TIMEOUT,
)
from shared.logger import logger


class WBAPIClient:
    """HTTP-клиент для Feedbacks API Wildberries."""

    def __init__(self, token_file: Path, user_agent: str = "ozon-reviews-wb/1.0"):
        """
        Инициализация клиента.

        Args:
            token_file: Путь к JSON-файлу с токеном ({"feedback_token": "..."})
            user_agent: User-Agent для запросов
        """
        self.token_file = token_file
        self.token = self._load_token()
        self.client = httpx.Client(timeout=REQUEST_TIMEOUT)
        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": user_agent,
        }
        self._last_request_ts = 0.0

    def _load_token(self) -> str:
        """
        Загрузка токена из файла.

        Returns:
            API-токен категории "Отзывы и вопросы"

        Raises:
            FileNotFoundError: Если файл с токеном не найден
            ValueError: Если токен не заполнен
        """
        if not self.token_file.exists():
            raise FileNotFoundError(
                f"Файл {self.token_file} не найден. "
                "Создайте его с ключом feedback_token "
                "(API-токен из личного кабинета Wildberries → Настройки → Доступ к API, "
                "категория «Вопросы и отзывы»)."
            )

        with open(self.token_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        token = (data.get("feedback_token") or "").strip()
        if not token:
            raise ValueError(f"В {self.token_file} не заполнен feedback_token.")

        return token

    def _respect_delay(self, min_delay: float) -> None:
        """Выдерживает минимальный интервал между запросами."""
        elapsed = time.monotonic() - self._last_request_ts
        if elapsed < min_delay:
            time.sleep(min_delay - elapsed)

    def _request(
        self,
        method: str,
        url: str,
        *,
        min_delay: float,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
    ) -> Any:
        """
        Выполняет запрос к Feedbacks API с защитой от лимита частоты запросов (429).

        Returns:
            Распарсенный JSON-ответ (или None для пустого тела)

        Raises:
            RuntimeError: При HTTP-ошибке или исчерпании попыток из-за 429
        """
        response: Optional[httpx.Response] = None

        for attempt in range(1, RATE_LIMIT_RETRIES + 1):
            self._respect_delay(min_delay)
            self._last_request_ts = time.monotonic()

            response = self.client.request(method, url, params=params, json=json_body, headers=self.headers)

            if response.status_code == 429:
                wait_sec = self._retry_delay(response, min_delay, attempt)
                logger.warning(
                    f"⚠️  WB API 429: лимит запросов. Пауза {wait_sec:.1f}с, "
                    f"попытка {attempt}/{RATE_LIMIT_RETRIES}"
                )
                if attempt == RATE_LIMIT_RETRIES:
                    break
                time.sleep(wait_sec)
                continue

            if response.status_code >= 400:
                raise RuntimeError(
                    f"WB API ERROR | HTTP {response.status_code} | {method} {url} | "
                    f"RESPONSE={response.text[:2000]}"
                )

            return response.json() if response.content else None

        raise RuntimeError(
            f"WB API RATE LIMIT | HTTP 429 после {RATE_LIMIT_RETRIES} попыток | {method} {url} | "
            f"RESPONSE={response.text[:2000] if response is not None else ''}"
        )

    @staticmethod
    def _retry_delay(response: httpx.Response, min_delay: float, attempt: int) -> float:
        """Вычисляет паузу перед повтором запроса после HTTP 429."""
        raw = response.headers.get("X-Ratelimit-Retry") or response.headers.get("Retry-After")
        try:
            header_delay = float(str(raw).replace(",", ".")) if raw else 0.0
        except ValueError:
            header_delay = 0.0

        if header_delay > 300:  # похоже на миллисекунды вместо секунд
            header_delay /= 1000.0

        fallback = max(min_delay, 2.0 * attempt)
        return max(header_delay, fallback) + RATE_LIMIT_EXTRA_DELAY

    def get_feedbacks(
        self,
        *,
        is_answered: bool,
        take: int,
        skip: int,
        date_from: int,
        date_to: int,
        min_delay: float,
        order: str = "dateDesc",
    ) -> Dict[str, Any]:
        """
        Получить страницу отзывов.

        Args:
            is_answered: Отвечены ли отзывы (False — только неотвеченные)
            take: Сколько отзывов запросить
            skip: Смещение
            date_from: Начало периода (unix timestamp)
            date_to: Конец периода (unix timestamp)
            min_delay: Минимальная задержка между запросами
            order: Порядок сортировки

        Returns:
            Сырой ответ API Wildberries
        """
        params = {
            "isAnswered": str(is_answered).lower(),
            "take": take,
            "skip": skip,
            "order": order,
            "dateFrom": date_from,
            "dateTo": date_to,
        }
        return self._request(
            "GET",
            f"{FEEDBACKS_BASE_URL}{API_FEEDBACKS_LIST_ENDPOINT}",
            min_delay=min_delay,
            params=params,
        )

    def answer_feedback(self, feedback_id: str, text: str, *, min_delay: float) -> None:
        """
        Отправить ответ на отзыв.

        Args:
            feedback_id: ID отзыва
            text: Текст ответа
            min_delay: Минимальная задержка между запросами
        """
        self._request(
            "POST",
            f"{FEEDBACKS_BASE_URL}{API_FEEDBACKS_ANSWER_ENDPOINT}",
            min_delay=min_delay,
            json_body={"id": feedback_id, "text": text},
        )
