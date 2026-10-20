# services/updater.py - Sistema de Auto-Update via GitHub Releases para Windows
# =============================================================================

import os
import sys
import re
import json
import time
import socket
import ssl
import urllib.request
import urllib.error
import threading
import subprocess
import webbrowser
import tempfile
import ctypes
import customtkinter as ctk

from version import __version__
from config import (
    GITHUB_OWNER, GITHUB_REPO, UPDATE_CHECK_TIMEOUT,
    COR_PRIMARIA, COR_PRIMARIA_HVR, COR_VERDE, COR_VERDE_HVR,
    COR_VERMELHO, COR_CINZA_BARRA, COR_TEXTO_SUAVE, COR_AZUL_POINT, COR_TEXTO
)


# ── Utilitários de Permissão e Elevação UAC no Windows ─────────────────────────

def _is_running_as_admin() -> bool:
    """Verifica se o processo atual está executando com privilégios de Administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _can_write_to_folder(path: str) -> bool:
    """Testa se o diretório permite criação e exclusão direta de arquivos sem UAC."""
    try:
        os.makedirs(path, exist_ok=True)
        test_file = os.path.join(path, f".chk_perm_{os.getpid()}.tmp")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception:
        return False


# ── Contexto SSL Resiliente para Windows ─────────────────────────────────────

def _get_ssl_context() -> ssl.SSLContext:
    """
    Retorna um contexto SSL configurado para download de atualizações no Windows,
    evitando o erro 'SSL: CERTIFICATE_VERIFY_FAILED: Missing Authority Key Identifier'
    do OpenSSL ao redirecionar para os servidores de storage do GitHub / AWS S3.
    """
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        return ssl._create_unverified_context()


# Aplica o contexto SSL resiliente globalmente no urllib para cobrir redirects automáticos
try:
    ssl._create_default_https_context = _get_ssl_context
except AttributeError:
    pass


def _get_github_token() -> str | None:
    """Recupera o token do GitHub de variáveis de ambiente ou arquivo local se disponível."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".github_token"),
        os.path.expanduser("~/.github_token")
    ]
    for c in candidates:
        if os.path.isfile(c):
            try:
                with open(c, "r", encoding="utf-8") as f:
                    t = f.read().strip()
                    if t:
                        return t
            except Exception:
                pass
    return None


class SmartRedirectHandler(urllib.request.HTTPRedirectHandler):
    """
    Handler de redirecionamento inteligente:
    1. Remove o cabeçalho Authorization ao redirecionar para serviços de storage (AWS S3, Azure Blob)
       para evitar rejeições de autenticação de terceiros.
    2. Se o host for release-assets.githubusercontent.com (suscetível a erros 503 Backend unavailable
       por falha de cache/Varnish do Fastly no Brasil), contorna apontando diretamente para o storage origin.
    """
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_headers = dict(req.headers)
        new_headers.pop('Authorization', None)
        new_headers.pop('authorization', None)
        if 'release-assets.githubusercontent.com' in newurl:
            newurl = newurl.replace('release-assets.githubusercontent.com', 'releaseassetproduction.blob.core.windows.net')
        return urllib.request.Request(newurl, headers=new_headers, origin_req_host=req.origin_req_host, unverifiable=True)


def _parse_version(v_str: str) -> tuple[int, ...]:
    """
    Converte uma string de versão (ex: 'v1.0.1' ou '1.2.0') em tupla de inteiros
    para comparação segura no padrão de Versionamento Semântico.
    """
    nums = re.findall(r"\d+", v_str or "")
    return tuple(int(n) for n in nums) if nums else (0, 0, 0)


def is_newer_version(remote_ver: str, local_ver: str = __version__) -> bool:
    """Verifica se a versão remota é superior à versão local instalada."""
    return _parse_version(remote_ver) > _parse_version(local_ver)


# ── Diálogo Gráfico de Notificação e Download da Atualização ──────────────────

