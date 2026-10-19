@echo off
chcp 65001 >nul
title Point Lanches - Gerador de Executavel (PyInstaller)
color 0A

echo ================================================================
echo           POINT LANCHES - GERADOR DE EXECUTAVEL (.EXE)
echo ================================================================
echo.

:: 1. Localizar executável do Python
set PYTHON_CMD=python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
        set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    ) else if exist "C:\Users\Herval\AppData\Local\Programs\Python\Python314\python.exe" (
        set PYTHON_CMD="C:\Users\Herval\AppData\Local\Programs\Python\Python314\python.exe"
    ) else (
        echo [ERRO] Python nao foi encontrado no sistema!
        pause
        exit /b 1
    )
)

echo [OK] Python detectado: %PYTHON_CMD%
echo.

:: 2. Garantir dependências instaladas
echo [1/3] Verificando dependencias (customtkinter, pillow, pyinstaller)...
%PYTHON_CMD% -m pip install -q -r requirements.txt pyinstaller
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao instalar dependencias necessarias.
    pause
    exit /b 1
)
echo [OK] Todas as dependencias estao prontas.
echo.

:: 3. Escolher tipo de build
echo [2/3] Escolha o modo de empacotamento desejado:
echo.
echo   [1] PASTA DISTRIBUIVEL (--onedir) [RECOMENDADO PARA CAIXA / PDV]
echo       - Abre instantaneamente (sem demora ao clicar)
echo       - Maior estabilidade contra falsos positivos de antivirus
echo       - Banco SQLite 'point_lanches.db' fica visivel para backup facil
echo.
echo   [2] ARQUIVO UNICO (--onefile)
echo       - Gera apenas um arquivo 'PointLanches.exe'
echo       - Leva alguns segundos a mais para abrir na inicializacao
echo.
set /p MODO="Digite 1 ou 2 (Padrao: 1): "
if "%MODO%"=="" set MODO=1

echo.
echo [3/3] Compilando executavel... Por favor, aguarde...
echo.

if "%MODO%"=="2" (
    echo Compilando modo ARQUIVO UNICO (--onefile)...
    %PYTHON_CMD% -m PyInstaller --noconfirm --noconsole --onefile --name PointLanches --collect-all customtkinter main.py
) else (
    echo Compilando modo PASTA DISTRIBUIVEL (--onedir)...
    %PYTHON_CMD% -m PyInstaller --noconfirm PointLanches.spec
)

if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Ocorreu uma falha durante o processo de compilacao.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo       EXECUTAVEL GERADO COM SUCESSO NA PASTA 'dist'!
echo ================================================================
echo.
if "%MODO%"=="2" (
    echo Seu executavel: dist\PointLanches.exe
) else (
    echo Sua aplicacao: dist\PointLanches\PointLanches.exe
    echo Dica: Basta copiar a pasta 'PointLanches' para o computador do caixa!
)
echo.

:: Abrir pasta dist no Windows Explorer
if exist "dist" (
    start explorer dist
)

echo Pressione qualquer tecla para encerrar...
pause >nul
