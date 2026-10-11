@echo off
cd /d "%~dp0"

rem При запуске сразу в момент входа в Windows иногда не успевает
rem освободиться файл браузера Chromium (антивирус/фоновая загрузка
rem профиля) - Playwright кратко видит его как отсутствующий. Поэтому
rem если бот упал почти сразу, пробуем ещё раз с паузой, вместо того
rem чтобы сдаться.

set ATTEMPTS=0

:retry
set /a ATTEMPTS+=1
echo [%date% %time%] Попытка запуска %ATTEMPTS% >> bot_autostart.log
"C:\Program Files\Python312\python.exe" -m bot.main >> bot_autostart.log 2>&1

if %ATTEMPTS% LSS 5 (
    echo [%date% %time%] Бот завершился, жду 20 секунд и пробую снова... >> bot_autostart.log
    timeout /t 20 /nobreak >nul
    goto retry
)

echo [%date% %time%] Превышено число попыток, останавливаюсь. >> bot_autostart.log
