# ui/screen_auth.py - Tela de Autenticação Supabase / Modo Offline
# =============================================================================

import threading
import customtkinter as ctk
from version import __version__
from config import (
    COR_PRIMARIA, COR_PRIMARIA_HVR, COR_VERDE, COR_VERDE_HVR,
    COR_VERMELHO, COR_CINZA_BARRA, COR_TEXTO, COR_TEXTO_SUAVE,
    COR_AZUL_POINT, COR_CINZA_CARD
)
from services.supabase_auth import auth_manager


class ScreenAuth(ctk.CTkToplevel):
    """
    Tela inicial de autenticação do Point Lanches.
    Exibida antes da abertura do sistema principal:
    - Permite login seguro via Supabase Auth (e-mail + senha).
    - Permite continuar em Modo Offline utilizando o banco SQLite local.
    """

    def __init__(self, parent, on_success=None, on_offline=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("Point Lanches - Acesso ao Sistema")
        self._on_success = on_success
        self._on_offline = on_offline

        self.geometry("440x510")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._acao_offline)

        self._senha_visivel = False
        self._processando = False

        self._centralizar_janela()
        self._build_ui()

    def _centralizar_janela(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - 440) // 2)
        y = max(0, (sh - 510) // 2)
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        self.configure(fg_color="#0F1218")

        card = ctk.CTkFrame(self, fg_color=COR_CINZA_BARRA, corner_radius=14, border_width=1, border_color="#1E293B")
        card.pack(fill="both", expand=True, padx=16, pady=14)

        # ── Logo & Cabeçalho ──
        logo_frame = ctk.CTkFrame(card, fg_color="transparent")
        logo_frame.pack(pady=(12, 2))

        ctk.CTkLabel(
            logo_frame, text="🍔 POINT",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COR_PRIMARIA
        ).pack(side="left")

        ctk.CTkLabel(
            logo_frame, text=" LANCHES",
            font=ctk.CTkFont(size=20, weight="bold", slant="italic"),
            text_color=COR_AZUL_POINT
        ).pack(side="left")

        ctk.CTkLabel(
            card, text=f"Sistema de Pedidos • v{__version__}",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#64748B"
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            card, text="Acesso à Nuvem (Supabase)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_TEXTO
        ).pack(pady=(0, 1))

        ctk.CTkLabel(
            card, text="Informe suas credenciais ou continue em modo local.",
            font=ctk.CTkFont(size=11),
            text_color=COR_TEXTO_SUAVE
        ).pack(pady=(0, 10))

        # ── Campos de Entrada ──
        form_frame = ctk.CTkFrame(card, fg_color="transparent")
        form_frame.pack(fill="x", padx=20)

        ctk.CTkLabel(form_frame, text="E-mail de Acesso", font=ctk.CTkFont(size=11, weight="bold"), text_color=COR_TEXTO_SUAVE).pack(anchor="w", pady=(0, 2))
        self._email_entry = ctk.CTkEntry(
            form_frame, height=34, font=ctk.CTkFont(size=12),
            placeholder_text="caixa@pointlanches.com",
            fg_color="#1E2430", border_color="#334155"
        )
        self._email_entry.pack(fill="x", pady=(0, 8))

        # Preencher e-mail anterior se existir
        email_salvo = auth_manager.get_user_email()
        if email_salvo:
            self._email_entry.insert(0, email_salvo)

        ctk.CTkLabel(form_frame, text="Senha", font=ctk.CTkFont(size=11, weight="bold"), text_color=COR_TEXTO_SUAVE).pack(anchor="w", pady=(0, 2))

        senha_box = ctk.CTkFrame(form_frame, fg_color="transparent")
        senha_box.pack(fill="x", pady=(0, 4))

        self._senha_entry = ctk.CTkEntry(
            senha_box, height=34, font=ctk.CTkFont(size=12),
            show="*", placeholder_text="Digite sua senha",
            fg_color="#1E2430", border_color="#334155"
        )
        self._senha_entry.pack(side="left", fill="x", expand=True)
        self._senha_entry.bind("<Return>", lambda e: self._executar_login())

        self._btn_olho = ctk.CTkButton(
            senha_box, text="👁", width=34, height=34,
            font=ctk.CTkFont(size=13),
            fg_color="#1E2430", hover_color="#334155",
            command=self._toggle_ver_senha
        )
        self._btn_olho.pack(side="left", padx=(5, 0))

        # ── Opção Lembrar Login ──
        self._lembrar_var = ctk.BooleanVar(value=True)
        self._check_lembrar = ctk.CTkCheckBox(
            form_frame, text="Lembrar login neste computador",
            variable=self._lembrar_var,
            font=ctk.CTkFont(size=11),
            text_color=COR_TEXTO_SUAVE,
            checkmark_color=COR_TEXTO,
            fg_color=COR_PRIMARIA
        )
        self._check_lembrar.pack(anchor="w", pady=(2, 6))

        # ── Label de Status / Erro ──
        self._status_lbl = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COR_VERMELHO, wraplength=340
        )
        self._status_lbl.pack(pady=(0, 4))

        # ── Botão Conectar Nuvem ──
        self._btn_login = ctk.CTkButton(
            card, text="🚀  Conectar à Nuvem", height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_PRIMARIA, hover_color=COR_PRIMARIA_HVR,
            corner_radius=8, command=self._executar_login
        )
        self._btn_login.pack(fill="x", padx=20, pady=(0, 6))

        # ── Divisor OU ──
        div_frame = ctk.CTkFrame(card, fg_color="transparent")
        div_frame.pack(fill="x", padx=24, pady=2)
        ctk.CTkFrame(div_frame, height=1, fg_color="#334155").pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(div_frame, text="  ou  ", font=ctk.CTkFont(size=10), text_color="#64748B").pack(side="left")
        ctk.CTkFrame(div_frame, height=1, fg_color="#334155").pack(side="left", fill="x", expand=True)

        # ── Botão Continuar Offline ──
        self._btn_offline = ctk.CTkButton(
            card, text="📴  Continuar Offline (Banco Local)", height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1E293B", hover_color="#334155",
            text_color=COR_TEXTO_SUAVE,
            corner_radius=8, command=self._acao_offline
        )
        self._btn_offline.pack(fill="x", padx=20, pady=(4, 10))

        # Foco inicial
        if email_salvo:
            self._senha_entry.focus_set()
        else:
            self._email_entry.focus_set()

    def _toggle_ver_senha(self):
        self._senha_visivel = not self._senha_visivel
        self._senha_entry.configure(show="" if self._senha_visivel else "*")

    def _executar_login(self):
        if self._processando:
            return

        email = self._email_entry.get().strip()
        senha = self._senha_entry.get()

        if not email or not senha:
            self._status_lbl.configure(text="⚠️ Informe e-mail e senha para conectar.", text_color=COR_VERMELHO)
            return

        self._processando = True
        self._btn_login.configure(state="disabled", text="Autenticando no Supabase...")
        self._status_lbl.configure(text="Conectando à nuvem segura...", text_color=COR_AZUL_POINT)

        def _worker():
            sucesso, msg = auth_manager.login(email, senha, remember=self._lembrar_var.get())
            if sucesso:
                self.after(0, lambda: self._status_lbl.configure(text="Sincronizando com a nuvem...", text_color=COR_AZUL_POINT))
                try:
                    from services.supabase_sync import sincronizar_tudo_com_supabase
                    sincronizar_tudo_com_supabase(timeout=6)
                except Exception:
                    pass
            self.after(0, lambda: self._pos_login(sucesso, msg))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _pos_login(self, sucesso: bool, msg: str):
        self._processando = False
        self._btn_login.configure(state="normal", text="🚀  Conectar à Nuvem")

        if sucesso:
            self._status_lbl.configure(text="✅ Conectado com sucesso!", text_color=COR_VERDE)
            self.after(350, self._concluir_sucesso)
        else:
            self._status_lbl.configure(text=f"❌ {msg}", text_color=COR_VERMELHO)

    def _concluir_sucesso(self):
        try:
            self.destroy()
        except Exception:
            pass
        if self._on_success:
            self._on_success()

    def _acao_offline(self):
        try:
            self.destroy()
        except Exception:
            pass
        if self._on_offline:
            self._on_offline()
