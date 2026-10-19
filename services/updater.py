# services/updater.py - Sistema de Auto-Update via GitHub Releases para Windows
# =============================================================================

import os
import sys
import re
import json
import time
import socket
import urllib.request
import urllib.error
import threading
import subprocess
import webbrowser
import customtkinter as ctk

from version import __version__
from config import (
    GITHUB_OWNER, GITHUB_REPO, UPDATE_CHECK_TIMEOUT,
    COR_PRIMARIA, COR_PRIMARIA_HVR, COR_VERDE, COR_VERDE_HVR,
    COR_VERMELHO, COR_CINZA_BARRA, COR_TEXTO_SUAVE, COR_AZUL_POINT, COR_TEXTO
)


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

        self._download_status_lbl = ctk.CTkLabel(
            self._download_view,
            text="Preparando download da atualização...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_AZUL_POINT
        )
        self._download_status_lbl.pack(pady=(30, 10))

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

        # 1. Localizar binário .exe (ou .zip) nas assets do release
        target_asset = None
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

        # 2. Definir caminho do executável atual e arquivo temporário de download
        if getattr(sys, "frozen", False):
            current_exe = os.path.abspath(sys.executable)
            exe_dir = os.path.dirname(current_exe)
        else:
            # Em modo de desenvolvimento
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            exe_dir = os.path.join(base_dir, "dist", "PointLanches")
            if not os.path.isdir(exe_dir):
                exe_dir = base_dir
            current_exe = os.path.join(exe_dir, "PointLanches.exe")

        temp_exe = os.path.join(exe_dir, "PointLanches_update.exe")
        bat_script = os.path.join(exe_dir, "updater.bat")

        # 3. Baixar arquivo com relatório em tempo real
        try:
            self.after(0, lambda: self._download_status_lbl.configure(
                text=f"Baixando {target_asset.get('name', 'PointLanches.exe')}...",
                text_color=COR_AZUL_POINT
            ))

            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": f"PointLanches-Updater/{__version__}"}
            )

            downloaded = 0
            chunk_size = 65536  # 64 KB por bloco para download rápido

            with urllib.request.urlopen(req, timeout=30) as resp, open(temp_exe, "wb") as out_file:
                if total_size <= 0:
                    total_size = int(resp.headers.get("Content-Length", 0))

                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        prog = downloaded / total_size
                        mb_down = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        percent = int(prog * 100)

                        self.after(0, lambda p=prog, pct=percent, md=mb_down, mt=mb_total: (
                            self._progress_bar.set(p),
                            self._progress_detail_lbl.configure(text=f"{pct}% ({md:.1f} MB / {mt:.1f} MB)")
                        ))

            self.after(0, lambda: self._download_status_lbl.configure(
                text="✅ Download concluído! Reiniciando sistema...",
                text_color=COR_VERDE
            ))
            time.sleep(1)

        except Exception as exc:
            self.after(0, lambda e=exc: self._download_status_lbl.configure(
                text=f"❌ Erro ao baixar atualização: {str(e)[:45]}",
                text_color=COR_VERMELHO
            ))
            self.after(0, lambda: self._btn_depois.configure(state="normal", text="Fechar"))
            return

        # 4. Executar script Batch de substituição silenciosa e reiniciar
        if getattr(sys, "frozen", False):
            exe_name = os.path.basename(current_exe)
            batch_content = f"""@echo off
chcp 65001 >nul
title Atualizando Point Lanches...
echo ===================================================
echo     ATUALIZANDO POINT LANCHES PARA A VERSAO {self._tag}
echo ===================================================
echo Aguardando fechamento do aplicativo...
timeout /t 2 /nobreak >nul

:espera_lock
del /f /q "{current_exe}" >nul 2>&1
if exist "{current_exe}" (
    timeout /t 1 /nobreak >nul
    goto espera_lock
)

echo Substituindo executavel...
move /y "{temp_exe}" "{current_exe}" >nul 2>&1

echo Reiniciando Point Lanches...
start "" "{current_exe}"

:: Auto-excluir este script batch temporario
del /f /q "%~f0" >nul 2>&1
exit
"""
            try:
                with open(bat_script, "w", encoding="utf-8") as f:
                    f.write(batch_content)

                # Disparar processo desanexado do terminal
                DETACHED_FLAGS = (
                    subprocess.CREATE_NEW_PROCESS_GROUP |
                    subprocess.DETACHED_PROCESS |
                    subprocess.CREATE_NO_WINDOW
                )
                subprocess.Popen(
                    ["cmd.exe", "/c", bat_script],
                    creationflags=DETACHED_FLAGS,
                    close_fds=True
                )

                # Encerrar aplicativo imediatamente para liberar o lock do Windows
                self.after(100, lambda: sys.exit(0))
            except Exception as e:
                self.after(0, lambda err=e: self._download_status_lbl.configure(
                    text=f"Falha ao iniciar updater: {err}",
                    text_color=COR_VERMELHO
                ))
        else:
            # Em modo dev: avisa que baixou e deixa o arquivo salvo para inspeção
            self.after(0, lambda: self._download_status_lbl.configure(
                text="[Modo Dev] Atualização baixada em:\n" + temp_exe,
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
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"PointLanches-Updater/{__version__}",
            "Accept": "application/vnd.github.v3+json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