class UpdateDialog(ctk.CTkToplevel):
    """
    Janela modal para notificar o operador sobre uma nova versão disponível,
    exibir o changelog oficial e gerenciar o download/reinicialização do executável.
    """

    def __init__(self, parent, release_info: dict, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("🚀  Atualização Disponível – Point Lanches")
        self._release = release_info
        self._tag = release_info.get("tag_name", "").lstrip("vV")
        self._body = release_info.get("body", "Melhorias de desempenho e correções gerais.")

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        mw, mh = 530, 480
        self.geometry(f"{mw}x{mh}")
        self.minsize(480, 420)
        self.grab_set()
        self.resizable(False, False)

        px = max(10, (sw - mw) // 2)
        py = max(10, (sh - mh) // 2)
        self.geometry(f"+{px}+{py}")

        self._build_ui()

    def _build_ui(self):
        # 1. Cabeçalho
        header = ctk.CTkFrame(self, height=70, fg_color="#181818", corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="🚀  NOVA ATUALIZAÇÃO DISPONÍVEL!",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COR_VERDE
        ).pack(anchor="w", padx=20, pady=(12, 2))

        ctk.CTkLabel(
            header,
            text=f"Versão Atual: v{__version__}    ➜    Nova Versão: v{self._tag}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_AZUL_POINT
        ).pack(anchor="w", padx=20, pady=(0, 10))

        # 2. Container Central
        self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._content_frame.pack(fill="both", expand=True, padx=20, pady=14)

        # Visão 1: Detalhes e Changelog
        self._changelog_view = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._changelog_view.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self._changelog_view,
            text="O que há de novo nesta versão:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_TEXTO_SUAVE
        ).pack(anchor="w", pady=(0, 6))

        self._txt_notes = ctk.CTkTextbox(
            self._changelog_view,
            font=ctk.CTkFont(size=12),
            fg_color=COR_CINZA_BARRA,
            corner_radius=8,
            wrap="word"
        )
        self._txt_notes.pack(fill="both", expand=True, pady=(0, 10))
        self._txt_notes.insert("1.0", self._body or "Novas melhorias e otimizações de sistema.")
        self._txt_notes.configure(state="disabled")

        ctk.CTkLabel(
            self._changelog_view,
            text="💡 O download é rápido e o sistema será reiniciado automaticamente com a nova versão.",
            font=ctk.CTkFont(size=11),
            text_color=COR_TEXTO_SUAVE,
            justify="left"
        ).pack(anchor="w", pady=(0, 4))

        # Visão 2: Barra de Progresso do Download (inicialmente oculta)
        self._download_view = ctk.CTkFrame(self._content_frame, fg_color="transparent")

        from ui.components.loading import AnimatedGif
        self._download_gif = AnimatedGif(
            self._download_view,
            size=(170, 96),
            bg_color="transparent",
            autoplay=True
        )
        self._download_gif.pack(pady=(12, 4))

        self._download_status_lbl = ctk.CTkLabel(
            self._download_view,
            text="Preparando download da atualização...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_AZUL_POINT
        )
        self._download_status_lbl.pack(pady=(4, 10))

        self._progress_bar = ctk.CTkProgressBar(
            self._download_view,
            height=20,
            corner_radius=10,
            fg_color="#232323",
            progress_color=COR_VERDE
        )
        self._progress_bar.pack(fill="x", padx=10, pady=(0, 12))
        self._progress_bar.set(0.0)

        self._progress_detail_lbl = ctk.CTkLabel(
            self._download_view,
            text="0% (0.0 MB / 0.0 MB)",
            font=ctk.CTkFont(size=12),
            text_color=COR_TEXTO_SUAVE
        )
        self._progress_detail_lbl.pack(pady=(0, 20))

        # 3. Rodapé com Botões de Ação
        self._footer = ctk.CTkFrame(self, height=56, fg_color="#181818", corner_radius=0)
        self._footer.pack(fill="x", side="bottom")
        self._footer.pack_propagate(False)

        self._btn_atualizar = ctk.CTkButton(
            self._footer,
            text="🚀  Atualizar Agora",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_VERDE,
            hover_color=COR_VERDE_HVR,
            width=160, height=38,
            corner_radius=8,
            command=self._iniciar_atualizacao
        )
        self._btn_atualizar.pack(side="right", padx=(6, 20), pady=9)

        self._btn_depois = ctk.CTkButton(
            self._footer,
            text="Lembrar Mais Tarde",
            font=ctk.CTkFont(size=12),
            fg_color="#334155",
            hover_color="#475569",
            width=140, height=38,
            corner_radius=8,
            command=self.destroy
        )
        self._btn_depois.pack(side="right", padx=6, pady=9)

    def _iniciar_atualizacao(self):
        """Alterna a interface para o modo de download e dispara a thread de download."""
        self._changelog_view.pack_forget()
        self._download_view.pack(fill="both", expand=True)
        self._btn_atualizar.configure(state="disabled")
        self._btn_depois.configure(state="disabled")

        threading.Thread(target=self._executar_download_e_substituicao, daemon=True).start()

    def _executar_download_e_substituicao(self):
        """Localiza o binário correto no release, baixa com barra de progresso e dispara o batch updater."""
        assets = self._release.get("assets", [])

        # 1. Definir caminho do executável atual e diretório
        if getattr(sys, "frozen", False):
            current_exe = os.path.abspath(sys.executable)
            exe_dir = os.path.dirname(current_exe)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            exe_dir = os.path.join(base_dir, "dist", "PointLanches")
            if not os.path.isdir(exe_dir):
                exe_dir = base_dir
            current_exe = os.path.join(exe_dir, "PointLanches.exe")

        is_installed = os.path.exists(os.path.join(exe_dir, "unins000.exe"))

        # 2. Localizar o binário apropriado nas assets do release
        target_asset = None

        # Se for instalação completa via Inno Setup, priorizar o instalador Setup
        if is_installed:
            for a in assets:
                nome = a.get("name", "").lower()
                if nome.endswith(".exe") and ("setup" in nome or "instal" in nome):
                    target_asset = a
                    break

        # Se for versão standalone ou se não achou o instalador, buscar PointLanches.exe
        if not target_asset:
            for a in assets:
                nome = a.get("name", "").lower()
                if nome == "pointlanches.exe":
                    target_asset = a
                    break

        # Fallback para o instalador se não houver PointLanches.exe avulso
        if not target_asset:
            for a in assets:
                nome = a.get("name", "").lower()
                if nome.endswith(".exe") and ("setup" in nome or "instal" in nome):
                    target_asset = a
                    break

        # Fallback genérico para qualquer .exe
        if not target_asset:
            for a in assets:
                nome = a.get("name", "").lower()
                if nome.endswith(".exe"):
                    target_asset = a
                    break

        if not target_asset and assets:
            target_asset = assets[0]  # Primeiro arquivo anexado

        if not target_asset:
            # Fallback: abrir página de releases no navegador caso o binário não esteja anexado
            self.after(0, lambda: self._download_status_lbl.configure(
                text="⚠ Binário não encontrado na release. Abrindo no navegador...",
                text_color=COR_VERMELHO
            ))
            time.sleep(2)
            webbrowser.open(self._release.get("html_url", f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"))
            self.after(0, self.destroy)
            return

        download_url = target_asset.get("browser_download_url")
        total_size = target_asset.get("size", 0)
        asset_name = target_asset.get("name", "PointLanches.exe")
        is_setup_installer = ("setup" in asset_name.lower() or "instal" in asset_name.lower())

        # 2. Configurar caminhos em tempfile.gettempdir() e arquivos de log
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(
            temp_dir,
            f"PointLanches_Setup_v{self._tag}.exe" if is_setup_installer else f"PointLanches_update_v{self._tag}.exe"
        )
        bat_script = os.path.join(temp_dir, f"PointLanches_updater_{self._tag}.bat")
        update_log_file = os.path.join(temp_dir, "point_lanches_update.log")
        installer_log_file = os.path.join(temp_dir, "point_lanches_installer.log")

        def _log_update(msg: str):
            try:
                with open(update_log_file, "a", encoding="utf-8") as lf:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    lf.write(f"[{ts}] {msg}\n")
            except Exception:
                pass

        _log_update("===================================================")
        _log_update(f"INICIANDO PROCESSO DE ATUALIZACAO -> v{self._tag}")
        _log_update(f"Versao local: {__version__}")
        _log_update(f"Executavel atual: {current_exe}")
        _log_update(f"Diretorio de instalacao: {exe_dir}")
        _log_update(f"Instalado via Inno Setup: {is_installed}")
        _log_update(f"Asset selecionado: {asset_name} ({total_size} bytes)")
        _log_update(f"URL de download: {download_url}")
        _log_update(f"Arquivo temporario de download: {temp_file}")
        _log_update(f"Script batch do updater: {bat_script}")

        # 3. Baixar arquivo via API oficial de assets com retry automático (3 tentativas)
        token = _get_github_token()
        asset_id = target_asset.get("id")
        api_download_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/assets/{asset_id}" if asset_id else download_url

        ssl_ctx = _get_ssl_context()
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl_ctx),
            SmartRedirectHandler
        )

        max_tentativas = 3
        sucesso = False
        ultimo_erro = None
        downloaded_bytes = 0

        for tentativa in range(1, max_tentativas + 1):
            _log_update(f"Iniciando tentativa {tentativa}/{max_tentativas} de download via API: {api_download_url}")
            try:
                if tentativa > 1:
                    self.after(0, lambda t=tentativa: self._download_status_lbl.configure(
                        text=f"Tentando novamente ({t}/{max_tentativas})...",
                        text_color=COR_AZUL_POINT
                    ))
                else:
                    self.after(0, lambda: self._download_status_lbl.configure(
                        text=f"Baixando {asset_name}...",
                        text_color=COR_AZUL_POINT
                    ))

                headers = {
                    "Accept": "application/octet-stream",
                    "User-Agent": "PointLanches-Updater"
                }
                if token:
                    headers["Authorization"] = f"token {token}"

                # Na 1a e 2a tentativa prioriza o endpoint oficial da API de assets; na 3a tenta browser_download_url como alternativa
                url_requisicao = api_download_url if (tentativa < 3 or not download_url) else download_url
                req = urllib.request.Request(url_requisicao, headers=headers)

                downloaded = 0
                chunk_size = 65536  # 64 KB por bloco

                with opener.open(req, timeout=35) as resp, open(temp_file, "wb") as out_file:
                    cur_size = total_size
                    if cur_size <= 0:
                        cur_size = int(resp.headers.get("Content-Length", 0))

                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        downloaded += len(chunk)

                        if cur_size > 0:
                            prog = min(1.0, downloaded / cur_size)
                            mb_down = downloaded / (1024 * 1024)
                            mb_total = cur_size / (1024 * 1024)
                            percent = int(prog * 100)

                            self.after(0, lambda p=prog, pct=percent, md=mb_down, mt=mb_total: (
                                self._progress_bar.set(p),
                                self._progress_detail_lbl.configure(text=f"{pct}% ({md:.1f} MB / {mt:.1f} MB)")
                            ))

                downloaded_bytes = os.path.getsize(temp_file) if os.path.isfile(temp_file) else 0
                if downloaded_bytes > 0 and (cur_size <= 0 or downloaded_bytes >= cur_size * 0.95):
                    _log_update(f"Download concluido com sucesso na tentativa {tentativa}! Tamanho no disco: {downloaded_bytes} bytes")
                    sucesso = True
                    break
                else:
                    raise IOError(f"Arquivo recebido incompleto ({downloaded_bytes}/{cur_size} bytes)")

            except Exception as exc:
                ultimo_erro = exc
                _log_update(f"Falha na tentativa {tentativa}/{max_tentativas}: {exc}")
                if os.path.isfile(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception:
                        pass
                if tentativa < max_tentativas:
                    time.sleep(2)  # Intervalo de 2 segundos antes de tentar novamente

        if not sucesso:
            _log_update(f"ERRO definitivo durante o download apos {max_tentativas} tentativas: {ultimo_erro}")
            self.after(0, lambda e=ultimo_erro: (
                self._download_gif.stop() if hasattr(self, '_download_gif') else None,
                self._download_status_lbl.configure(
                    text=f"❌ Erro ao baixar atualização: {str(e)[:45]}",
                    text_color=COR_VERMELHO
                ),
                self._btn_depois.configure(state="normal", text="Fechar")
            ))
            return

        self.after(0, lambda: (
            self._download_gif.stop() if hasattr(self, '_download_gif') else None,
            self._progress_bar.set(1.0),
            self._progress_detail_lbl.configure(text=f"100% ({downloaded_bytes / (1024*1024):.1f} MB)"),
            self._download_status_lbl.configure(
                text="✅ Download concluído! Reiniciando sistema...",
                text_color=COR_VERDE
            )
        ))
        time.sleep(1)

        # 4. Executar instalador de atualização e reiniciar
        if getattr(sys, "frozen", False):
            exe_name = os.path.basename(current_exe)
            if is_setup_installer:
                installer_args = f'/SP- /SILENT /SUPPRESSMSGBOXES /FORCECLOSEAPPLICATIONS /DIR="{exe_dir}" /LOG="{installer_log_file}"'
                _log_update(f"Disparando instalador diretamente via ShellExecuteW: {temp_file} {installer_args}")

                try:
                    ret = ctypes.windll.shell32.ShellExecuteW(
                        None,
                        "open",
                        temp_file,
                        installer_args,
                        None,
                        1
                    )
                    _log_update(f"ShellExecuteW executado com retorno: {ret}")
                    if ret <= 32:
                        _log_update("ShellExecuteW retornou codigo <= 32, tentando subprocess.Popen fallback...")
                        subprocess.Popen(
                            [temp_file, "/SP-", "/SILENT", "/SUPPRESSMSGBOXES", "/FORCECLOSEAPPLICATIONS", f'/DIR={exe_dir}', f'/LOG={installer_log_file}'],
                            close_fds=True
                        )
                except Exception as exc:
                    _log_update(f"Erro no ShellExecuteW: {exc}, tentando subprocess.Popen...")
                    subprocess.Popen(
                        [temp_file, "/SP-", "/SILENT", "/SUPPRESSMSGBOXES", "/FORCECLOSEAPPLICATIONS", f'/DIR={exe_dir}', f'/LOG={installer_log_file}'],
                        close_fds=True
                    )

                # Aguarda 300ms para o processo do instalador ser inicializado pelo Windows e encerra
                self.after(300, lambda: os._exit(0))
                return
            else:
                batch_content = f"""@echo off
chcp 65001 >nul
title Atualizando Point Lanches...
set LOGFILE={update_log_file}

echo =================================================== >> "%LOGFILE%"
echo [%date% %time%] [updater.bat] Iniciando script de atualizacao standalone >> "%LOGFILE%"
echo [%date% %time%] [updater.bat] Versao alvo: {self._tag} >> "%LOGFILE%"
echo [%date% %time%] [updater.bat] Aguardando 2 segundos para encerramento... >> "%LOGFILE%"
timeout /t 2 /nobreak >nul

:: Garante encerramento do executavel antigo
taskkill /f /im "{exe_name}" >> "%LOGFILE%" 2>&1
timeout /t 1 /nobreak >nul

:espera_lock
del /f /q "{current_exe}" >nul 2>&1
if exist "{current_exe}" (
    timeout /t 1 /nobreak >nul
    goto espera_lock
)

echo [%date% %time%] [updater.bat] Substituindo executavel... >> "%LOGFILE%"
move /y "{temp_file}" "{current_exe}" >> "%LOGFILE%" 2>&1

echo [%date% %time%] [updater.bat] Reiniciando Point Lanches em "{current_exe}"... >> "%LOGFILE%"
start "" "{current_exe}"

:: Auto-excluir este script batch temporario
del /f /q "%~f0" >nul 2>&1
exit
"""
            try:
                with open(bat_script, "w", encoding="utf-8") as f:
                    f.write(batch_content)
                _log_update(f"Script batch criado com sucesso em: {bat_script}")

                # Avaliar se o diretório precisa de elevação de Administrador (ex: C:\Program Files)
                needs_admin = (not _can_write_to_folder(exe_dir)) or ("program files" in exe_dir.lower())
                is_admin = _is_running_as_admin()
                _log_update(f"Checagem de privilegios: is_admin={is_admin}, needs_admin={needs_admin}")

                if needs_admin and not is_admin:
                    _log_update("Disparando atualizacao via ShellExecuteW com verbo 'runas' (UAC)...")
                    ret = ctypes.windll.shell32.ShellExecuteW(
                        None,
                        "runas",
                        "cmd.exe",
                        f'/c "{bat_script}"',
                        None,
                        1
                    )
                    _log_update(f"ShellExecuteW executado com retorno: {ret}")
                else:
                    _log_update("Disparando atualizacao desanexada via subprocess.Popen...")
                    DETACHED_FLAGS = (
                        subprocess.CREATE_NEW_PROCESS_GROUP |
                        subprocess.DETACHED_PROCESS |
                        subprocess.CREATE_NO_WINDOW
                    )
                    p = subprocess.Popen(
                        ["cmd.exe", "/c", bat_script],
                        creationflags=DETACHED_FLAGS,
                        close_fds=True
                    )
                    _log_update(f"Subprocesso Popen iniciado PID: {p.pid}")

                # Aguardar 350ms para que o Windows inicialize o novo processo antes do encerramento
                self.after(350, lambda: os._exit(0))
            except Exception as e:
                _log_update(f"FALHA ao disparar updater: {e}")
                self.after(0, lambda err=e: self._download_status_lbl.configure(
                    text=f"Falha ao iniciar updater: {err}",
                    text_color=COR_VERMELHO
                ))
        else:
            # Em modo dev: avisa que baixou e deixa o arquivo salvo para inspeção
            _log_update(f"[Modo Dev] Atualizacao baixada em: {temp_file}")
            self.after(0, lambda: self._download_status_lbl.configure(
                text="[Modo Dev] Atualização baixada em:\n" + temp_file,
                text_color=COR_VERDE
            ))
            self.after(0, lambda: self._btn_depois.configure(state="normal", text="Concluir"))


# ── Verificador de Atualizações da API do GitHub ──────────────────────────────

def fetch_latest_release(owner: str = GITHUB_OWNER, repo: str = GITHUB_REPO, timeout: int = UPDATE_CHECK_TIMEOUT) -> dict | None:
    """
    Consulta a API pública do GitHub para obter a última release disponível.
    Retorna os dados em dict ou None caso ocorra qualquer erro de rede/timeout.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    headers = {
        "User-Agent": "PointLanches-Updater",
        "Accept": "application/vnd.github.v3+json"
    }
    token = _get_github_token()
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_get_ssl_context()) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data
    except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout, TimeoutError, Exception):
        # Falha silenciosa para não travar o caixa nem atrapalhar o operador
        return None

    return None


def check_for_updates(parent_window, owner: str = GITHUB_OWNER, repo: str = GITHUB_REPO, silent_if_uptodate: bool = True):
    """
    Executa a checagem de versão. Se houver nova versão, exibe o UpdateDialog.
    Se já estiver atualizado e silent_if_uptodate=False, exibe mensagem informativa.
    """
    release = fetch_latest_release(owner=owner, repo=repo)
    if not release:
        if not silent_if_uptodate:
            _mostrar_aviso(parent_window, "Verificação de Versão", "Não foi possível conectar ao servidor de atualizações.\nVerifique sua conexão com a internet.", icone="⚠️")
        return

    tag_remota = release.get("tag_name", "").lstrip("vV")
    if is_newer_version(tag_remota, __version__):
        # Nova versão encontrada -> abrir popup no thread da UI
        parent_window.after(0, lambda: UpdateDialog(parent_window, release))
    else:
        if not silent_if_uptodate:
            _mostrar_aviso(parent_window, "Sistema Atualizado", f"Você já está utilizando a versão mais recente do Point Lanches (v{__version__}).", icone="✅")


def check_updates_background(parent_window, owner: str = GITHUB_OWNER, repo: str = GITHUB_REPO):
    """
    Dispara a checagem de atualização em uma thread separada para não causar lag
    nem atrasar o carregamento da tela do caixa.
    """
    threading.Thread(
        target=lambda: check_for_updates(parent_window, owner=owner, repo=repo, silent_if_uptodate=True),
        daemon=True,
        name="PointLanches-AutoUpdater"
    ).start()


def _mostrar_aviso(parent, titulo: str, msg: str, icone: str = "ℹ️"):
    """Exibe um diálogo informativo compacto do CustomTkinter."""
    win = ctk.CTkToplevel(parent)
    win.title(titulo)
    win.geometry("420x220")
    win.grab_set()
    win.resizable(False, False)

    win.update_idletasks()
    px = parent.winfo_rootx() + (parent.winfo_width() - 420) // 2
    py = parent.winfo_rooty() + (parent.winfo_height() - 220) // 2
    win.geometry(f"+{max(0, px)}+{max(0, py)}")

    ctk.CTkLabel(win, text=icone, font=ctk.CTkFont(size=40)).pack(pady=(16, 2))
    ctk.CTkLabel(win, text=titulo, font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(2, 6))
    ctk.CTkLabel(win, text=msg, font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE, wraplength=380, justify="center").pack(padx=20, pady=(0, 14))

    ctk.CTkButton(
        win, text="OK", width=120, height=36,
        font=ctk.CTkFont(size=13, weight="bold"),
        fg_color=COR_PRIMARIA, hover_color=COR_PRIMARIA_HVR,
        corner_radius=8, command=win.destroy
    ).pack(pady=(0, 14))
