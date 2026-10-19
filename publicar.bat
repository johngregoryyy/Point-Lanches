@echo off
chcp 65001 >nul
title Point Lanches - Publicador de Versão (GitHub Releases)
color 0B

echo ================================================================
echo      POINT LANCHES – PUBLICADOR DE RELEASES NO GITHUB
echo ================================================================
echo.

:: 1. Forçar UTF-8 para evitar problemas de acentuação no terminal
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set "PATH=%~dp0tools\mingit\cmd;%LOCALAPPDATA%\Microsoft\WinGet\Packages\GitHub.cli_Microsoft.Winget.Source_8wekyb3d8bbwe\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;C:\Program Files\GitHub CLI;%PATH%"

:: 2. Localizar Python
set PYTHON_CMD=python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
        set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    ) else if exist "C:\Users\Herval\AppData\Local\Programs\Python\Python314\python.exe" (
        set PYTHON_CMD="C:\Users\Herval\AppData\Local\Programs\Python\Python314\python.exe"
    )
)

:: 3. Executar publicador
%PYTHON_CMD% tools\publish_release.py %*

if %errorlevel% neq 0 (
    echo.
    color 0C
    echo ================================================================
    echo      AVISO: O PROCESSO FINALIZOU COM PENDENCIAS OU ERRO
    echo ================================================================
    echo O log detalhado de toda a operacao foi gravado em:
    echo   %~dp0publicar.log
    echo.
    echo Abrindo o log no Bloco de Notas para conferencia...
    start notepad.exe "%~dp0publicar.log"
    echo.
    echo Pressione qualquer tecla para encerrar esta janela...
    pause >nul
    exit /b 1
) else (
    echo.
    color 0A
    echo ================================================================
    echo      SUCESSO: RELEASE PUBLICADA COM EXITO NO GITHUB!
    echo ================================================================
    echo.
    echo Pressione qualquer tecla para finalizar...
    pause >nul
)
