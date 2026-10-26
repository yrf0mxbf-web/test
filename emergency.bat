@echo off
chcp 65001 >nul
title Strovo — Аварийный сервер
cd /d "%~dp0"
echo.
echo  ========================================
echo   STROVO — АВАРИЙНЫЙ СЕРВЕР
echo  ========================================
echo.
python emergency_server.py
if errorlevel 1 (
  echo.
  echo  Python не найден или ошибка запуска.
  echo  Попробуй:  py emergency_server.py
  py emergency_server.py
)
pause
