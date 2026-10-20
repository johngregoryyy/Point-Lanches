# ui/components/widgets.py - Componentes reutilizáveis (v2)
# =============================================================================

import customtkinter as ctk
from version import __version__
from config import (
    COR_PRIMARIA, COR_PRIMARIA_HVR, COR_CINZA_CARD,
    COR_VERDE, COR_VERDE_HVR, COR_VERMELHO, COR_VERMELHO_HVR,
    COR_TEXTO, COR_TEXTO_SUAVE, COR_SELECAO,
    COR_CINZA_BARRA, COR_AZUL_POINT
)


# ── Utilitário de Feedback Visual e Prevenção de Duplo-Clique ──────────────────

def com_feedback_clique(botao: ctk.CTkButton, comando, cor_flash: str = None, debounce_ms: int = 180):
    """
    Envolve o comando de um botão para:
    1. Fornecer feedback visual/tátil imediato de clique (flash na cor de destaque).
    2. Bloquear cliques acidentais múltiplos (debounce de 180ms para operadores de caixa).
    """
    bloqueado = False

    def wrapper(*args, **kwargs):
        nonlocal bloqueado
        if bloqueado:
            return
        bloqueado = True

        try:
            cor_atual = botao.cget("fg_color")
            flash = cor_flash or (COR_VERDE if cor_atual != COR_VERDE else COR_PRIMARIA_HVR)
            botao.configure(fg_color=flash)
            botao.after(90, lambda: botao.configure(fg_color=cor_atual) if botao.winfo_exists() else None)
        except Exception:
            pass

        try:
            if comando:
                return comando(*args, **kwargs)
        finally:
            if botao.winfo_exists():
                botao.after(debounce_ms, _liberar)

    def _liberar():
        nonlocal bloqueado
        bloqueado = False

    return wrapper


def habilitar_feedback_clique(botao: ctk.CTkButton, cor_flash: str = None, debounce_ms: int = 180) -> ctk.CTkButton:
    """Aplica o wrapper com feedback tátil e debounce a um CTkButton já existente."""
    cmd_original = botao.cget("command")
    if not cmd_original:
        return botao
    botao.configure(command=com_feedback_clique(botao, cmd_original, cor_flash=cor_flash, debounce_ms=debounce_ms))
    return botao


class ProductCard(ctk.CTkButton):
    """Card clicável de produto com feedback tátil imediato e prevenção de clique duplo."""

    def __init__(self, master, nome: str, preco: float,
                 descricao: str = "", categoria: str = "",
                 on_click=None, **kwargs):
        self._nome      = nome
        self._preco     = preco
        self._desc      = descricao
        self._categoria = categoria
        self._bloqueado = False

        preco_fmt = f"R$ {preco:.2f}".replace(".", ",")
        label = f"{nome}\n{preco_fmt}"

        def _click_handler():
            if self._bloqueado:
                return
            self._bloqueado = True

            # Feedback tátil imediato: borda destacada e preenchimento ativo
            try:
                self.configure(fg_color=COR_PRIMARIA, border_color=COR_VERDE, border_width=2)
                self.after(100, lambda: self.configure(
                    fg_color=COR_CINZA_CARD, border_color=COR_PRIMARIA, border_width=1
                ) if self.winfo_exists() else None)
            except Exception:
                pass

            try:
                if on_click:
                    on_click(nome, preco, descricao, categoria)
            finally:
                self.after(200, self._desbloquear)

        super().__init__(
            master,
            text=label,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=74,
            width=140,
            corner_radius=10,
            fg_color=COR_CINZA_CARD,
            hover_color=COR_SELECAO,
            text_color=COR_TEXTO,
            border_color=COR_PRIMARIA,
            border_width=1,
            command=_click_handler,
            **kwargs
        )

    def _desbloquear(self):
        self._bloqueado = False


