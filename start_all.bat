@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ==========================================
echo   ЗАПУСК ПОЛНОЙ СИСТЕМЫ
echo ==========================================
echo.

python --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ОШИБКА] Python не найден!
    pause
    exit /b 1
)

cd /d "%~dp0"

if not exist venv (
    echo Создаю виртуальное окружение...
    python -m venv venv
)

echo Активация окружения...
call venv\Scripts\activate.bat

echo Установка зависимостей...
if exist requirements.txt (
    pip install -r requirements.txt -q
)

echo.
echo ==========================================
echo   ЗАПУСК КОМПОНЕНТОВ
echo ==========================================
echo.
echo [1] Запускаю БОТА...
start "Bot Process" cmd /k python main.py

timeout /t 2 /nobreak

echo [2] Запускаю АДМИН-ПАНЕЛЬ...
start "Admin Panel" cmd /k cd admin_panel ^& ..\venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

echo.
echo ==========================================
echo   ВСЕ КОМПОНЕНТЫ ЗАПУЩЕНЫ
echo ==========================================
echo.
echo БОТ:          Работает в отдельном окне
echo АДМИН-ПАНЕЛЬ: http://127.0.0.1:8000
echo.
echo Для остановки закрой оба окна (или нажми Ctrl+C в каждом)
echo.
pause
