@echo off
REM Полный цикл автоответов на сервере: Ozon + Wildberries
REM Запускать раз в 3 часа через Windows Task Scheduler на Proftex-Server
REM Читает PYTHON_EXE из .env файла

setlocal enabledelayedexpansion

cd /d "C:\Proftex-Server\marketplaces_auto_replies"

REM Создаём папку логов если её нет
mkdir logs 2>nul

REM Формируем путь логфайла с датой/временем
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set LOGFILE=logs\auto_cycle_%mydate%_%mytime%.log

echo [%date% %time%] === Запуск полного цикла на сервере === >> %LOGFILE%

REM Загружаем PYTHON_EXE из .env (простой парсинг)
for /f "usebackq tokens=2 delims==" %%i in (`findstr "PYTHON_EXE" .env`) do (
    set "PYTHON_PATH=%%i"
)

if not defined PYTHON_PATH (
    echo [%date% %time%] ОШИБКА: PYTHON_EXE не найден в .env >> %LOGFILE%
    echo [%date% %time%] ОШИБКА: PYTHON_EXE не найден в .env
    exit /b 1
)

echo [%date% %time%] Используем Python: %PYTHON_PATH% >> %LOGFILE%

REM Ozon: update-cookies + collect + reply для всех аккаунтов
echo [%date% %time%] Запуск цикла Ozon... >> %LOGFILE%
"%PYTHON_PATH%" -m cli.main auto ozon --all-accounts >> %LOGFILE% 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] ОШИБКА: Ozon цикл завершился с кодом %errorlevel% >> %LOGFILE%
) else (
    echo [%date% %time%] OK: Ozon цикл завершён успешно >> %LOGFILE%
)

echo. >> %LOGFILE%

REM Wildberries: collect + reply для всех аккаунтов
echo [%date% %time%] Запуск цикла Wildberries... >> %LOGFILE%
"%PYTHON_PATH%" -m cli.main auto wb --all-accounts >> %LOGFILE% 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] ОШИБКА: WB цикл завершился с кодом %errorlevel% >> %LOGFILE%
) else (
    echo [%date% %time%] OK: WB цикл завершён успешно >> %LOGFILE%
)

echo [%date% %time%] === Цикл завершён === >> %LOGFILE%

endlocal
