# ui/screen_cart.py - Tela 1: Cardápio e Carrinho (v2)
# =============================================================================

import customtkinter as ctk
from database.db import listar_categorias, listar_produtos, listar_adicionais, listar_observacoes_padrao
from ui.components.widgets import ProductCard, CartItem, ChipButton, TopBar
from config import (
    COR_PRIMARIA, COR_PRIMARIA_HVR, COR_VERDE, COR_VERDE_HVR,
    COR_CINZA_BARRA, COR_FUNDO, COR_TEXTO, COR_TEXTO_SUAVE,
)

# Categorias que NÃO exibem adicionais
CATS_SEM_ADICIONAIS = {"bebidas", "pratos feitos", "alaminuta"}


class ScreenCart(ctk.CTkFrame):
    """Tela 1 – Cardápio por categorias + Carrinho lateral."""

    def __init__(self, master, state: dict, on_next, on_admin,
                 on_historico=None, on_balanco=None, **kwargs):
        super().__init__(master, fg_color=COR_FUNDO, **kwargs)
        self._state        = state
        self._on_next      = on_next
        self._on_historico = on_historico
        self._on_balanco   = on_balanco
        self._cat_atual    = None     # None = Todos

        self._build_ui(on_admin)
        self._carregar_categorias()

    # ── Construção da UI ──────────────────────────────────────────────────────

    def _build_ui(self, on_admin):
        self._topbar = TopBar(
            self, "Cardápio",
            on_admin=on_admin,
            on_historico=self._on_historico,
            on_balanco=self._on_balanco
        )
        self._topbar.pack(fill="x")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=6)
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=0)
        body.rowconfigure(0, weight=1)

        # ── Sidebar categorias ──
        self._sidebar = ctk.CTkScrollableFrame(
            body, width=148, fg_color=COR_CINZA_BARRA, corner_radius=10
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        ctk.CTkLabel(
            self._sidebar, text="CATEGORIAS",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COR_TEXTO_SUAVE
        ).pack(pady=(8, 4), padx=6)

        # ── Grade de produtos ──
        self._prod_scroll = ctk.CTkScrollableFrame(
            body, fg_color="transparent"
        )
        self._prod_scroll.grid(row=0, column=1, sticky="nsew", padx=3)

        # ── Carrinho ──
        cart_panel = ctk.CTkFrame(
            body, width=320, fg_color=COR_CINZA_BARRA, corner_radius=10
        )
        cart_panel.grid(row=0, column=2, sticky="nsew")
        cart_panel.pack_propagate(False)

        ctk.CTkLabel(
            cart_panel, text="🛒  CARRINHO",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(10, 2))

        self._cart_scroll = ctk.CTkScrollableFrame(
            cart_panel, fg_color="transparent"
        )
        self._cart_scroll.pack(fill="both", expand=True, padx=6)

        cart_footer = ctk.CTkFrame(cart_panel, fg_color="transparent")
        cart_footer.pack(fill="x", padx=10, pady=6)

        self._subtotal_lbl = ctk.CTkLabel(
            cart_footer, text="Subtotal: R$ 0,00",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self._subtotal_lbl.pack(anchor="e", pady=(0, 6))

        self._btn_avancar = ctk.CTkButton(
            cart_footer,
            text="Avançar para Entrega  ➜",
            height=46,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COR_VERDE, hover_color=COR_VERDE_HVR,
            corner_radius=10,
            state="disabled",
            command=self._avancar
        )
        self._btn_avancar.pack(fill="x")

    # ── Categorias ────────────────────────────────────────────────────────────

    def _carregar_categorias(self):
        for w in self._sidebar.winfo_children():
            if isinstance(w, ctk.CTkButton):
                w.destroy()

        cats = listar_categorias()

        # ── Botão "Todos" primeiro ──
        btn_todos = ctk.CTkButton(
            self._sidebar,
            text="⊞  Todos",
            height=38, corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COR_PRIMARIA,
            hover_color=COR_PRIMARIA_HVR,
            anchor="w",
            command=lambda: self._selecionar_todos()
        )
        btn_todos.pack(fill="x", padx=4, pady=2)
        self._btn_todos = btn_todos

        self._cat_btns: list[ctk.CTkButton] = []
        for cat in cats:
            btn = ctk.CTkButton(
                self._sidebar,
                text=cat["nome"],
                height=38, corner_radius=8,
                font=ctk.CTkFont(size=12),
                fg_color="transparent",
                hover_color="#3A3A3A",
                anchor="w",
                command=lambda c=cat: self._selecionar_categoria(c)
            )
            btn.pack(fill="x", padx=4, pady=2)
            self._cat_btns.append(btn)

        # Iniciar na aba "Todos"
        self._selecionar_todos()

    def _selecionar_todos(self):
        self._cat_atual = None
        self._btn_todos.configure(fg_color=COR_PRIMARIA)
        for btn in self._cat_btns:
            btn.configure(fg_color="transparent")
        self._carregar_produtos_todos()

    def _selecionar_categoria(self, cat: dict):
        self._cat_atual = cat
        self._btn_todos.configure(fg_color="transparent")
        for btn in self._cat_btns:
            btn.configure(
                fg_color=COR_PRIMARIA if btn.cget("text") == cat["nome"] else "transparent"
            )
        self._carregar_produtos(cat["id"])

    # ── Grade de produtos ─────────────────────────────────────────────────────

    def _carregar_produtos_todos(self):
        """Modo 'Todos': agrupa por categoria com cabeçalho."""
        for w in self._prod_scroll.winfo_children():
            w.destroy()

        COLS = 3
        for c in range(COLS):
            self._prod_scroll.columnconfigure(c, weight=1)

        cats = listar_categorias()
        current_row = 0

        for cat in cats:
            produtos = listar_produtos(cat["id"])
            if not produtos:
                continue

            # Cabeçalho da categoria
            ctk.CTkLabel(
                self._prod_scroll,
                text=f"── {cat['nome'].upper()} ──",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COR_PRIMARIA,
                anchor="w"
            ).grid(
                row=current_row, column=0, columnspan=COLS,
                sticky="ew", padx=8, pady=(14, 2)
            )
            current_row += 1

            for i, prod in enumerate(produtos):
                col = i % COLS
                if i > 0 and col == 0:
                    current_row += 1
                card = ProductCard(
                    self._prod_scroll,
                    nome=prod["nome"],
                    preco=prod["preco"],
                    descricao=prod.get("descricao", ""),
                    categoria=prod.get("categoria", ""),
                    on_click=self._abrir_modal_item
                )
                card.grid(row=current_row, column=col, padx=8, pady=8, sticky="nsew")

            current_row += 1  # espaço após última linha da categoria

    def _carregar_produtos(self, categoria_id: int):
        """Modo categoria única: grade simples 3 colunas."""
        for w in self._prod_scroll.winfo_children():
            w.destroy()

        COLS = 3
        for c in range(COLS):
            self._prod_scroll.columnconfigure(c, weight=1)

        produtos = listar_produtos(categoria_id)
        for i, prod in enumerate(produtos):
            row, col = divmod(i, COLS)
            card = ProductCard(
                self._prod_scroll,
                nome=prod["nome"],
                preco=prod["preco"],
                descricao=prod.get("descricao", ""),
                categoria=prod.get("categoria", ""),
                on_click=self._abrir_modal_item
            )
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

    # ── Modal de adição ───────────────────────────────────────────────────────

    def _abrir_modal_item(self, nome: str, preco: float,
                          descricao: str, categoria: str):
        modal = ctk.CTkToplevel(self)
        modal.title(f"Adicionar: {nome}")

        modal.update_idletasks()
        sw = modal.winfo_screenwidth()
        sh = modal.winfo_screenheight()

        # Proporção adaptada para 1366x768 (altura máxima ~560px para não sobrepor a barra de tarefas)
        mw = min(660, sw - 30)
        mh = min(560, sh - 90)
        modal.minsize(520, 460)
        modal.resizable(True, True)
        modal.grab_set()

        px = max(10, (sw - mw) // 2)
        py = max(10, (sh - mh) // 2)
        modal.geometry(f"{mw}x{mh}+{px}+{py}")

        # ── Estado compartilhado do modal ──
        obs_selecionadas: list[str] = []
        adicionais_selecionados: list[dict] = []  # {"nome":..., "preco":...}
        preco_extra_var = ctk.DoubleVar(value=0.0)
        obs_var         = ctk.StringVar()
        obs_livre_var   = ctk.StringVar()
        qty_var         = ctk.IntVar(value=1)

        # ── 1. RODAPÉ FIXO NO FUNDO (SEMPRE VISÍVEL 100% DO TEMPO) ──
        footer = ctk.CTkFrame(modal, fg_color="#181818", height=66, corner_radius=0)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)

        foot_row = ctk.CTkFrame(footer, fg_color="transparent")
        foot_row.pack(fill="both", expand=True, padx=12, pady=8)
        foot_row.columnconfigure(0, weight=0)
        foot_row.columnconfigure(1, weight=1)

        # Seletor de quantidade no rodapé
        qty_frame = ctk.CTkFrame(foot_row, fg_color="#262626", corner_radius=10)
        qty_frame.grid(row=0, column=0, padx=(0, 14), sticky="w")

        ctk.CTkLabel(
            qty_frame, text="Qtd:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=(10, 4), pady=4)

        def _dec_qty():
            if qty_var.get() > 1:
                qty_var.set(qty_var.get() - 1)
                _recalcular_preco_total()

        def _inc_qty():
            qty_var.set(qty_var.get() + 1)
            _recalcular_preco_total()

        ctk.CTkButton(
            qty_frame, text="−", width=38, height=38,
            font=ctk.CTkFont(size=20, weight="bold"), corner_radius=8,
            fg_color="#3A3A3A", hover_color="#4A4A4A",
            command=_dec_qty
        ).pack(side="left", padx=3, pady=4)

        qty_lbl = ctk.CTkLabel(
            qty_frame, textvariable=qty_var,
            font=ctk.CTkFont(size=18, weight="bold"), width=34
        )
        qty_lbl.pack(side="left", padx=2)

        ctk.CTkButton(
            qty_frame, text="+", width=38, height=38,
            font=ctk.CTkFont(size=20, weight="bold"), corner_radius=8,
            fg_color=COR_VERDE, hover_color=COR_VERDE_HVR,
            command=_inc_qty
        ).pack(side="left", padx=(3, 10), pady=4)

        # Botão confirmar no rodapé
        def confirmar():
            extra = sum(a["preco"] for a in adicionais_selecionados)
            partes_obs = []
            if adicionais_selecionados:
                adicionais_str = ", ".join(f"+{a['nome']}" for a in adicionais_selecionados)
                partes_obs.append(f"Adicionais: {adicionais_str}")
            obs_livre = obs_var.get().strip()
            if obs_livre:
                partes_obs.append(obs_livre)
            obs_final = " | ".join(partes_obs)

            self._adicionar_ao_carrinho(
                nome=nome,
                preco=preco + extra,
                obs=obs_final,
                categoria=categoria,
                quantidade=qty_var.get()
            )
            modal.destroy()

        btn_confirmar = ctk.CTkButton(
            foot_row,
            text="✔  Adicionar ao Carrinho",
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COR_PRIMARIA, hover_color=COR_PRIMARIA_HVR,
            corner_radius=10,
            command=confirmar
        )
        btn_confirmar.grid(row=0, column=1, sticky="ew")

        # ── 2. ÁREA ROLÁVEL CENTRAL (CABEÇALHO + OBS + ADICIONAIS) ──
        scroll = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        scroll.pack(side="top", fill="both", expand=True, padx=10, pady=(6, 2))

        ctk.CTkLabel(
            scroll, text=nome,
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(4, 2))

        preco_base_lbl = ctk.CTkLabel(
            scroll, text=f"R$ {preco:.2f}".replace(".", ","),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COR_PRIMARIA
        )
        preco_base_lbl.pack(pady=(0, 2))

        if descricao:
            ctk.CTkLabel(
                scroll, text=descricao,
                font=ctk.CTkFont(size=12),
                text_color=COR_TEXTO_SUAVE,
                wraplength=620
            ).pack(pady=(0, 10), padx=14)

        def _recalcular_preco_total():
            extra = sum(a["preco"] for a in adicionais_selecionados)
            preco_extra_var.set(extra)
            unit_total = preco + extra
            tot_geral = unit_total * qty_var.get()

            preco_base_lbl.configure(
                text=f"R$ {unit_total:.2f}".replace(".", ",") +
                     (f"  (+R$ {extra:.2f})".replace(".", ",") if extra > 0 else "")
            )
            btn_confirmar.configure(
                text=f"✔  Adicionar ao Carrinho  •  R$ {tot_geral:.2f}".replace(".", ",")
            )

        def _atualizar_obs_field():
            partes = list(obs_selecionadas)
            livre = obs_livre_var.get().strip()
            if livre:
                partes.append(livre)
            obs_var.set(", ".join(partes))

        # ── Observações rápidas (3 colunas) ──
        # Bebidas NÃO exibem observações pré-definidas de lanches (como "Sem Maionese")
        if categoria.lower() != "bebidas":
            obs_rapidas_db = listar_observacoes_padrao(apenas_ativas=True)
            if obs_rapidas_db:
                ctk.CTkLabel(
                    scroll, text="Observações rápidas:",
                    font=ctk.CTkFont(size=13, weight="bold")
                ).pack(anchor="w", padx=14, pady=(4, 2))

                obs_frame = ctk.CTkFrame(scroll, fg_color="transparent")
                obs_frame.pack(fill="x", padx=10, pady=2)
                for c in range(3):
                    obs_frame.columnconfigure(c, weight=1)

                def on_obs_chip(texto: str, selecionado: bool):
                    if selecionado and texto not in obs_selecionadas:
                        obs_selecionadas.append(texto)
                    elif not selecionado and texto in obs_selecionadas:
                        obs_selecionadas.remove(texto)
                    _atualizar_obs_field()

                for idx, obs_item in enumerate(obs_rapidas_db):
                    chip = ChipButton(
                        obs_frame, text=obs_item["texto"],
                        on_select=on_obs_chip
                    )
                    chip.grid(row=idx // 3, column=idx % 3, padx=4, pady=3, sticky="ew")

        # Campo de observação livre
        ctk.CTkLabel(
            scroll, text="Observação livre:",
            font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE
        ).pack(anchor="w", padx=14, pady=(8, 0))

        ctk.CTkEntry(
            scroll, textvariable=obs_livre_var,
            placeholder_text="Ex: bem passado, sem sal...",
            height=36, font=ctk.CTkFont(size=13)
        ).pack(fill="x", padx=14, pady=(2, 10))
        obs_livre_var.trace_add("write", lambda *_: _atualizar_obs_field())

        # ── Adicionais em 3 colunas (aproveita melhor o espaço) ──
        if categoria.lower() not in CATS_SEM_ADICIONAIS:
            adicionais_db = listar_adicionais()
            if adicionais_db:
                ctk.CTkLabel(
                    scroll,
                    text="Adicionais:",
                    font=ctk.CTkFont(size=13, weight="bold")
                ).pack(anchor="w", padx=14, pady=(4, 2))

                add_frame = ctk.CTkFrame(scroll, fg_color="transparent")
                add_frame.pack(fill="x", padx=10, pady=2)
                for c in range(3):
                    add_frame.columnconfigure(c, weight=1)

                def on_adicional_chip(add: dict, texto: str, selecionado: bool):
                    if selecionado:
                        if add not in adicionais_selecionados:
                            adicionais_selecionados.append(add)
                    else:
                        if add in adicionais_selecionados:
                            adicionais_selecionados.remove(add)
                    _recalcular_preco_total()

                for idx, ad in enumerate(adicionais_db):
                    label_add = f"+{ad['nome']} R$ {ad['preco']:.2f}".replace(".", ",")
                    chip = ChipButton(
                        add_frame,
                        text=label_add,
                        on_select=lambda t, s, a=ad: on_adicional_chip(a, t, s)
                    )
                    chip.grid(row=idx // 3, column=idx % 3, padx=4, pady=3, sticky="ew")

        # Inicializar cálculo de preço no botão
        _recalcular_preco_total()

    # ── Carrinho ──────────────────────────────────────────────────────────────

    def _adicionar_ao_carrinho(self, nome: str, preco: float,
                               obs: str, categoria: str, quantidade: int = 1):
        item = {
            "nome":       nome,
            "preco_unit": preco,
            "quantidade": quantidade,
            "observacao": obs,
            "categoria":  categoria,
        }
        self._state.setdefault("carrinho", []).append(item)
        self._renderizar_carrinho()

    def _renderizar_carrinho(self):
        for w in self._cart_scroll.winfo_children():
            w.destroy()
        for item in self._state.get("carrinho", []):
            CartItem(
                self._cart_scroll, item,
                on_change=self._atualizar_subtotal,
                on_remove=self._remover_item
            ).pack(fill="x", pady=4)
        self._atualizar_subtotal()

    def _atualizar_subtotal(self):
        carrinho = self._state.get("carrinho", [])
        sub = sum(i["quantidade"] * i["preco_unit"] for i in carrinho)
        self._state["subtotal"] = sub
        self._subtotal_lbl.configure(
            text=f"Subtotal: R$ {sub:.2f}".replace(".", ",")
        )
        self._btn_avancar.configure(
            state="normal" if carrinho else "disabled"
        )

    def _remover_item(self, item: dict):
        self._state["carrinho"].remove(item)
        self._renderizar_carrinho()

    def _avancar(self):
        self._on_next()

    def on_show(self):
        """Chamado quando a tela fica visível."""
        self._renderizar_carrinho()
        self._carregar_categorias()
