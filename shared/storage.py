"""Модуль для сохранения данных в JSON."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class JSONStorage:
    """Класс для работы с JSON файлами."""

    def __init__(self, data_dir: Path):
        """
        Инициализация хранилища.

        Args:
            data_dir: Директория для сохранения файлов
        """
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save_reviews(
        self,
        reviews: List[Dict[str, Any]],
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        temp: bool = False,
        page: Optional[int] = None,
    ) -> Path:
        """
        Сохранение отзывов в JSON.

        Args:
            reviews: Список отзывов
            date_from: Начальная дата периода
            date_to: Конечная дата периода
            temp: Временное сохранение (промежуточное)
            page: Номер страницы (для временных файлов)

        Returns:
            Путь к сохранённому файлу
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

        # Формирование имени файла
        if temp and page:
            filename = f"reviews_{timestamp}_temp_page{page}.json"
            filepath = self.data_dir / filename

            # Для временных файлов сохраняем просто список
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(reviews, f, ensure_ascii=False, indent=2)

            return filepath

        # Финальное сохранение с метаданными
        filename = f"reviews_{timestamp}.json"
        filepath = self.data_dir / filename

        # Удаление временных файлов
        for temp_file in self.data_dir.glob(f"reviews_{timestamp}_temp_*.json"):
            try:
                temp_file.unlink()
            except Exception:
                pass

        # Подготовка метаданных
        metadata: Dict[str, Any] = {
            "collected_at": datetime.now().isoformat(),
            "total_unanswered_reviews": len(reviews),
            "only_unanswered": True,
        }

        if date_from:
            metadata["period_from"] = date_from.isoformat()
        if date_to:
            metadata["period_to"] = date_to.isoformat()

        data = {
            "metadata": metadata,
            "reviews": reviews,
        }

        # Сохранение в файл
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return filepath

    def load_reviews(self, filepath: Path) -> List[Dict[str, Any]]:
        """
        Загрузка отзывов из JSON файла.

        Args:
            filepath: Путь к файлу

        Returns:
            Список отзывов
        """
        if not filepath.exists():
            return []

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Если это файл с метаданными
        if isinstance(data, dict) and "reviews" in data:
            return data["reviews"]

        # Если это просто список отзывов
        if isinstance(data, list):
            return data

        return []

    def load_all_review_files(self) -> List[Path]:
        """
        Получить список всех файлов с отзывами.

        Returns:
            Список путей к файлам
        """
        review_files = sorted(self.data_dir.glob("reviews_*.json"), reverse=True)

        # Исключаем временные файлы
        review_files = [f for f in review_files if "_temp_" not in f.name]

        return review_files
