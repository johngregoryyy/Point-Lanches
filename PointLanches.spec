# -*- mode: python ; coding: utf-8 -*-
# PointLanches.spec - Arquivo de especificação PyInstaller para Point Lanches
# =============================================================================

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import sys
import os

block_cipher = None

# 1. Coleta automática de todos os dados e submódulos do CustomTkinter
# (inclui arquivos JSON de temas, fontes OTF/TTF e assets gráficos)
datas = collect_data_files('customtkinter')
# Incluir pasta assets com o ícone oficial da aplicação
datas += [('assets', 'assets')]

# 2. Módulos ocultos para garantir inclusão completa
hiddenimports = [
    'customtkinter',
    'darkdetect',
    'packaging',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'PIL.ImageSequence',
    'PIL._tkinter_finder',
    'sqlite3',
    'socket',
    'ctypes',
    'ctypes.wintypes',
    'datetime',
    'textwrap',
    're',
    'urllib',
    'urllib.request',
    'urllib.error',
    'json',
    'webbrowser',
    'subprocess',
    'version',
    'services',
    'services.updater',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test', 'unittest', 'test'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# ── MODO DISTRIBUÍVEL EM PASTA (--onedir) - RECOMENDADO PARA CAIXA COMERCIAL ──
# Proporciona inicialização instantânea, estabilidade com antivírus e
# fácil acesso ao banco de dados SQLite para backups.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PointLanches',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                 # 100% Gráfico: Sem janela preta de terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/images.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PointLanches',
)
