@echo off
REM Полный цикл автоответов: Ozon (update-cookies + collect + reply) + Wildberries (collect + reply)
REM Запускать раз в 3 часа через Windows Task Scheduler

cd /d "C:\MainFolder\Programming\Python\marketplaces_auto_replies"

REM Логирование
set LOGFILE=logs\auto_cycle_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%.log

mkdir logs 2>nul

echo [%date% %time%] === Запуск полного цикла === >> %LOGFILE%

REM Ozon: update-cookies + collect + reply для всех аккаунтов
echo [%date% %time%] Запуск цикла Ozon... >> %LOGFILE%
python -m cli.main auto ozon --all-accounts >> %LOGFILE% 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] ОШИБКА: Ozon цикл завершился с кодом %errorlevel% >> %LOGFILE%
) else (
    echo [%date% %time%] OK: Ozon цикл завершён успешно >> %LOGFILE%
)

echo. >> %LOGFILE%

REM Wildberries: collect + reply для всех аккаунтов
echo [%date% %time%] Запуск цикла Wildberries... >> %LOGFILE%
python -m cli.main auto wb --all-accounts >> %LOGFILE% 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] ОШИБКА: WB цикл завершился с кодом %errorlevel% >> %LOGFILE%
) else (
    echo [%date% %time%] OK: WB цикл завершён успешно >> %LOGFILE%
)

echo [%date% %time%] === Цикл завершён === >> %LOGFILE%
