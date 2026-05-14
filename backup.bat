@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

REM Path to DB and backups folder
set DB_PATH=%~dp0shopDB.sqlite
set BACKUP_DIR=%~dp0backups

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM Build timestamp (YYYY-MM-DD_HH-MM-SS)
for /f "tokens=1-3 delims=/.- " %%a in ('date /t') do (
	set DD=%%a
	set MM=%%b
	set YY=%%c
)
for /f "tokens=1-2 delims=:" %%a in ('echo %time%') do (
	set HH=%%a
	set MN=%%b
)
set TIMESTAMP=%YY%-%MM%-%DD%_%HH%-%MN%

copy "%DB_PATH%" "%BACKUP_DIR%\shopDB_%TIMESTAMP%.sqlite"
echo Backup created: %BACKUP_DIR%\shopDB_%TIMESTAMP%.sqlite

REM Delete backups older than 30 days (Windows)
forfiles /p "%BACKUP_DIR%" /s /m *.sqlite /d -30 /c "cmd /c del @path" >nul 2>&1
echo Old backups deleted (older than 30 days).