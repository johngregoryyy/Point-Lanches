@echo off
:: instalar.bat - Instalador do Point Lanches
:: =========================================================
title Point Lanches - Instalando...
echo.
echo  =============================================
echo    POINT LANCHES - Instalacao do Sistema
echo  =============================================
echo.

:: Verificar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERRO] Python nao encontrado!
    echo  Por favor, instale o Python 3.10 ou superior em:
    echo  https://www.python.org/downloads/
    echo  IMPORTANTE: Marque "Add Python to PATH" durante a instalacao!
    echo.
    pause
    exit /b 1
)

echo  Python encontrado:
python --version
echo.

:: Instalar dependencias
echo  Instalando dependencias...
python -m pip install --upgrade pip -q
python -m pip install customtkinter Pillow -q

if %errorlevel% neq 0 (
    echo  [ERRO] Falha ao instalar dependencias!
    pause
    exit /b 1
)

echo.
echo  =============================================
echo    Instalacao concluida com sucesso!
echo    Execute: iniciar.bat ou python main.py
echo  =============================================
echo.
pause
