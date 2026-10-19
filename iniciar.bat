@echo off
:: iniciar.bat - Inicializador do Point Lanches
title Point Lanches - Sistema de Pedidos
cd /d "%~dp0"

:: Tenta python no PATH; se falhar, usa caminho direto do Python 3.14
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python main.py
) else (
    "C:\Users\Herval\AppData\Local\Programs\Python\Python314\python.exe" main.py
)

if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Falha ao iniciar.
    pause
)