class ChipButton(ctk.CTkButton):
    """Botão chip estilo pill com feedback tátil na seleção."""

    def __init__(self, master, text: str, on_select=None,
                 selected=False, **kwargs):
        self._selected  = selected
        self._on_select = on_select
        self._text      = text

        super().__init__(
            master,
            text=text,
            height=32,
            corner_radius=16,
            font=ctk.CTkFont(size=12),
            border_width=2,
            **kwargs
        )
        self._apply_state()
        self.configure(command=self._toggle)

    def _toggle(self):
        # Feedback tátil instantâneo ao clicar
        try:
            self.configure(border_color="#FFFFFF")
        except Exception:
            pass

        self._selected = not self._selected
        self._apply_state()
        if self._on_select:
            self._on_select(self._text, self._selected)

    def _apply_state(self):
        if self._selected:
            self.configure(
                fg_color=COR_PRIMARIA,
                hover_color=COR_PRIMARIA_HVR,
                text_color="#FFFFFF",
                border_color=COR_PRIMARIA,
            )
        else:
            self.configure(
                fg_color="transparent",
                hover_color="#3A3A3A",
                text_color=COR_TEXTO_SUAVE,
                border_color="#555555",
            )

    def set_selected(self, val: bool):
        self._selected = val
        self._apply_state()

    @property
    def selected(self):
        return self._selected


