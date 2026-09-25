"""Получение cookies через Chrome DevTools Protocol (CDP) — без Selenium/chromedriver.

Ozon помечает антиботом сессии, залогиненные через Selenium/chromedriver: сервер видит
признаки автоматизации (WebDriver-флаги и т.п.) в момент логина и клеймит выданный
токен — даже при полностью честном входе. Дальше любой запрос с этим токеном (хоть из
браузера, хоть из httpx) попадает под антибот-проверку. Проверено эмпирически 2026-09-24.

Chrome, запущенный напрямую (`--remote-debugging-port`, без chromedriver), этих флагов
не выставляет. Вход в аккаунт делает человек сам, один раз, в обычном окне Chrome — а
код здесь только читает cookies уже существующей сессии через сырой CDP-протокол.
Само чтение cookies не обращается к серверам Ozon вообще, поэтому его нечем клеймить.

Использование (см. config/accounts.py: cdp_profile_dir, cdp_port):
    1. Один раз на каждый аккаунт: запустить Chrome с его профилем и портом,
       войти в нужный кабинет seller.ozon.ru руками, оставить профиль (не удалять).
       Пример (PowerShell):
       Start-Process "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" `
           -ArgumentList '--user-data-dir="C:\\ChromeProfiles\\milky_garden" --remote-debugging-port=9223 --remote-allow-origins=* --no-first-run --no-default-browser-check'
    2. Дальше `CDPCookieFetcher.fetch_ozon_cookies()` сам запускает Chrome с этим же
       профилем и портом, забирает cookies, закрывает Chrome — без участия человека,
       пока сессия в профиле остаётся живой (Ozon сам тихо обновляет access-token
       через refresh-token при заходе на страницу).
"""

import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

import httpx
import websocket

from shared.logger import logger


class CDPCookieFetcher:
    """Извлечение cookies ozon.ru из профиля Chrome через CDP."""

    def __init__(self, profile_dir: Path, port: int, chrome_path: Optional[Path] = None):
        """
        Инициализация.

        Args:
            profile_dir: Папка профиля Chrome (--user-data-dir), в который заранее
                вручную выполнен вход в нужный кабинет
            port: Порт для --remote-debugging-port (свой на каждый аккаунт,
                чтобы можно было держать несколько профилей запущенными одновременно)
            chrome_path: Путь к chrome.exe (по умолчанию — стандартный путь установки)
        """
        self.profile_dir = profile_dir
        self.port = port
        self.chrome_path = chrome_path or self._default_chrome_path()

    @staticmethod
    def _default_chrome_path() -> Path:
        """Путь к Chrome по умолчанию для текущей ОС."""
        system = platform.system()
        if system == "Windows":
            return Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        if system == "Darwin":
            return Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        return Path("google-chrome")

    def fetch_ozon_cookies(self, wait_after_start: float = 4.0, cdp_timeout: float = 15.0) -> Optional[str]:
        """
        Запускает Chrome с этим профилем, забирает cookies ozon.ru через CDP, закрывает Chrome.

        Args:
            wait_after_start: Сколько секунд ждать после запуска Chrome перед обращением к CDP
            cdp_timeout: Сколько секунд ждать, пока CDP-порт начнёт отвечать

        Returns:
            Строка cookies вида "name=value; name2=value2; ..." или None при ошибке
        """
        if not self.chrome_path.exists():
            logger.error(f"❌ Chrome не найден: {self.chrome_path}")
            return None

        if not self.profile_dir.exists():
            logger.error(
                f"❌ Профиль браузера не найден: {self.profile_dir}\n"
                f"   Запустите Chrome с этим профилем и портом {self.port} и войдите в кабинет вручную"
            )
            return None

        logger.info(f"🌐 Запускаем Chrome (профиль {self.profile_dir.name}, порт {self.port})...")
        proc = self._launch_chrome()

        try:
            time.sleep(wait_after_start)

            if not self._wait_for_cdp(cdp_timeout):
                logger.error(f"❌ CDP не отвечает на порту {self.port} — Chrome не запустился вовремя")
                return None

            logger.info("🍪 Забираем cookies через CDP...")
            cookies = self._get_ozon_cookies()

            if not cookies:
                logger.warning(f"⚠️  Cookies для ozon.ru не найдены в профиле {self.profile_dir.name}")
                return None

            cookie_string = "; ".join(f"{c['name']}={c['value']}" for c in cookies if c.get("name"))
            logger.info(f"✅ Получено {len(cookies)} cookies ozon.ru")
            return cookie_string

        finally:
            self._kill_chrome(proc)

    def _launch_chrome(self) -> subprocess.Popen:
        """Запускает Chrome как обычный процесс (без chromedriver/Selenium)."""
        args = [
            str(self.chrome_path),
            f"--user-data-dir={self.profile_dir}",
            f"--remote-debugging-port={self.port}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
            "--disable-infobars",
        ]
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == "Windows" else 0
        return subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags
        )

    def _wait_for_cdp(self, timeout: float) -> bool:
        """Ждёт, пока CDP-эндпоинт на self.port начнёт отвечать."""
        url = f"http://localhost:{self.port}/json/version"
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if httpx.get(url, timeout=1.0).status_code == 200:
                    return True
            except httpx.HTTPError:
                pass
            time.sleep(0.4)
        return False

    def _get_ozon_cookies(self) -> List[Dict]:
        """Забирает все cookies домена ozon.ru через CDP-команду Network.getAllCookies."""
        targets = httpx.get(f"http://localhost:{self.port}/json", timeout=5.0).json()
        if not targets:
            raise RuntimeError(f"Нет открытых вкладок на порту {self.port}")

        ws_url = targets[0]["webSocketDebuggerUrl"]
        ws = websocket.create_connection(ws_url, timeout=8)
        try:
            ws.send(json.dumps({"id": 1, "method": "Network.getAllCookies"}))
            response = json.loads(ws.recv())
        finally:
            ws.close()

        cookies = response.get("result", {}).get("cookies", [])
        return [c for c in cookies if "ozon.ru" in c.get("domain", "")]

    def _kill_chrome(self, proc: subprocess.Popen) -> None:
        """
        Завершает Chrome для этого профиля.

        Chrome на Windows держит один процесс на `--user-data-dir`: если профиль
        уже был открыт (например, предыдущий запуск не закрылся), наш новый
        запуск Chrome просто передаёт аргументы уже работающему процессу и сам
        сразу завершается — `proc.pid` в этот момент уже мёртв, а убивать нужно
        настоящий долгоживущий процесс. Поэтому на Windows ищем и закрываем все
        chrome.exe с этим `--user-data-dir` по командной строке, а не только
        `proc.pid`. Без этого старый Chrome остаётся висеть вечно, а параллельная
        работа живой сессии в нём и httpx-запросов с той же cookie — частая причина
        разлогина аккаунта на Ozon (см. модульный docstring).
        """
        logger.info("🚪 Закрываем Chrome...")
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass

        if platform.system() == "Windows":
            self._kill_chrome_windows_by_profile()
            return

        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _kill_chrome_windows_by_profile(self) -> None:
        """Убивает все chrome.exe с этим --user-data-dir (см. docstring _kill_chrome)."""
        profile_marker = f"*--user-data-dir=*{self.profile_dir}*"
        ps_script = (
            "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
            f"Where-Object {{ $_.CommandLine -like '{profile_marker}' }} | "
            "ForEach-Object { taskkill /F /T /PID $_.ProcessId }"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
