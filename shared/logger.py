"""Логгер для консольного вывода."""

import sys


class Logger:
    """Простой логгер с цветным выводом."""

    def __init__(self):
        """Инициализация с настройкой UTF-8 кодировки для Windows."""
        # Для Windows консоли включаем UTF-8 режим
        if sys.platform == "win32":
            try:
                # Переключаем stdout/stderr на UTF-8
                sys.stdout.reconfigure(encoding="utf-8")
                sys.stderr.reconfigure(encoding="utf-8")
            except AttributeError:
                # Python < 3.7 не поддерживает reconfigure
                pass

    def info(self, message: str, end: str = "\n") -> None:
        """Информационное сообщение."""
        try:
            print(message, end=end, flush=True)
        except UnicodeEncodeError:
            # Fallback: удаляем эмодзи если консоль их не поддерживает
            print(self._strip_emoji(message), end=end, flush=True)

    def success(self, message: str, end: str = "\n") -> None:
        """Успешное выполнение."""
        try:
            print(message, end=end, flush=True)
        except UnicodeEncodeError:
            print(self._strip_emoji(message), end=end, flush=True)

    def warning(self, message: str) -> None:
        """Предупреждение."""
        try:
            print(message, flush=True)
        except UnicodeEncodeError:
            print(self._strip_emoji(message), flush=True)

    def error(self, message: str) -> None:
        """Ошибка."""
        try:
            print(message, flush=True)
        except UnicodeEncodeError:
            print(self._strip_emoji(message), flush=True)

    def debug(self, message: str) -> None:
        """Отладочное сообщение (пока просто print)."""
        # В будущем можно добавить уровни логирования
        pass

    @staticmethod
    def _strip_emoji(text: str) -> str:
        """
        Удалить эмодзи из текста (fallback для старых консолей).

        Args:
            text: Исходный текст

        Returns:
            Текст без эмодзи
        """
        # Простая замена популярных эмодзи
        replacements = {
            "🔍": "[SEARCH]",
            "📄": "[PAGE]",
            "✅": "[OK]",
            "❌": "[ERROR]",
            "⚠️": "[WARNING]",
            "💾": "[SAVE]",
            "📊": "[STATS]",
            "📁": "[FILE]",
            "🎯": "[TARGET]",
            "🚀": "[START]",
            "🌐": "[WEB]",
            "🔐": "[AUTH]",
            "👤": "[USER]",
            "🍪": "[COOKIE]",
            "⏳": "[WAIT]",
        }

        result = text
        for emoji, replacement in replacements.items():
            result = result.replace(emoji, replacement)

        return result


# Глобальный экземпляр
logger = Logger()