class RadioChip(ctk.CTkFrame):
    """Grupo de chips de seleção única (radio-style)."""

    def __init__(self, master, opcoes: list, on_change=None,
                 selecionado=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_change   = on_change
        self._selecionado = selecionado
        self._chips: dict[str, ChipButton] = {}

        for i, op in enumerate(opcoes):
            chip = ChipButton(
                self, text=str(op),
                selected=(str(op) == str(selecionado)),
                on_select=self._on_chip_select
            )
            chip.grid(row=0, column=i, padx=4, pady=4, sticky="w")
            self._chips[str(op)] = chip

    def _on_chip_select(self, texto: str, _estado: bool):
        for k, chip in self._chips.items():
            chip.set_selected(k == texto)
        self._selecionado = texto
        if self._on_change:
            self._on_change(texto)

    def get(self):
        return self._selecionado

    def set(self, val):
        self._on_chip_select(str(val), True)


class CartItem(ctk.CTkFrame):
    """Linha do carrinho: [Nome + obs (expand=True)] [(-) [Qtd] (+)] [Preço (width=75)] [Lixeira (width=30)]"""

    def __init__(self, master, item: dict,
                 on_change=None, on_remove=None, **kwargs):
        super().__init__(master, fg_color="#1E2430", corner_radius=8, **kwargs)
        self._item      = item
        self._on_change = on_change
        self._on_remove = on_remove

        # Grid rigorosamente alinhado:
        # Coluna 0: Nome + Obs (weight=1, absorve o espaço variável)
        # Colunas 1, 2, 3: Controles fixos que jamais colapsam
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.columnconfigure(2, weight=0)
        self.columnconfigure(3, weight=0)
        self.rowconfigure(0, weight=1)

        nome_text = item["nome"]
        obs = item.get("observacao", "")
        if obs:
            nome_text += f"\n↳ {obs}"

        # 1. Nome do produto + Observações (expand=True)
        ctk.CTkLabel(
            self, text=nome_text,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w", justify="left",
            wraplength=115
        ).grid(row=0, column=0, padx=(8, 2), pady=6, sticky="ew")

        # 2. Sub-frame horizontal exclusivo para quantidade (largura fixa 90px, sem expansão)
        qty_frame = ctk.CTkFrame(self, fg_color="transparent", width=90, height=32)
        qty_frame.grid(row=0, column=1, padx=2, pady=4, sticky="e")
        qty_frame.pack_propagate(False)

        # Botão Menos (-) tamanho fixo 28x28
        self._btn_dec = ctk.CTkButton(
            qty_frame, text="−", width=28, height=28,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#3A1E1E", hover_color="#5A2828", text_color="#EF4444",
            corner_radius=14,
            command=self._decrement
        )
        self._btn_dec.pack(side="left", padx=1)
        habilitar_feedback_clique(self._btn_dec, cor_flash="#5A1E1E", debounce_ms=100)

        # Label Quantidade (largura fixa 30, texto centralizado)
        self._qty_lbl = ctk.CTkLabel(
            qty_frame, text=str(item["quantidade"]),
            font=ctk.CTkFont(size=13, weight="bold"),
            width=30, anchor="center"
        )
        self._qty_lbl.pack(side="left", padx=0)

        # Botão Mais (+) tamanho fixo 28x28
        self._btn_inc = ctk.CTkButton(
            qty_frame, text="+", width=28, height=28,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#1E3828", hover_color="#2A5038", text_color="#10B981",
            corner_radius=14,
            command=self._increment
        )
        self._btn_inc.pack(side="left", padx=1)
        habilitar_feedback_clique(self._btn_inc, cor_flash="#2A5038", debounce_ms=100)

        # 3. Preço Total (largura fixa 75, alinhado à direita)
        total = item['quantidade'] * item['preco_unit']
        self._preco_lbl = ctk.CTkLabel(
            self,
            text=f"R$ {total:.2f}".replace(".", ","),
            font=ctk.CTkFont(size=12, weight="bold"),
            width=75, anchor="e"
        )
        self._preco_lbl.grid(row=0, column=2, padx=(2, 4), sticky="e")

        # 4. Botão Lixeira (largura fixa 30)
        btn_del = ctk.CTkButton(
            self, text="🗑", width=30, height=28,
            fg_color="transparent", hover_color="#3A1A1A", text_color="#EF4444",
            font=ctk.CTkFont(size=15),
            corner_radius=6,
            command=self._remove
        )
        btn_del.grid(row=0, column=3, padx=(0, 6), sticky="e")
        habilitar_feedback_clique(btn_del, cor_flash="#5A1A1A", debounce_ms=150)

    def _increment(self):
        self._item["quantidade"] += 1
        self._atualizar()

    def _decrement(self):
        if self._item["quantidade"] > 1:
            self._item["quantidade"] -= 1
            self._atualizar()

    def _atualizar(self):
        self._qty_lbl.configure(text=str(self._item["quantidade"]))
        total = self._item["quantidade"] * self._item["preco_unit"]
        self._preco_lbl.configure(text=f"R$ {total:.2f}".replace(".", ","))
        if self._on_change:
            self._on_change()

    def _remove(self):
        if self._on_remove:
            self._on_remove(self._item)


class TopBar(ctk.CTkFrame):
    """Barra superior com logo, título e botões de ação."""

    def __init__(self, master, titulo: str,
                 on_admin=None, on_historico=None, on_balanco=None, on_login=None, on_sync=None, **kwargs):
        super().__init__(master, height=48, corner_radius=0,
                         fg_color=COR_CINZA_BARRA, **kwargs)
        self.pack_propagate(False)
        self._on_login = on_login
        self._on_sync = on_sync

        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.pack(side="left", padx=14)

        ctk.CTkLabel(
            logo_frame, text="🍔 POINT",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COR_PRIMARIA
        ).pack(side="left")

        ctk.CTkLabel(
            logo_frame, text=" LANCHES",
            font=ctk.CTkFont(size=16, weight="bold", slant="italic"),
            text_color=COR_AZUL_POINT
        ).pack(side="left")

        ctk.CTkLabel(
            logo_frame, text=f"v{__version__}",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#64748B"
        ).pack(side="left", padx=(6, 0), pady=(3, 0))

        ctk.CTkLabel(
            self, text=f"│  {titulo}",
            font=ctk.CTkFont(size=13),
            text_color=COR_TEXTO_SUAVE
        ).pack(side="left", padx=6)

        # Botões à direita (ordem inversa com side=right)
        if on_admin:
            btn_adm = ctk.CTkButton(
                self, text="⚙", width=38, height=32,
                font=ctk.CTkFont(size=18),
                fg_color="transparent",
                hover_color="#3A3A3A",
                command=on_admin
            )
            btn_adm.pack(side="right", padx=3)
            habilitar_feedback_clique(btn_adm, cor_flash="#475569", debounce_ms=250)

        if on_balanco:
            btn_bal = ctk.CTkButton(
                self, text="📊", width=38, height=32,
                font=ctk.CTkFont(size=16),
                fg_color="transparent",
                hover_color="#3A3A3A",
                command=on_balanco
            )
            btn_bal.pack(side="right", padx=3)
            habilitar_feedback_clique(btn_bal, cor_flash="#475569", debounce_ms=250)

        if on_historico:
            btn_hist = ctk.CTkButton(
                self, text="📋", width=38, height=32,
                font=ctk.CTkFont(size=18),
                fg_color="transparent",
                hover_color="#3A3A3A",
                command=on_historico
            )
            btn_hist.pack(side="right", padx=3)
            habilitar_feedback_clique(btn_hist, cor_flash="#475569", debounce_ms=250)

        # Botão de Sincronização manual com Supabase
        if on_sync:
            self._btn_sync = ctk.CTkButton(
                self, text="🔄", width=38, height=32,
                font=ctk.CTkFont(size=16),
                fg_color="transparent",
                hover_color="#3A3A3A",
                command=self._disparar_sync
            )
            self._btn_sync.pack(side="right", padx=3)
            habilitar_feedback_clique(self._btn_sync, cor_flash="#475569", debounce_ms=1000)

        # Botão de Login / Conectar Nuvem (visível em modo offline, oculto quando logado)
        self._btn_cloud_login = ctk.CTkButton(
            self, text="☁️ Conectar", width=96, height=30,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#0369A1", hover_color="#0284C7",
            corner_radius=6,
            command=self._disparar_login
        )
        habilitar_feedback_clique(self._btn_cloud_login, cor_flash="#38BDF8", debounce_ms=250)

        # Listener para auto-ocultação quando logado no Supabase
        try:
            from services.supabase_auth import auth_manager
            auth_manager.add_auth_listener(self.atualizar_status_auth)
            self.atualizar_status_auth(auth_manager.is_authenticated())
        except Exception:
            self._btn_cloud_login.pack(side="right", padx=5)

    def _disparar_sync(self):
        """Dispara sincronização bidirecional em segundo plano com feedback visual."""
        if not hasattr(self, "_btn_sync"):
            return
        self._btn_sync.configure(text="⏳", state="disabled")

        def _worker():
            try:
                from services.supabase_sync import sincronizar_tudo_com_supabase
                sincronizar_tudo_com_supabase(timeout=6)
            except Exception as e:
                print(f"Erro ao sincronizar manualmente: {e}")

            def _update_ui():
                if self.winfo_exists() and hasattr(self, "_btn_sync"):
                    self._btn_sync.configure(text="✅")
                    self.after(1200, lambda: self._btn_sync.configure(text="🔄", state="normal") if self.winfo_exists() and hasattr(self, "_btn_sync") else None)
                if self._on_sync:
                    self._on_sync()

            try:
                self.after(0, _update_ui)
            except Exception:
                pass

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _disparar_login(self):
        if self._on_login:
            self._on_login()

    def atualizar_status_auth(self, logado: bool = None):
        """Atualiza a visibilidade do botão de login: caso esteja logado, o ícone SOME."""
        def _apply():
            nonlocal logado
            if logado is None:
                try:
                    from services.supabase_auth import auth_manager
                    logado = auth_manager.is_authenticated()
                except Exception:
                    logado = False

            if not hasattr(self, "_btn_cloud_login"):
                return

            if logado:
                # Caso esteja logado, o ícone SOME imediatamente
                if self._btn_cloud_login.winfo_ismapped():
                    self._btn_cloud_login.pack_forget()
            else:
                # Caso esteja offline, exibe o ícone de login junto aos outros botões
                if not self._btn_cloud_login.winfo_ismapped() and self._on_login:
                    self._btn_cloud_login.pack(side="right", padx=5)

        try:
            self.after(0, _apply)
        except Exception:
            _apply()
