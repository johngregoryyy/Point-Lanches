# ui/screen_admin.py - Painel Administrativo com 4 Abas (Cardápio, Adicionais, Taxas, Impressora Rede/USB)
# =============================================================================

import customtkinter as ctk
from database.db import (
    listar_categorias, listar_produtos,
    adicionar_produto, atualizar_produto,
    remover_produto, adicionar_categoria,
    atualizar_categoria, contar_produtos_por_categoria, remover_categoria,
    atualizar_categoria_eh_bebida,
    listar_adicionais, adicionar_adicional, atualizar_adicional, remover_adicional,
    listar_taxas, adicionar_taxa, atualizar_taxa, remover_taxa,
    get_config, set_config,
    listar_observacoes_padrao, adicionar_observacao_padrao,
    atualizar_observacao_padrao, remover_observacao_padrao,
    exportar_dados_json, importar_dados_json, get_categoria_por_nome,
    exportar_banco_sqlite, importar_banco_sqlite
)
from printer.escpos_printer import (
    test_connection_network, test_connection_usb,
    send_to_usb_printer, listar_impressoras_windows,
    CMD_INIT, CMD_CUT, CMD_FEED_LINE, _encode,
    CMD_CODEPAGE_CP850
)
from version import __version__
from services.updater import check_for_updates
from ui.components.widgets import habilitar_feedback_clique
from config import (
    COR_PRIMARIA, COR_PRIMARIA_HVR, COR_VERDE, COR_VERDE_HVR,
    COR_VERMELHO, COR_VERMELHO_HVR, COR_CINZA_BARRA,
    COR_TEXTO_SUAVE, COR_AZUL_POINT,
    PRINTER_TIPO_DEFAULT, PRINTER_IP_DEFAULT, PRINTER_USB_DEFAULT
)


class ScreenAdmin(ctk.CTkToplevel):
    """
    Janela Administrativa (Toplevel) com:
    - Aba 1: CRUD de Produtos do Cardápio
    - Aba 2: Gestão de Adicionais / Extras (criar, editar, ativar/desativar)
    - Aba 3: Gestão de Botões de Taxa de Tele-Entrega
    - Aba 4: Gestão de Observações Rápidas
    - Aba 5: Configuração da Impressora Elgin i8 (Rede TCP 9100 e Cabo USB)
    """

    def __init__(self, parent, on_refresh=None, initial_tab=None, on_ready=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("⚙  Configurações & Painel Administrativo")
        self._on_refresh = on_refresh
        self._on_ready = on_ready
        self._abas_carregadas: set[str] = set()
        self._overlay = None

        # Fixa a janela como modal e sempre à frente do PDV (impossibilita que deslize para trás)
        try:
            self.transient(parent)
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self.fechar)

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        # Adaptado para 1366x768 (altura máxima ~570px com margem para a barra de tarefas)
        mw = min(1040, sw - 30)
        mh = min(570, sh - 90)
        self.geometry(f"{mw}x{mh}")
        self.minsize(860, 480)
        self.resizable(True, True)

        # Centralizar na tela
        px = max(10, (sw - mw) // 2)
        py = max(10, (sh - mh) // 2)
        self.geometry(f"+{px}+{py}")

        self._produto_selecionado = None
        self._cat_selecionada = None
        self._adicional_selecionado = None
        self._taxa_selecionada = None
        self._obs_selecionada = None
        self._loading_timers: list[str] = []

        self._build_ui()
        if initial_tab:
            try:
                self._tabs.set(initial_tab)
            except Exception:
                pass

        # Carrega sob demanda apenas a aba ativa (zero congelamento)
        self._ao_trocar_aba()

        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except Exception:
            pass

        if hasattr(self, "_on_ready") and callable(self._on_ready):
            try:
                self._on_ready()
            except Exception:
                pass

    def definir_aba(self, tab=None):
        """Alterna para a aba indicada e carrega seus dados sob demanda."""
        if tab and hasattr(self, "_tabs"):
            try:
                self._tabs.set(tab)
                self._ao_trocar_aba()
            except Exception:
                pass

    def mostrar(self, tab=None):
        """Torna a janela visível instantaneamente com foco."""
        if tab:
            self.definir_aba(tab)
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except Exception:
            pass

    def fechar(self):
        """Fecha e destrói a janela liberando todos os recursos com segurança."""
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _ao_trocar_aba(self):
        """Carrega sob demanda o conteúdo da aba selecionada."""
        aba_atual = self._tabs.get() if hasattr(self, "_tabs") else ""
        if "Cardápio" in aba_atual:
            if "cardapio" not in self._abas_carregadas:
                self._carregar_produtos()
                self._abas_carregadas.add("cardapio")
        elif "Categorias" in aba_atual:
            if "categorias" not in self._abas_carregadas:
                if hasattr(self, "_carregar_categorias_tab"):
                    self._carregar_categorias_tab()
                self._abas_carregadas.add("categorias")
        elif "Adicionais" in aba_atual:
            if "adicionais" not in self._abas_carregadas:
                self._carregar_adicionais()
                self._abas_carregadas.add("adicionais")
        elif "Taxas" in aba_atual:
            if "taxas" not in self._abas_carregadas:
                self._carregar_taxas()
                self._abas_carregadas.add("taxas")
        elif "Obs" in aba_atual:
            if "obs" not in self._abas_carregadas:
                if hasattr(self, "_carregar_obs"):
                    self._carregar_obs()
                self._abas_carregadas.add("obs")
        elif "Impressora" in aba_atual:
            if "impressora" not in self._abas_carregadas:
                if hasattr(self, "_carregar_config"):
                    self._carregar_config()
                self._abas_carregadas.add("impressora")

    # ── Build Abas ────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header superior compacto com título e botões de Ação
        header_top = ctk.CTkFrame(self, height=44, fg_color="#181818", corner_radius=0)
        header_top.pack(fill="x")
        header_top.pack_propagate(False)

        ctk.CTkLabel(
            header_top,
            text=f"⚙  AJUSTES & CONFIGURAÇÕES (v{__version__})",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COR_PRIMARIA
        ).pack(side="left", padx=16)

        btn_atualizar = ctk.CTkButton(
            header_top,
            text="🚀  Buscar Atualizações",
            width=155, height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1E293B", hover_color="#334155",
            corner_radius=6,
            command=self._verificar_atualizacoes_manual
        )
        btn_atualizar.pack(side="right", padx=(4, 16))
        habilitar_feedback_clique(btn_atualizar, cor_flash="#334155")

        btn_recarregar = ctk.CTkButton(
            header_top,
            text="🔄  Recarregar Ajustes",
            width=150, height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1E293B", hover_color="#334155",
            corner_radius=6,
            command=self._finalizar_carregamento_ajustes
        )
        btn_recarregar.pack(side="right", padx=4)
        habilitar_feedback_clique(btn_recarregar, cor_flash="#334155")

        btn_importar = ctk.CTkButton(
            header_top,
            text="📂  Importar Backup",
            width=135, height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#334155", hover_color="#475569",
            corner_radius=6,
            command=self._importar_backup
        )
        btn_importar.pack(side="right", padx=4)
        habilitar_feedback_clique(btn_importar, cor_flash="#475569")

        # Botão de Logout da Nuvem se autenticado
        try:
            from services.supabase_auth import auth_manager
            if auth_manager.is_authenticated():
                email_usr = auth_manager.get_user_email()
                txt_nuvem = f"☁️ Sair ({email_usr[:14]}...)" if len(email_usr) > 16 else f"☁️ Sair ({email_usr})"
                btn_nuvem = ctk.CTkButton(
                    header_top,
                    text=txt_nuvem if email_usr else "☁️ Desconectar Nuvem",
                    height=30,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color="#7F1D1D", hover_color="#991B1B",
                    corner_radius=6,
                    command=self._desconectar_nuvem
                )
                btn_nuvem.pack(side="right", padx=4)
                habilitar_feedback_clique(btn_nuvem, cor_flash="#DC2626")
        except Exception:
            pass

        btn_exportar = ctk.CTkButton(
            header_top,
            text="💾  Exportar Backup",
            width=135, height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COR_PRIMARIA, hover_color=COR_PRIMARIA_HVR,
            corner_radius=6,
            command=self._exportar_backup
        )
        btn_exportar.pack(side="right", padx=4)
        habilitar_feedback_clique(btn_exportar, cor_flash=COR_VERDE)

        self._tabs = ctk.CTkTabview(self, corner_radius=10)
        self._tabs.pack(fill="both", expand=True, padx=14, pady=(8, 14))

        self._tabs.add("🍔  Cardápio")
        self._tabs.add("📂  Categorias")
        self._tabs.add("🧀  Adicionais")
        self._tabs.add("🛵  Taxas de Tele")
        self._tabs.add("📝  Obs. Rápidas")
        self._tabs.add("🖨  Impressora")

        self._build_tab_cardapio(self._tabs.tab("🍔  Cardápio"))
        self._build_tab_categorias(self._tabs.tab("📂  Categorias"))
        self._build_tab_adicionais(self._tabs.tab("🧀  Adicionais"))
        self._build_tab_taxas(self._tabs.tab("🛵  Taxas de Tele"))
        self._build_tab_observacoes(self._tabs.tab("📝  Obs. Rápidas"))
        self._build_tab_impressora(self._tabs.tab("🖨  Impressora"))

        self._tabs.configure(command=self._ao_trocar_aba)

        # Overlay de carregamento para abertura e operações assíncronas
        if not hasattr(self, "_overlay") or self._overlay is None:
            from ui.components.loading import LoadingOverlay
            self._overlay = LoadingOverlay(self, text="Carregando Ajustes...")

    def _iniciar_carregamento_ajustes(self):
        """Carrega e valida configurações da aba ativa de forma imediata."""
        self._finalizar_carregamento_ajustes()

    def _finalizar_carregamento_ajustes(self, force_all: bool = False):
        """Oculta o overlay e recarrega os dados sob demanda de forma imediata e fluida."""
        if hasattr(self, "_overlay") and self._overlay and self.winfo_exists():
            self._overlay.hide()

        if force_all:
            self._abas_carregadas.clear()

        self._ao_trocar_aba()

        if hasattr(self, "_on_ready") and callable(self._on_ready):
            try:
                self._on_ready()
            except Exception:
                pass

    def destroy(self):
        """Garante liberação do grab, cancelamento de timers e destruição segura da janela."""
        try:
            self.grab_release()
        except Exception:
            pass
        if hasattr(self, "_loading_timers"):
            for tid in self._loading_timers:
                try:
                    self.after_cancel(tid)
                except Exception:
                    pass
            self._loading_timers.clear()
        if hasattr(self, "_overlay") and self._overlay:
            try:
                self._overlay.destroy()
            except Exception:
                pass
            self._overlay = None
        if hasattr(self, "_on_ready") and callable(self._on_ready):
            try:
                self._on_ready()
            except Exception:
                pass
        super().destroy()

    def _flash_entry_salvo(self, widget, border_normal="#3A3A3A", border_flash="#10B981"):
        """Aplica borda verde de confirmação visual por 1 segundo ao salvar inline."""
        try:
            widget.configure(border_color=border_flash, border_width=2)
            widget.after(1000, lambda: widget.configure(border_color=border_normal, border_width=1) if widget.winfo_exists() else None)
        except Exception:
            pass

    # ── ABA 1: CARDÁPIO (EDIÇÃO INLINE & CADASTRO) ─────────────────────────────

    def _build_tab_cardapio(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=0)
        tab.rowconfigure(0, weight=1)

        tabela_frame = ctk.CTkFrame(tab, fg_color=COR_CINZA_BARRA, corner_radius=10)
        tabela_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tabela_frame.rowconfigure(1, weight=1)
        tabela_frame.columnconfigure(0, weight=1)

        header = ctk.CTkFrame(tabela_frame, fg_color="#1E1E1E", height=36, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=3, minsize=180)
        header.columnconfigure(1, weight=0, minsize=140)
        header.columnconfigure(2, weight=0, minsize=100)
        header.columnconfigure(3, weight=0, minsize=50)

        ctk.CTkLabel(header, text="Nome do Produto (clique para editar)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkLabel(header, text="Categoria", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=1, padx=6, pady=6, sticky="w")
        ctk.CTkLabel(header, text="Preço (R$)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=2, padx=6, pady=6, sticky="e")
        ctk.CTkLabel(header, text="Ações", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=3, padx=(4, 8), pady=6, sticky="e")

        self._tabela_scroll = ctk.CTkScrollableFrame(tabela_frame, fg_color="transparent")
        self._tabela_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._tabela_scroll.columnconfigure(0, weight=3, minsize=180)
        self._tabela_scroll.columnconfigure(1, weight=0, minsize=140)
        self._tabela_scroll.columnconfigure(2, weight=0, minsize=100)
        self._tabela_scroll.columnconfigure(3, weight=0, minsize=50)

        # Form lateral estritamente para adicionar novos produtos
        form = ctk.CTkFrame(tab, fg_color=COR_CINZA_BARRA, corner_radius=10, width=320)
        form.grid(row=0, column=1, sticky="nsew")
        form.pack_propagate(False)

        ctk.CTkLabel(form, text="ADICIONAR NOVO PRODUTO", font=ctk.CTkFont(size=13, weight="bold"), text_color=COR_TEXTO_SUAVE).pack(pady=(14, 8), padx=14, anchor="w")

        ctk.CTkLabel(form, text="Nome do Produto", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w", padx=14)
        self._f_nome = ctk.CTkEntry(form, height=36, font=ctk.CTkFont(size=13), placeholder_text="Ex: Xis Salada Especial")
        self._f_nome.pack(fill="x", padx=14, pady=(2, 6))

        ctk.CTkLabel(form, text="Descrição / Ingredientes", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w", padx=14)
        self._f_desc = ctk.CTkTextbox(form, height=65, font=ctk.CTkFont(size=12))
        self._f_desc.pack(fill="x", padx=14, pady=(2, 6))

        ctk.CTkLabel(form, text="Preço de Venda (R$)", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w", padx=14)
        self._f_preco = ctk.CTkEntry(form, height=36, font=ctk.CTkFont(size=13), placeholder_text="0.00", justify="right")
        self._f_preco.pack(fill="x", padx=14, pady=(2, 6))

        ctk.CTkLabel(form, text="Categoria", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w", padx=14)
        cats = [c["nome"] for c in listar_categorias()]
        if not cats:
            cats = ["Geral"]
        self._f_cat_var = ctk.StringVar(value=cats[0] if cats else "Geral")
        self._f_cat = ctk.CTkComboBox(form, values=cats, variable=self._f_cat_var, height=36, font=ctk.CTkFont(size=13))
        self._f_cat.pack(fill="x", padx=14, pady=(2, 14))

        btn_cadastrar = ctk.CTkButton(
            form, text="➕  Cadastrar Produto", height=42,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_VERDE, hover_color=COR_VERDE_HVR, corner_radius=8,
            command=self._cadastrar_produto
        )
        btn_cadastrar.pack(fill="x", padx=14, pady=(0, 6))
        habilitar_feedback_clique(btn_cadastrar, cor_flash="#10B981")

        btn_limpar = ctk.CTkButton(
            form, text="Limpar Campos", height=34,
            font=ctk.CTkFont(size=12),
            fg_color="#444", hover_color="#555", corner_radius=8,
            command=self._limpar_form_produto
        )
        btn_limpar.pack(fill="x", padx=14, pady=(0, 6))
        habilitar_feedback_clique(btn_limpar, cor_flash="#666")

        self._status_lbl = ctk.CTkLabel(form, text="", font=ctk.CTkFont(size=12), wraplength=280)
        self._status_lbl.pack(padx=14)

        # Dica explicativa sobre edição inline
        ctk.CTkLabel(
            form,
            text="💡 Edição Rápida:\n"
                 "    • Altere Nome ou Preço na tabela (Enter para salvar)\n"
                 "    • Troque de Categoria diretamente na setinha dropdown\n"
                 "    O sistema salva no SQLite instantaneamente!",
            font=ctk.CTkFont(size=11), text_color=COR_TEXTO_SUAVE, justify="left"
        ).pack(anchor="w", padx=14, pady=(16, 0))

    def _carregar_produtos(self):
        for w in self._tabela_scroll.winfo_children():
            w.destroy()

        produtos = listar_produtos()
        categorias_db = listar_categorias(incluir_extras=True)
        cat_nomes = [c["nome"] for c in categorias_db] if categorias_db else ["Geral"]
        if not cat_nomes:
            cat_nomes = ["Geral"]
        cat_map = {c["nome"]: c["id"] for c in categorias_db} if categorias_db else {}

        def _criar_linha_produto(i, prod):
            bg = "#272727" if i % 2 == 0 else "#222222"
            row = ctk.CTkFrame(self._tabela_scroll, fg_color=bg, corner_radius=6, height=42)
            row.pack(fill="x", pady=2, padx=2)
            row.columnconfigure(0, weight=3, minsize=180)
            row.columnconfigure(1, weight=0, minsize=140)
            row.columnconfigure(2, weight=0, minsize=100)
            row.columnconfigure(3, weight=0, minsize=50)

            # Célula 1: Nome do produto (editável inline)
            entry_nome = ctk.CTkEntry(
                row, height=30, font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#1E1E1E", border_width=1, border_color="#333333"
            )
            entry_nome.insert(0, prod["nome"])
            entry_nome.grid(row=0, column=0, padx=6, pady=4, sticky="ew")

            def _ao_mudar_nome(event, p=prod, w=entry_nome):
                novo_nome = w.get().strip()
                if not novo_nome or novo_nome == p["nome"]:
                    w.delete(0, "end")
                    w.insert(0, p["nome"])
                    return
                atualizar_produto(p["id"], novo_nome, p.get("descricao", ""), p["preco"], p["categoria_id"], p.get("ativo", 1))
                p["nome"] = novo_nome
                self._flash_entry_salvo(w, border_normal="#333333", border_flash=COR_VERDE)
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            entry_nome.bind("<Return>", _ao_mudar_nome)
            entry_nome.bind("<FocusOut>", _ao_mudar_nome)

            # Célula 2: Categoria via Dropdown (CTkOptionMenu com setinha)
            cur_cat = prod.get("categoria", "")
            if cur_cat not in cat_nomes and cat_nomes:
                cur_cat = cat_nomes[0]
            var_cat = ctk.StringVar(value=cur_cat)

            opt_cat = ctk.CTkOptionMenu(
                row, variable=var_cat, values=cat_nomes,
                width=135, height=30, font=ctk.CTkFont(size=11),
                fg_color="#222834", button_color="#333E52", button_hover_color="#475569",
                dropdown_fg_color="#1A202C", dynamic_resizing=False
            )
            opt_cat.grid(row=0, column=1, padx=6, pady=4, sticky="w")

            def _ao_mudar_cat(nova_cat, p=prod, cmap=cat_map, opt=opt_cat):
                n_id = cmap.get(nova_cat)
                if not n_id or n_id == p.get("categoria_id"):
                    return
                atualizar_produto(p["id"], p["nome"], p.get("descricao", ""), p["preco"], n_id, p.get("ativo", 1))
                p["categoria_id"] = n_id
                p["categoria"] = nova_cat
                opt.configure(fg_color=COR_VERDE)
                self.after(600, lambda: opt.configure(fg_color="#222834") if opt.winfo_exists() else None)
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            opt_cat.configure(command=_ao_mudar_cat)

            # Célula 3: Preço (editável inline)
            entry_preco = ctk.CTkEntry(
                row, width=95, height=30, font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#181818", border_width=1, border_color="#3A3A3A",
                text_color=COR_VERDE, justify="right"
            )
            entry_preco.insert(0, f"{prod['preco']:.2f}".replace(".", ","))
            entry_preco.grid(row=0, column=2, padx=6, pady=4, sticky="e")

            def _ao_mudar_preco(event, p=prod, w=entry_preco):
                val_raw = w.get().replace("R$", "").replace(" ", "").replace(",", ".").strip()
                try:
                    novo_preco = float(val_raw)
                    if novo_preco < 0:
                        raise ValueError()
                except ValueError:
                    w.delete(0, "end")
                    w.insert(0, f"{p['preco']:.2f}".replace(".", ","))
                    return
                if abs(novo_preco - p["preco"]) < 0.001:
                    w.delete(0, "end")
                    w.insert(0, f"{p['preco']:.2f}".replace(".", ","))
                    return
                atualizar_produto(p["id"], p["nome"], p.get("descricao", ""), novo_preco, p["categoria_id"], p.get("ativo", 1))
                p["preco"] = novo_preco
                w.delete(0, "end")
                w.insert(0, f"{novo_preco:.2f}".replace(".", ","))
                self._flash_entry_salvo(w, border_normal="#3A3A3A", border_flash=COR_VERDE)
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            entry_preco.bind("<Return>", _ao_mudar_preco)
            entry_preco.bind("<FocusOut>", _ao_mudar_preco)

            # Célula 4: Ação única Excluir (🗑) com diálogo de confirmação
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.grid(row=0, column=3, padx=(4, 8), sticky="e")

            btn_del = ctk.CTkButton(
                btn_frame, text="🗑", width=34, height=28,
                font=ctk.CTkFont(size=13),
                fg_color=COR_VERMELHO, hover_color=COR_VERMELHO_HVR,
                corner_radius=6, command=lambda p=prod: self._confirmar_remocao(p)
            )
            btn_del.pack(side="left")
            habilitar_feedback_clique(btn_del, cor_flash="#DC2626")

        # Renderização progressiva em lotes de 15 para abertura fluida (<250ms)
        def _render_lote(inicio=0):
            if not self.winfo_exists() or not hasattr(self, "_tabela_scroll") or not self._tabela_scroll.winfo_exists():
                return
            fim = min(inicio + 15, len(produtos))
            for i in range(inicio, fim):
                _criar_linha_produto(i, produtos[i])
            if fim < len(produtos):
                tid = self.after(10, lambda: _render_lote(fim))
                if hasattr(self, "_loading_timers"):
                    self._loading_timers.append(tid)

        _render_lote(0)

    def _cadastrar_produto(self):
        nome = self._f_nome.get().strip()
        desc = self._f_desc.get("1.0", "end").strip()
        preco_str = self._f_preco.get().strip().replace(",", ".")
        cat_nome = self._f_cat_var.get()

        if not nome:
            self._status_lbl.configure(text="⚠ Nome do produto é obrigatório!", text_color=COR_VERMELHO)
            return
        try:
            preco = float(preco_str)
            if preco < 0:
                raise ValueError()
        except ValueError:
            self._status_lbl.configure(text="⚠ Preço inválido!", text_color=COR_VERMELHO)
            return

        cats = {c["nome"]: c["id"] for c in listar_categorias()}
        cat_id = cats.get(cat_nome)
        if not cat_id:
            self._status_lbl.configure(text="⚠ Selecione uma categoria!", text_color=COR_VERMELHO)
            return

        adicionar_produto(cat_id, nome, desc, preco)
        self._limpar_form_produto()
        self._carregar_produtos()
        if hasattr(self, "_carregar_categorias_tab"):
            self._carregar_categorias_tab()
        if self._on_refresh:
            try:
                self._on_refresh()
            except Exception:
                pass
        self._status_lbl.configure(text=f"✅ '{nome}' cadastrado!", text_color=COR_VERDE)

    def _limpar_form_produto(self):
        self._f_nome.delete(0, "end")
        self._f_desc.delete("1.0", "end")
        self._f_preco.delete(0, "end")
        self._status_lbl.configure(text="")

    def _confirmar_remocao(self, prod: dict):
        def _exec():
            remover_produto(prod["id"])
            self._carregar_produtos()
            if hasattr(self, "_carregar_categorias_tab"):
                self._carregar_categorias_tab()
            if self._on_refresh:
                try:
                    self._on_refresh()
                except Exception:
                    pass

        self._confirmar_dialogo(
            "Excluir Produto",
            f"Deseja realmente excluir o produto '{prod['nome']}'?\n\nEle não aparecerá mais no cardápio.",
            _exec,
            icone="🗑"
        )

    # ── ABA 1B: GESTÃO DEDICADA DE CATEGORIAS (CRUD COMPLETO) ─────────────────

    def _build_tab_categorias(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=0)
        tab.rowconfigure(0, weight=1)

        tabela_frame = ctk.CTkFrame(tab, fg_color=COR_CINZA_BARRA, corner_radius=10)
        tabela_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tabela_frame.rowconfigure(1, weight=1)
        tabela_frame.columnconfigure(0, weight=1)

        header = ctk.CTkFrame(tabela_frame, fg_color="#1E1E1E", height=36, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=0, minsize=55)
        header.columnconfigure(1, weight=3, minsize=160)
        header.columnconfigure(2, weight=0, minsize=120)
        header.columnconfigure(3, weight=1, minsize=110)
        header.columnconfigure(4, weight=0, minsize=50)

        ctk.CTkLabel(header, text="Ordem", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=0, padx=6, pady=6)
        ctk.CTkLabel(header, text="Nome da Categoria (clique para editar)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=1, padx=6, pady=6, sticky="w")
        ctk.CTkLabel(header, text="Tipo / Bebida", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=2, padx=6, pady=6, sticky="w")
        ctk.CTkLabel(header, text="Produtos Vinculados", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=3, padx=6, pady=6, sticky="w")
        ctk.CTkLabel(header, text="Ações", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=4, padx=(4, 8), pady=6, sticky="e")

        self._cat_scroll = ctk.CTkScrollableFrame(tabela_frame, fg_color="transparent")
        self._cat_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._cat_scroll.columnconfigure(0, weight=0, minsize=55)
        self._cat_scroll.columnconfigure(1, weight=3, minsize=160)
        self._cat_scroll.columnconfigure(2, weight=0, minsize=120)
        self._cat_scroll.columnconfigure(3, weight=1, minsize=110)
        self._cat_scroll.columnconfigure(4, weight=0, minsize=50)

        # Form lateral categorias (focado estritamente em novos cadastros)
        form_cat = ctk.CTkFrame(tab, fg_color=COR_CINZA_BARRA, corner_radius=10, width=320)
        form_cat.grid(row=0, column=1, sticky="nsew")
        form_cat.pack_propagate(False)

        ctk.CTkLabel(form_cat, text="ADICIONAR NOVA CATEGORIA", font=ctk.CTkFont(size=13, weight="bold"), text_color=COR_TEXTO_SUAVE).pack(pady=(14, 8), padx=14, anchor="w")

        ctk.CTkLabel(form_cat, text="Nome da Categoria", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w", padx=14)
        self._cat_nome = ctk.CTkEntry(form_cat, height=36, font=ctk.CTkFont(size=13), placeholder_text="Ex: Lanches, Bebidas...")
        self._cat_nome.pack(fill="x", padx=14, pady=(2, 8))

        ctk.CTkLabel(form_cat, text="Ordem de Exibição", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w", padx=14)
        self._cat_ordem = ctk.CTkEntry(form_cat, height=36, font=ctk.CTkFont(size=13), placeholder_text="0 (Prioridade na fila)")
        self._cat_ordem.pack(fill="x", padx=14, pady=(2, 10))

        self._cat_eh_bebida_var = ctk.BooleanVar(value=False)
        self._cat_eh_bebida_switch = ctk.CTkSwitch(
            form_cat,
            text="É Categoria de Bebida?\n(oculta adicionais e obs. rápidas)",
            variable=self._cat_eh_bebida_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            progress_color=COR_VERDE
        )
        self._cat_eh_bebida_switch.pack(anchor="w", padx=14, pady=(4, 14))

        btn_cadastrar_cat = ctk.CTkButton(
            form_cat, text="➕  Cadastrar Categoria", height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_VERDE, hover_color=COR_VERDE_HVR, corner_radius=8,
            command=self._cadastrar_categoria
        )
        btn_cadastrar_cat.pack(fill="x", padx=14, pady=(0, 6))
        habilitar_feedback_clique(btn_cadastrar_cat, cor_flash="#10B981")

        btn_limpar_cat = ctk.CTkButton(
            form_cat, text="Limpar Campos", height=36,
            font=ctk.CTkFont(size=12),
            fg_color="#444", hover_color="#555", corner_radius=8,
            command=self._limpar_form_categoria
        )
        btn_limpar_cat.pack(fill="x", padx=14, pady=(0, 6))
        habilitar_feedback_clique(btn_limpar_cat, cor_flash="#666666")

        self._cat_status_lbl = ctk.CTkLabel(form_cat, text="", font=ctk.CTkFont(size=12), wraplength=280)
        self._cat_status_lbl.pack(padx=14)

        # Dica explicativa
        ctk.CTkLabel(
            form_cat,
            text="💡 Dica sobre Categorias:\n"
                 "    • Chave 'Bebida' ligada: oculta adicionais e\n"
                 "      observações rápidas no pop-up do item.\n"
                 "    • Altere Nome, Ordem ou Tipo direto na tabela.\n"
                 "    • A ordem 0 aparece primeiro no cardápio.",
            font=ctk.CTkFont(size=11), text_color=COR_TEXTO_SUAVE, justify="left"
        ).pack(anchor="w", padx=14, pady=(12, 0))

    def _carregar_categorias_tab(self):
        if not hasattr(self, "_cat_scroll") or not self._cat_scroll.winfo_exists():
            return
        for w in self._cat_scroll.winfo_children():
            w.destroy()

        categorias = listar_categorias(incluir_extras=True)
        for i, cat in enumerate(categorias):
            bg = "#272727" if i % 2 == 0 else "#222222"
            row = ctk.CTkFrame(self._cat_scroll, fg_color=bg, corner_radius=6, height=42)
            row.pack(fill="x", pady=2, padx=2)
            row.columnconfigure(0, weight=0, minsize=55)
            row.columnconfigure(1, weight=3, minsize=160)
            row.columnconfigure(2, weight=0, minsize=120)
            row.columnconfigure(3, weight=1, minsize=110)
            row.columnconfigure(4, weight=0, minsize=50)

            # Célula 0: Ordem (editável inline)
            entry_ordem = ctk.CTkEntry(
                row, width=50, height=30, font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#181818", border_width=1, border_color="#3A3A3A",
                justify="center"
            )
            entry_ordem.insert(0, str(cat.get("ordem", 0)))
            entry_ordem.grid(row=0, column=0, padx=6, pady=4)

            def _ao_mudar_ordem(event, c=cat, w=entry_ordem):
                val_raw = w.get().strip()
                try:
                    nova_ordem = int(val_raw) if val_raw else 0
                except ValueError:
                    w.delete(0, "end")
                    w.insert(0, str(c.get("ordem", 0)))
                    return
                if nova_ordem == c.get("ordem", 0):
                    return
                atualizar_categoria(c["id"], c["nome"], nova_ordem)
                c["ordem"] = nova_ordem
                self._flash_entry_salvo(w, border_normal="#3A3A3A", border_flash=COR_VERDE)
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            entry_ordem.bind("<Return>", _ao_mudar_ordem)
            entry_ordem.bind("<FocusOut>", _ao_mudar_ordem)

            # Célula 1: Nome da Categoria (editável inline)
            entry_nome = ctk.CTkEntry(
                row, height=30, font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#1E1E1E", border_width=1, border_color="#333333"
            )
            entry_nome.insert(0, cat["nome"])
            entry_nome.grid(row=0, column=1, padx=6, pady=4, sticky="ew")

            def _ao_mudar_nome_cat(event, c=cat, w=entry_nome):
                novo_nome = w.get().strip()
                if not novo_nome or novo_nome == c["nome"]:
                    w.delete(0, "end")
                    w.insert(0, c["nome"])
                    return
                atualizar_categoria(c["id"], novo_nome, c.get("ordem", 0))
                c["nome"] = novo_nome
                self._flash_entry_salvo(w, border_normal="#333333", border_flash=COR_VERDE)
                self._atualizar_combobox_categorias()
                if hasattr(self, "_carregar_produtos"):
                    self._carregar_produtos()
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            entry_nome.bind("<Return>", _ao_mudar_nome_cat)
            entry_nome.bind("<FocusOut>", _ao_mudar_nome_cat)

            # Célula 2: Switch Tipo de Categoria (Bebida vs Comida)
            var_bebida = ctk.BooleanVar(value=bool(cat.get("eh_bebida", 0)))
            switch_bebida = ctk.CTkSwitch(
                row,
                text="🥤 Bebida" if var_bebida.get() else "🍔 Comida",
                variable=var_bebida,
                width=95, height=26,
                font=ctk.CTkFont(size=11, weight="bold"),
                progress_color=COR_VERDE
            )
            def _ao_toggle_bebida(c=cat, v=var_bebida, sw=switch_bebida):
                novo_val = 1 if v.get() else 0
                sw.configure(text="🥤 Bebida" if novo_val else "🍔 Comida")
                atualizar_categoria_eh_bebida(c["id"], novo_val)
                c["eh_bebida"] = novo_val
                if hasattr(self, "_carregar_produtos"):
                    self._carregar_produtos()
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            switch_bebida.configure(command=_ao_toggle_bebida)
            switch_bebida.grid(row=0, column=2, padx=6, pady=4, sticky="w")

            # Célula 3: Produtos Vinculados
            qtd_prods = contar_produtos_por_categoria(cat["id"])
            cor_qtd = COR_VERDE if qtd_prods > 0 else COR_TEXTO_SUAVE
            txt_qtd = f"{qtd_prods} produto(s)" if qtd_prods > 0 else "Nenhum"
            ctk.CTkLabel(row, text=txt_qtd, font=ctk.CTkFont(size=11), text_color=cor_qtd, anchor="w").grid(row=0, column=3, padx=6, sticky="w")

            # Célula 4: Ação única Excluir (🗑) com diálogo e validação relacional
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.grid(row=0, column=4, padx=(4, 8), sticky="e")
            btn_del = ctk.CTkButton(
                btn_frame, text="🗑", width=34, height=28,
                font=ctk.CTkFont(size=13),
                fg_color=COR_VERMELHO, hover_color=COR_VERMELHO_HVR,
                corner_radius=6, command=lambda c=cat: self._tentar_excluir_categoria(c)
            )
            btn_del.pack(side="left")
            habilitar_feedback_clique(btn_del, cor_flash="#DC2626")

    def _cadastrar_categoria(self):
        nome = self._cat_nome.get().strip()
        ordem_str = self._cat_ordem.get().strip()
        eh_bebida = 1 if self._cat_eh_bebida_var.get() else 0

        if not nome:
            self._cat_status_lbl.configure(text="⚠ Nome da categoria é obrigatório!", text_color=COR_VERMELHO)
            return

        try:
            ordem = int(ordem_str) if ordem_str else 0
        except ValueError:
            ordem = 0

        adicionar_categoria(nome, ordem, eh_bebida)
        self._limpar_form_categoria()
        self._carregar_categorias_tab()
        self._atualizar_combobox_categorias()
        if hasattr(self, "_carregar_produtos"):
            self._carregar_produtos()
        if self._on_refresh:
            try:
                self._on_refresh()
            except Exception:
                pass
        self._cat_status_lbl.configure(text=f"✅ '{nome}' cadastrada!", text_color=COR_VERDE)

    def _limpar_form_categoria(self):
        self._cat_nome.delete(0, "end")
        self._cat_ordem.delete(0, "end")
        self._cat_eh_bebida_var.set(False)
        self._cat_status_lbl.configure(text="")
        self._cat_status_lbl.configure(text="")

    def _atualizar_combobox_categorias(self):
        if hasattr(self, "_f_cat"):
            cats = [c["nome"] for c in listar_categorias()]
            self._f_cat.configure(values=cats)
            if self._f_cat_var.get() not in cats and cats:
                self._f_cat_var.set(cats[0])

    def _tentar_excluir_categoria(self, cat: dict):
        cat_id = cat.get("id")
        nome = cat.get("nome", "")
        # Validação de integridade relacional
        qtd = contar_produtos_por_categoria(cat_id)
        if qtd > 0:
            self._mostrar_alerta(
                "Exclusão Bloqueada",
                f"Não é possível excluir a categoria '{nome}'!\n\nExistem {qtd} produto(s) vinculado(s) a esta categoria.\n\nMova ou exclua os produtos vinculados antes de remover a categoria.",
                icone="🚫"
            )
            return

        def _realizar_exclusao():
            remover_categoria(cat_id)
            self._limpar_categoria()
            self._carregar_categorias_tab()
            self._atualizar_combobox_categorias()
            if self._on_refresh:
                try:
                    self._on_refresh()
                except Exception:
                    pass

        self._confirmar_dialogo(
            "Confirmar Exclusão",
            f"Deseja realmente excluir a categoria '{nome}'?\n\nEsta ação removerá a categoria do sistema.",
            _realizar_exclusao,
            icone="🗑"
        )

    def _confirmar_dialogo(self, titulo: str, mensagem: str, on_confirmar, icone: str = "⚠️"):
        win = ctk.CTkToplevel(self)
        win.title(titulo)
        win.geometry("440x230")
        win.grab_set()
        win.resizable(False, False)

        win.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - 440) // 2
        py = self.winfo_rooty() + (self.winfo_height() - 230) // 2
        win.geometry(f"+{max(0, px)}+{max(0, py)}")

        ctk.CTkLabel(win, text=icone, font=ctk.CTkFont(size=40)).pack(pady=(14, 2))
        ctk.CTkLabel(win, text=titulo, font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(2, 6))
        ctk.CTkLabel(win, text=mensagem, font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE, wraplength=400, justify="center").pack(padx=20, pady=(0, 14))

        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(pady=(0, 14))

        def _exec():
            win.destroy()
            on_confirmar()

        btn_cancel = ctk.CTkButton(
            btns, text="Cancelar", width=110, height=36,
            font=ctk.CTkFont(size=12),
            fg_color="#444", hover_color="#555",
            corner_radius=8, command=win.destroy
        )
        btn_cancel.pack(side="left", padx=6)
        habilitar_feedback_clique(btn_cancel, cor_flash="#666666")

        btn_sim = ctk.CTkButton(
            btns, text="Sim, Excluir", width=120, height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COR_VERMELHO, hover_color=COR_VERMELHO_HVR,
            corner_radius=8, command=_exec
        )
        btn_sim.pack(side="left", padx=6)
        habilitar_feedback_clique(btn_sim, cor_flash="#DC2626")

    # ── ABA 2: ADICIONAIS / EXTRAS ───────────────────────────────────────────

    def _build_tab_adicionais(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=0)
        tab.rowconfigure(0, weight=1)

        tabela_frame = ctk.CTkFrame(tab, fg_color=COR_CINZA_BARRA, corner_radius=10)
        tabela_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tabela_frame.rowconfigure(1, weight=1)
        tabela_frame.columnconfigure(0, weight=1)

        header = ctk.CTkFrame(tabela_frame, fg_color="#1E1E1E", height=36, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=3, minsize=180)
        header.columnconfigure(1, weight=0, minsize=110)
        header.columnconfigure(2, weight=0, minsize=100)
        header.columnconfigure(3, weight=0, minsize=50)

        ctk.CTkLabel(header, text="Adicional / Extra (clique para editar)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkLabel(header, text="Acréscimo (R$)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=1, padx=6, pady=6, sticky="e")
        ctk.CTkLabel(header, text="Ativo", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=2, padx=8, pady=6, sticky="w")
        ctk.CTkLabel(header, text="Ações", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=3, padx=(4, 8), pady=6, sticky="e")

        self._adicionais_scroll = ctk.CTkScrollableFrame(tabela_frame, fg_color="transparent")
        self._adicionais_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._adicionais_scroll.columnconfigure(0, weight=3, minsize=180)
        self._adicionais_scroll.columnconfigure(1, weight=0, minsize=110)
        self._adicionais_scroll.columnconfigure(2, weight=0, minsize=100)
        self._adicionais_scroll.columnconfigure(3, weight=0, minsize=50)

        # Form lateral adicionais (focado estritamente em novos cadastros)
        form_ad = ctk.CTkFrame(tab, fg_color=COR_CINZA_BARRA, corner_radius=10, width=320)
        form_ad.grid(row=0, column=1, sticky="nsew")
        form_ad.pack_propagate(False)

        ctk.CTkLabel(form_ad, text="ADICIONAR NOVO ADICIONAL", font=ctk.CTkFont(size=13, weight="bold"), text_color=COR_TEXTO_SUAVE).pack(pady=(14, 8), padx=14, anchor="w")

        ctk.CTkLabel(form_ad, text="Nome do Adicional", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w", padx=14)
        self._ad_nome = ctk.CTkEntry(form_ad, height=36, font=ctk.CTkFont(size=13), placeholder_text="Ex: Bacon, Queijo Extra...")
        self._ad_nome.pack(fill="x", padx=14, pady=(2, 8))

        ctk.CTkLabel(form_ad, text="Preço / Acréscimo (R$)", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w", padx=14)
        self._ad_preco = ctk.CTkEntry(form_ad, height=36, font=ctk.CTkFont(size=13), placeholder_text="3.00", justify="right")
        self._ad_preco.pack(fill="x", padx=14, pady=(2, 14))

        btn_cadastrar_ad = ctk.CTkButton(
            form_ad, text="➕  Cadastrar Adicional", height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_VERDE, hover_color=COR_VERDE_HVR, corner_radius=8,
            command=self._cadastrar_adicional
        )
        btn_cadastrar_ad.pack(fill="x", padx=14, pady=(0, 6))
        habilitar_feedback_clique(btn_cadastrar_ad, cor_flash="#10B981")

        btn_limpar_ad = ctk.CTkButton(
            form_ad, text="Limpar Campos", height=36,
            font=ctk.CTkFont(size=12),
            fg_color="#444", hover_color="#555", corner_radius=8,
            command=self._limpar_form_adicional
        )
        btn_limpar_ad.pack(fill="x", padx=14, pady=(0, 6))
        habilitar_feedback_clique(btn_limpar_ad, cor_flash="#666666")

        self._ad_status_lbl = ctk.CTkLabel(form_ad, text="", font=ctk.CTkFont(size=12), wraplength=280)
        self._ad_status_lbl.pack(padx=14, pady=(8, 0))

        ctk.CTkLabel(
            form_ad,
            text="💡 Edite nomes e valores diretamente\n"
                 "    na tabela ao lado (Enter para salvar).\n"
                 "    Alterne o status no switch de cada linha.",
            font=ctk.CTkFont(size=11), text_color=COR_TEXTO_SUAVE, justify="left"
        ).pack(anchor="w", padx=14, pady=(16, 0))

    def _carregar_adicionais(self):
        for w in self._adicionais_scroll.winfo_children():
            w.destroy()

        adicionais = listar_adicionais(apenas_ativos=False)
        for i, ad in enumerate(adicionais):
            bg = "#272727" if i % 2 == 0 else "#222222"
            row = ctk.CTkFrame(self._adicionais_scroll, fg_color=bg, corner_radius=6, height=42)
            row.pack(fill="x", pady=2, padx=2)
            row.columnconfigure(0, weight=3, minsize=180)
            row.columnconfigure(1, weight=0, minsize=110)
            row.columnconfigure(2, weight=0, minsize=100)
            row.columnconfigure(3, weight=0, minsize=50)

            # Célula 1: Nome do adicional (editável inline)
            entry_nome = ctk.CTkEntry(
                row, height=30, font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#1E1E1E", border_width=1, border_color="#333333"
            )
            entry_nome.insert(0, ad["nome"])
            entry_nome.grid(row=0, column=0, padx=6, pady=4, sticky="ew")

            def _ao_mudar_nome(event, a=ad, w=entry_nome):
                novo_nome = w.get().strip()
                if not novo_nome or novo_nome == a["nome"]:
                    w.delete(0, "end")
                    w.insert(0, a["nome"])
                    return
                atualizar_adicional(a["id"], novo_nome, a["preco"], a.get("ativo", 1))
                a["nome"] = novo_nome
                self._flash_entry_salvo(w, border_normal="#333333", border_flash=COR_VERDE)
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            entry_nome.bind("<Return>", _ao_mudar_nome)
            entry_nome.bind("<FocusOut>", _ao_mudar_nome)

            # Célula 2: Preço / Acréscimo (editável inline)
            entry_preco = ctk.CTkEntry(
                row, width=95, height=30, font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#181818", border_width=1, border_color="#3A3A3A",
                text_color=COR_VERDE, justify="right"
            )
            entry_preco.insert(0, f"{ad['preco']:.2f}".replace(".", ","))
            entry_preco.grid(row=0, column=1, padx=6, pady=4, sticky="e")

            def _ao_mudar_preco(event, a=ad, w=entry_preco):
                val_raw = w.get().replace("R$", "").replace(" ", "").replace(",", ".").strip()
                try:
                    novo_preco = float(val_raw)
                    if novo_preco < 0:
                        raise ValueError()
                except ValueError:
                    w.delete(0, "end")
                    w.insert(0, f"{a['preco']:.2f}".replace(".", ","))
                    return
                if abs(novo_preco - a["preco"]) < 0.001:
                    w.delete(0, "end")
                    w.insert(0, f"{a['preco']:.2f}".replace(".", ","))
                    return
                atualizar_adicional(a["id"], a["nome"], novo_preco, a.get("ativo", 1))
                a["preco"] = novo_preco
                w.delete(0, "end")
                w.insert(0, f"{novo_preco:.2f}".replace(".", ","))
                self._flash_entry_salvo(w, border_normal="#3A3A3A", border_flash=COR_VERDE)
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            entry_preco.bind("<Return>", _ao_mudar_preco)
            entry_preco.bind("<FocusOut>", _ao_mudar_preco)

            # Célula 3: Status Ativo/Inativo (switch direto na linha)
            var_ativo = ctk.BooleanVar(value=bool(ad.get("ativo", 1)))
            switch_ativo = ctk.CTkSwitch(
                row, text="Ativo" if var_ativo.get() else "Inativo",
                variable=var_ativo,
                font=ctk.CTkFont(size=11, weight="bold"),
                progress_color=COR_VERDE
            )
            switch_ativo.grid(row=0, column=2, padx=8, pady=4, sticky="w")

            def _ao_toggle_ad(a=ad, var=var_ativo, sw=switch_ativo):
                st = 1 if var.get() else 0
                atualizar_adicional(a["id"], a["nome"], a["preco"], st)
                a["ativo"] = st
                sw.configure(text="Ativo" if st else "Inativo")
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            switch_ativo.configure(command=_ao_toggle_ad)

            # Célula 4: Ação única Excluir (🗑) com confirmação
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.grid(row=0, column=3, padx=(4, 8), sticky="e")

            btn_del = ctk.CTkButton(
                btn_frame, text="🗑", width=34, height=28,
                font=ctk.CTkFont(size=13),
                fg_color=COR_VERMELHO, hover_color=COR_VERMELHO_HVR,
                corner_radius=6, command=lambda a=ad: self._confirmar_remocao_adicional(a)
            )
            btn_del.pack(side="left")
            habilitar_feedback_clique(btn_del, cor_flash="#DC2626")

    def _cadastrar_adicional(self):
        nome = self._ad_nome.get().strip()
        preco_str = self._ad_preco.get().strip().replace(",", ".")

        if not nome:
            self._ad_status_lbl.configure(text="⚠ Nome é obrigatório!", text_color=COR_VERMELHO)
            return
        try:
            preco = float(preco_str)
            if preco < 0:
                raise ValueError()
        except ValueError:
            self._ad_status_lbl.configure(text="⚠ Preço inválido!", text_color=COR_VERMELHO)
            return

        adicionar_adicional(nome, preco)
        self._limpar_form_adicional()
        self._carregar_adicionais()
        if self._on_refresh:
            try:
                self._on_refresh()
            except Exception:
                pass
        self._ad_status_lbl.configure(text=f"✅ '{nome}' cadastrado!", text_color=COR_VERDE)

    def _limpar_form_adicional(self):
        self._ad_nome.delete(0, "end")
        self._ad_preco.delete(0, "end")
        self._ad_status_lbl.configure(text="")

    def _confirmar_remocao_adicional(self, ad: dict):
        def _exec():
            remover_adicional(ad["id"])
            self._carregar_adicionais()
            if self._on_refresh:
                try:
                    self._on_refresh()
                except Exception:
                    pass

        self._confirmar_dialogo(
            "Excluir Adicional",
            f"Deseja realmente excluir o adicional '{ad['nome']}'?\n\nEle não aparecerá mais como opção no cardápio.",
            _exec,
            icone="🗑"
        )

    # ── ABA 3: TAXAS DE TELE-ENTREGA ──────────────────────────────────────────

    def _build_tab_taxas(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=0)
        tab.rowconfigure(0, weight=1)

        tabela_frame = ctk.CTkFrame(tab, fg_color=COR_CINZA_BARRA, corner_radius=10)
        tabela_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tabela_frame.rowconfigure(1, weight=1)
        tabela_frame.columnconfigure(0, weight=1)

        header = ctk.CTkFrame(tabela_frame, fg_color="#1E1E1E", height=36, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=0, minsize=110)
        header.columnconfigure(1, weight=3, minsize=180)
        header.columnconfigure(2, weight=0, minsize=100)
        header.columnconfigure(3, weight=0, minsize=50)

        ctk.CTkLabel(header, text="Valor (R$)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=0, padx=6, pady=6, sticky="e")
        ctk.CTkLabel(header, text="Rótulo no Botão (clique para editar)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=1, padx=6, pady=6, sticky="w")
        ctk.CTkLabel(header, text="Ativo", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=2, padx=8, pady=6, sticky="w")
        ctk.CTkLabel(header, text="Ações", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=3, padx=(4, 8), pady=6, sticky="e")

        self._taxas_scroll = ctk.CTkScrollableFrame(tabela_frame, fg_color="transparent")
        self._taxas_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._taxas_scroll.columnconfigure(0, weight=0, minsize=110)
        self._taxas_scroll.columnconfigure(1, weight=3, minsize=180)
        self._taxas_scroll.columnconfigure(2, weight=0, minsize=100)
        self._taxas_scroll.columnconfigure(3, weight=0, minsize=50)

        # Form lateral taxas (focado estritamente em novos cadastros)
        form_tx = ctk.CTkFrame(tab, fg_color=COR_CINZA_BARRA, corner_radius=10, width=320)
        form_tx.grid(row=0, column=1, sticky="nsew")
        form_tx.pack_propagate(False)

        ctk.CTkLabel(form_tx, text="ADICIONAR NOVA TAXA", font=ctk.CTkFont(size=13, weight="bold"), text_color=COR_TEXTO_SUAVE).pack(pady=(14, 8), padx=14, anchor="w")

        ctk.CTkLabel(form_tx, text="Valor Numérico (R$)", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w", padx=14)
        self._tx_valor = ctk.CTkEntry(form_tx, height=36, font=ctk.CTkFont(size=13), placeholder_text="7.00", justify="right")
        self._tx_valor.pack(fill="x", padx=14, pady=(2, 8))

        ctk.CTkLabel(form_tx, text="Rótulo no Botão", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w", padx=14)
        self._tx_label = ctk.CTkEntry(form_tx, height=36, font=ctk.CTkFont(size=13), placeholder_text="Ex: R$ 7 ou Grátis")
        self._tx_label.pack(fill="x", padx=14, pady=(2, 14))

        btn_cadastrar_tx = ctk.CTkButton(
            form_tx, text="➕  Cadastrar Taxa", height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_VERDE, hover_color=COR_VERDE_HVR, corner_radius=8,
            command=self._cadastrar_taxa
        )
        btn_cadastrar_tx.pack(fill="x", padx=14, pady=(0, 6))
        habilitar_feedback_clique(btn_cadastrar_tx, cor_flash="#10B981")

        btn_limpar_tx = ctk.CTkButton(
            form_tx, text="Limpar Campos", height=36,
            font=ctk.CTkFont(size=12),
            fg_color="#444", hover_color="#555", corner_radius=8,
            command=self._limpar_form_taxa
        )
        btn_limpar_tx.pack(fill="x", padx=14, pady=(0, 6))
        habilitar_feedback_clique(btn_limpar_tx, cor_flash="#666666")

        self._tx_status_lbl = ctk.CTkLabel(form_tx, text="", font=ctk.CTkFont(size=12), wraplength=280)
        self._tx_status_lbl.pack(padx=14, pady=(8, 0))

        ctk.CTkLabel(
            form_tx,
            text="💡 Edite valores e rótulos diretamente\n"
                 "    na tabela ao lado (Enter para salvar).\n"
                 "    Alterne o status no switch de cada linha.",
            font=ctk.CTkFont(size=11), text_color=COR_TEXTO_SUAVE, justify="left"
        ).pack(anchor="w", padx=14, pady=(16, 0))

    def _carregar_taxas(self):
        for w in self._taxas_scroll.winfo_children():
            w.destroy()

        taxas = listar_taxas(apenas_ativas=False)
        for i, tx in enumerate(taxas):
            bg = "#272727" if i % 2 == 0 else "#222222"
            row = ctk.CTkFrame(self._taxas_scroll, fg_color=bg, corner_radius=6, height=42)
            row.pack(fill="x", pady=2, padx=2)
            row.columnconfigure(0, weight=0, minsize=110)
            row.columnconfigure(1, weight=3, minsize=180)
            row.columnconfigure(2, weight=0, minsize=100)
            row.columnconfigure(3, weight=0, minsize=50)

            # Célula 1: Valor Numérico (editável inline)
            entry_valor = ctk.CTkEntry(
                row, width=85, height=30, font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#181818", border_width=1, border_color="#3A3A3A",
                text_color=COR_VERDE, justify="right"
            )
            entry_valor.insert(0, f"{tx['valor']:.2f}".replace(".", ","))
            entry_valor.grid(row=0, column=0, padx=6, pady=4, sticky="e")

            def _ao_mudar_valor(event, t=tx, w=entry_valor):
                val_raw = w.get().replace("R$", "").replace(" ", "").replace(",", ".").strip()
                try:
                    novo_val = float(val_raw)
                    if novo_val < 0:
                        raise ValueError()
                except ValueError:
                    w.delete(0, "end")
                    w.insert(0, f"{t['valor']:.2f}".replace(".", ","))
                    return
                if abs(novo_val - t["valor"]) < 0.001:
                    w.delete(0, "end")
                    w.insert(0, f"{t['valor']:.2f}".replace(".", ","))
                    return
                atualizar_taxa(t["id"], novo_val, t["label"], t.get("ativo", 1))
                t["valor"] = novo_val
                w.delete(0, "end")
                w.insert(0, f"{novo_val:.2f}".replace(".", ","))
                self._flash_entry_salvo(w, border_normal="#3A3A3A", border_flash=COR_VERDE)
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            entry_valor.bind("<Return>", _ao_mudar_valor)
            entry_valor.bind("<FocusOut>", _ao_mudar_valor)

            # Célula 2: Rótulo / Texto no Botão (editável inline)
            entry_label = ctk.CTkEntry(
                row, height=30, font=ctk.CTkFont(size=12),
                fg_color="#1E1E1E", border_width=1, border_color="#333333"
            )
            entry_label.insert(0, tx["label"])
            entry_label.grid(row=0, column=1, padx=6, pady=4, sticky="ew")

            def _ao_mudar_label(event, t=tx, w=entry_label):
                novo_label = w.get().strip()
                if not novo_label or novo_label == t["label"]:
                    w.delete(0, "end")
                    w.insert(0, t["label"])
                    return
                atualizar_taxa(t["id"], t["valor"], novo_label, t.get("ativo", 1))
                t["label"] = novo_label
                self._flash_entry_salvo(w, border_normal="#333333", border_flash=COR_VERDE)
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            entry_label.bind("<Return>", _ao_mudar_label)
            entry_label.bind("<FocusOut>", _ao_mudar_label)

            # Célula 3: Status Ativo/Inativo (switch direto na linha)
            var_ativo = ctk.BooleanVar(value=bool(tx.get("ativo", 1)))
            switch_ativo = ctk.CTkSwitch(
                row, text="Ativo" if var_ativo.get() else "Inativo",
                variable=var_ativo,
                font=ctk.CTkFont(size=11, weight="bold"),
                progress_color=COR_VERDE
            )
            switch_ativo.grid(row=0, column=2, padx=8, pady=4, sticky="w")

            def _ao_toggle_tx(t=tx, var=var_ativo, sw=switch_ativo):
                st = 1 if var.get() else 0
                atualizar_taxa(t["id"], t["valor"], t["label"], st)
                t["ativo"] = st
                sw.configure(text="Ativo" if st else "Inativo")
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            switch_ativo.configure(command=_ao_toggle_tx)

            # Célula 4: Ação única Excluir (🗑) com confirmação
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.grid(row=0, column=3, padx=(4, 8), sticky="e")

            btn_del = ctk.CTkButton(
                btn_frame, text="🗑", width=34, height=28,
                font=ctk.CTkFont(size=13),
                fg_color=COR_VERMELHO, hover_color=COR_VERMELHO_HVR,
                corner_radius=6, command=lambda t=tx: self._confirmar_remocao_taxa(t)
            )
            btn_del.pack(side="left")
            habilitar_feedback_clique(btn_del, cor_flash="#DC2626")

    def _cadastrar_taxa(self):
        val_str = self._tx_valor.get().strip().replace(",", ".")
        label = self._tx_label.get().strip()

        try:
            valor = float(val_str)
            if valor < 0:
                raise ValueError()
        except ValueError:
            self._tx_status_lbl.configure(text="⚠ Valor numérico inválido!", text_color=COR_VERMELHO)
            return

        if not label:
            label = "Grátis" if valor == 0 else f"R$ {int(valor) if valor == int(valor) else valor}"

        adicionar_taxa(valor, label, 1)
        self._limpar_form_taxa()
        self._carregar_taxas()
        if self._on_refresh:
            try:
                self._on_refresh()
            except Exception:
                pass
        self._tx_status_lbl.configure(text=f"✅ Botão '{label}' adicionado!", text_color=COR_VERDE)

    def _limpar_form_taxa(self):
        self._tx_valor.delete(0, "end")
        self._tx_label.delete(0, "end")
        self._tx_status_lbl.configure(text="")

    def _confirmar_remocao_taxa(self, tx: dict):
        def _exec():
            remover_taxa(tx["id"])
            self._carregar_taxas()
            if self._on_refresh:
                try:
                    self._on_refresh()
                except Exception:
                    pass

        self._confirmar_dialogo(
            "Excluir Taxa",
            f"Deseja realmente excluir a opção de taxa '{tx['label']}' (R$ {tx['valor']:.2f})?",
            _exec,
            icone="🗑"
        )

    # ── ABA 4: OBSERVAÇÕES RÁPIDAS ───────────────────────────────────────────

    def _build_tab_observacoes(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=0)
        tab.rowconfigure(0, weight=1)

        tabela_frame = ctk.CTkFrame(tab, fg_color=COR_CINZA_BARRA, corner_radius=10)
        tabela_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tabela_frame.rowconfigure(1, weight=1)
        tabela_frame.columnconfigure(0, weight=1)

        header = ctk.CTkFrame(tabela_frame, fg_color="#1E1E1E", height=36, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=3, minsize=220)
        header.columnconfigure(1, weight=0, minsize=100)
        header.columnconfigure(2, weight=0, minsize=50)

        ctk.CTkLabel(header, text="Texto da Observação (Clique para editar)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkLabel(header, text="Ativo", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        ctk.CTkLabel(header, text="Ações", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=2, padx=(4, 8), pady=6, sticky="e")

        self._obs_scroll = ctk.CTkScrollableFrame(tabela_frame, fg_color="transparent")
        self._obs_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._obs_scroll.columnconfigure(0, weight=3, minsize=220)
        self._obs_scroll.columnconfigure(1, weight=0, minsize=100)
        self._obs_scroll.columnconfigure(2, weight=0, minsize=50)

        # Form lateral observações (focado estritamente em novos cadastros)
        form_obs = ctk.CTkFrame(tab, fg_color=COR_CINZA_BARRA, corner_radius=10, width=320)
        form_obs.grid(row=0, column=1, sticky="nsew")
        form_obs.pack_propagate(False)

        ctk.CTkLabel(form_obs, text="ADICIONAR NOVA OBSERVAÇÃO", font=ctk.CTkFont(size=13, weight="bold"), text_color=COR_TEXTO_SUAVE).pack(pady=(14, 8), padx=14, anchor="w")

        ctk.CTkLabel(form_obs, text="Texto da Observação", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w", padx=14)
        self._obs_texto = ctk.CTkEntry(form_obs, height=36, font=ctk.CTkFont(size=13), placeholder_text="Ex: Sem Cebola, Bem Passado...")
        self._obs_texto.pack(fill="x", padx=14, pady=(2, 14))

        btn_cadastrar_obs = ctk.CTkButton(
            form_obs, text="➕  Cadastrar Observação", height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_VERDE, hover_color=COR_VERDE_HVR, corner_radius=8,
            command=self._cadastrar_obs
        )
        btn_cadastrar_obs.pack(fill="x", padx=14, pady=(0, 6))
        habilitar_feedback_clique(btn_cadastrar_obs, cor_flash="#10B981")

        btn_limpar_obs = ctk.CTkButton(
            form_obs, text="Limpar Campos", height=36,
            font=ctk.CTkFont(size=12),
            fg_color="#444", hover_color="#555", corner_radius=8,
            command=self._limpar_form_obs
        )
        btn_limpar_obs.pack(fill="x", padx=14, pady=(0, 6))
        habilitar_feedback_clique(btn_limpar_obs, cor_flash="#666666")

        self._obs_status_lbl = ctk.CTkLabel(form_obs, text="", font=ctk.CTkFont(size=12), wraplength=280)
        self._obs_status_lbl.pack(padx=14, pady=(8, 0))

        ctk.CTkLabel(
            form_obs,
            text="💡 Essas observações aparecem como\n"
                 "    botões rápidos no pop-up de itens.\n"
                 "    Edite o texto clicando na tabela ao lado.",
            font=ctk.CTkFont(size=11), text_color=COR_TEXTO_SUAVE, justify="left"
        ).pack(anchor="w", padx=14, pady=(20, 0))

    def _carregar_obs(self):
        for w in self._obs_scroll.winfo_children():
            w.destroy()

        obs_list = listar_observacoes_padrao(apenas_ativas=False)
        for i, obs in enumerate(obs_list):
            bg = "#272727" if i % 2 == 0 else "#222222"
            row = ctk.CTkFrame(self._obs_scroll, fg_color=bg, corner_radius=6, height=42)
            row.pack(fill="x", pady=2, padx=2)
            row.columnconfigure(0, weight=3, minsize=220)
            row.columnconfigure(1, weight=0, minsize=100)
            row.columnconfigure(2, weight=0, minsize=50)

            # Célula 1: Texto da Observação (editável inline)
            entry_texto = ctk.CTkEntry(
                row, height=30, font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#1E1E1E", border_width=1, border_color="#333333"
            )
            entry_texto.insert(0, obs["texto"])
            entry_texto.grid(row=0, column=0, padx=6, pady=4, sticky="ew")

            def _ao_mudar_texto(event, o=obs, w=entry_texto):
                novo_texto = w.get().strip()
                if not novo_texto or novo_texto == o["texto"]:
                    w.delete(0, "end")
                    w.insert(0, o["texto"])
                    return
                atualizar_observacao_padrao(o["id"], novo_texto, o.get("ativo", 1))
                o["texto"] = novo_texto
                self._flash_entry_salvo(w, border_normal="#333333", border_flash=COR_VERDE)
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            entry_texto.bind("<Return>", _ao_mudar_texto)
            entry_texto.bind("<FocusOut>", _ao_mudar_texto)

            # Célula 2: Status Ativo/Inativo (switch direto na linha)
            var_ativo = ctk.BooleanVar(value=bool(obs.get("ativo", 1)))
            switch_ativo = ctk.CTkSwitch(
                row, text="Ativa" if var_ativo.get() else "Inativa",
                variable=var_ativo,
                font=ctk.CTkFont(size=11, weight="bold"),
                progress_color=COR_VERDE
            )
            switch_ativo.grid(row=0, column=1, padx=8, pady=4, sticky="w")

            def _ao_toggle_obs(o=obs, var=var_ativo, sw=switch_ativo):
                st = 1 if var.get() else 0
                atualizar_observacao_padrao(o["id"], o["texto"], st)
                o["ativo"] = st
                sw.configure(text="Ativa" if st else "Inativa")
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

            switch_ativo.configure(command=_ao_toggle_obs)

            # Célula 3: Ação única Excluir (🗑) com confirmação
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.grid(row=0, column=2, padx=(4, 8), sticky="e")

            btn_del = ctk.CTkButton(
                btn_frame, text="🗑", width=34, height=28,
                font=ctk.CTkFont(size=13),
                fg_color=COR_VERMELHO, hover_color=COR_VERMELHO_HVR,
                corner_radius=6, command=lambda o=obs: self._confirmar_remocao_obs(o)
            )
            btn_del.pack(side="left")
            habilitar_feedback_clique(btn_del, cor_flash="#DC2626")

    def _cadastrar_obs(self):
        texto = self._obs_texto.get().strip()

        if not texto:
            self._obs_status_lbl.configure(text="⚠ Texto é obrigatório!", text_color=COR_VERMELHO)
            return

        adicionar_observacao_padrao(texto)
        self._limpar_form_obs()
        self._carregar_obs()
        if self._on_refresh:
            try:
                self._on_refresh()
            except Exception:
                pass
        self._obs_status_lbl.configure(text=f"✅ '{texto}' cadastrada!", text_color=COR_VERDE)

    def _limpar_form_obs(self):
        self._obs_texto.delete(0, "end")
        self._obs_status_lbl.configure(text="")

    def _confirmar_remocao_obs(self, obs: dict):
        def _exec():
            remover_observacao_padrao(obs["id"])
            self._carregar_obs()
            if self._on_refresh:
                try:
                    self._on_refresh()
                except Exception:
                    pass

        self._confirmar_dialogo(
            "Excluir Observação",
            f"Deseja realmente excluir a observação rápida '{obs['texto']}'?",
            _exec,
            icone="🗑"
        )

    # ── ABA 5: IMPRESSORA (REDE E CABO USB) ────────────────────────────────────

    def _build_tab_impressora(self, tab):
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=8)

        card = ctk.CTkFrame(scroll, fg_color=COR_CINZA_BARRA, corner_radius=12)
        card.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            card, text="🖨  Configuração da Impressora Térmica Elgin i8",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=20, pady=(18, 4))

        ctk.CTkLabel(
            card, text="Selecione abaixo o método de conexão da Elgin i8 a este computador de caixa:",
            font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE
        ).pack(anchor="w", padx=20, pady=(0, 14))

        # Seletor de Tipo de Conexão
        self._tipo_conexao_var = ctk.StringVar(value=get_config("printer_tipo", PRINTER_TIPO_DEFAULT))

        tipo_frame = ctk.CTkFrame(card, fg_color="#1E1E1E", corner_radius=8)
        tipo_frame.pack(fill="x", padx=20, pady=(0, 16))

        r_rede = ctk.CTkRadioButton(
            tipo_frame, text="🌐  Rede Ethernet / Wi-Fi (TCP Socket Porta 9100)",
            variable=self._tipo_conexao_var, value="rede",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._alternar_interface_impressora
        )
        r_rede.pack(side="left", padx=20, pady=12)

        r_usb = ctk.CTkRadioButton(
            tipo_frame, text="🔌  Cabo USB Direto (Windows Spooler / Driver)",
            variable=self._tipo_conexao_var, value="usb",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._alternar_interface_impressora
        )
        r_usb.pack(side="left", padx=20, pady=12)

        # ── Painel de Configuração REDE ──
        self._frame_rede = ctk.CTkFrame(card, fg_color="#232323", corner_radius=8)
        self._frame_rede.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkLabel(
            self._frame_rede, text="Configuração de Rede (Ethernet / TCP Socket):",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COR_PRIMARIA
        ).pack(anchor="w", padx=14, pady=(12, 4))

        ctk.CTkLabel(
            self._frame_rede, text="Endereço IP da Elgin i8 na rede local:",
            font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE
        ).pack(anchor="w", padx=14)

        ip_input_row = ctk.CTkFrame(self._frame_rede, fg_color="transparent")
        ip_input_row.pack(fill="x", padx=14, pady=(4, 12))

        self._ip_var = ctk.StringVar(value=get_config("printer_ip", PRINTER_IP_DEFAULT))
        self._ip_entry = ctk.CTkEntry(
            ip_input_row, textvariable=self._ip_var, width=220, height=40,
            font=ctk.CTkFont(size=15), placeholder_text="192.168.1.100"
        )
        self._ip_entry.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            ip_input_row, text="Porta: 9100 (Padrão RAW)",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            ip_input_row, text="🔌  Testar Conexão (Socket TCP)", height=40, width=220,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#3A3A3A", hover_color="#4A4A4A",
            command=self._testar_impressora_rede
        ).pack(side="left", padx=(14, 0))

        # ── Painel de Configuração USB ──
        self._frame_usb = ctk.CTkFrame(card, fg_color="#232323", corner_radius=8)
        self._frame_usb.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkLabel(
            self._frame_usb, text="Configuração Cabo USB (Windows Spooler / Driver):",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COR_PRIMARIA
        ).pack(anchor="w", padx=14, pady=(12, 4))

        ctk.CTkLabel(
            self._frame_usb, text="Selecione a impressora Elgin i8 instalada no Windows:",
            font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE
        ).pack(anchor="w", padx=14)

        usb_input_row = ctk.CTkFrame(self._frame_usb, fg_color="transparent")
        usb_input_row.pack(fill="x", padx=14, pady=(4, 12))

        printers_list = listar_impressoras_windows()
        if not printers_list:
            printers_list = [PRINTER_USB_DEFAULT, "POS-80"]

        default_usb = get_config("printer_usb", PRINTER_USB_DEFAULT)
        self._usb_var = ctk.StringVar(value=default_usb)

        self._usb_combo = ctk.CTkComboBox(
            usb_input_row, variable=self._usb_var,
            values=printers_list, width=280, height=40,
            font=ctk.CTkFont(size=13)
        )
        self._usb_combo.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            usb_input_row, text="🔄  Atualizar Lista", height=40, width=130,
            font=ctk.CTkFont(size=12),
            fg_color="#333", hover_color="#444",
            command=self._atualizar_lista_usb
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            usb_input_row, text="🔌  Testar Impressão USB", height=40, width=180,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#3A3A3A", hover_color="#4A4A4A",
            command=self._testar_impressora_usb
        ).pack(side="left")

        # Botão Salvar Global de Impressora
        save_box = ctk.CTkFrame(card, fg_color="transparent")
        save_box.pack(fill="x", padx=20, pady=(6, 14))

        ctk.CTkButton(
            save_box, text="💾  SALVAR CONFIGURAÇÕES DA IMPRESSORA",
            height=44, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_VERDE, hover_color=COR_VERDE_HVR,
            corner_radius=8,
            command=self._salvar_config_impressora
        ).pack(side="left", padx=(0, 14))

        self._printer_status_lbl = ctk.CTkLabel(
            save_box, text="", font=ctk.CTkFont(size=13, weight="bold")
        )
        self._printer_status_lbl.pack(side="left")

        # Dicas informativas
        dica_box = ctk.CTkFrame(card, fg_color="#181818", corner_radius=8)
        dica_box.pack(fill="x", padx=20, pady=(0, 18))

        ctk.CTkLabel(
            dica_box,
            text="💡 Dicas de Conexão:\n"
                 "  • Cabo USB: Conecte o cabo USB no computador e instale o driver oficial da Elgin i8.\n"
                 "    A impressora aparecerá na lista suspensa acima (ex: 'Elgin i8' ou 'POS-80').\n"
                 "  • Rede Ethernet: Conecte o cabo de rede no roteador. Ligue a impressora segurando\n"
                 "    o botão FEED por 3 segundos para imprimir a folha com o IP atual da rede.",
            font=ctk.CTkFont(size=11), text_color=COR_TEXTO_SUAVE, justify="left"
        ).pack(anchor="w", padx=16, pady=10)

        # Atualizar visibilidade inicial
        self._alternar_interface_impressora()

    def _alternar_interface_impressora(self):
        tipo = self._tipo_conexao_var.get()
        if tipo == "usb":
            self._frame_usb.configure(border_color=COR_PRIMARIA, border_width=1)
            self._frame_rede.configure(border_width=0)
        else:
            self._frame_rede.configure(border_color=COR_PRIMARIA, border_width=1)
            self._frame_usb.configure(border_width=0)

    def _atualizar_lista_usb(self):
        printers = listar_impressoras_windows()
        if not printers:
            printers = [PRINTER_USB_DEFAULT, "POS-80"]
        self._usb_combo.configure(values=printers)
        self._printer_status_lbl.configure(text=f"🔄 {len(printers)} impressoras encontradas no Windows.", text_color=COR_PRIMARIA)

    def _salvar_config_impressora(self):
        tipo = self._tipo_conexao_var.get()
        ip = self._ip_var.get().strip()
        usb = self._usb_var.get().strip()

        set_config("printer_tipo", tipo)
        if ip:
            set_config("printer_ip", ip)
        if usb:
            set_config("printer_usb", usb)

        alvo = f"USB '{usb}'" if tipo == "usb" else f"Rede '{ip}:9100'"
        self._printer_status_lbl.configure(
            text=f"✅ Configuração salva: Modo {tipo.upper()} -> {alvo}!",
            text_color=COR_VERDE
        )

    def _testar_impressora_rede(self):
        ip = self._ip_var.get().strip()
        if not ip:
            self._printer_status_lbl.configure(text="⚠ Informe o endereço IP da Elgin i8!", text_color=COR_VERMELHO)
            return

        self._printer_status_lbl.configure(text=f"⏳ Testando conexão Socket TCP em {ip}:9100 (timeout 2s)...", text_color=COR_AZUL_POINT)
        self.update()

        import threading
        import socket
        def _test():
            try:
                with socket.create_connection((ip, 9100), timeout=2.0):
                    self.after(0, lambda: self._printer_status_lbl.configure(
                        text=f"✅ Elgin i8 em {ip}:9100 conectada com sucesso!",
                        text_color=COR_VERDE
                    ))
            except Exception:
                self.after(0, lambda: self._printer_status_lbl.configure(
                    text=f"❌ Inacessível em {ip}:9100 (verifique se a impressora está ligada e na rede)",
                    text_color=COR_VERMELHO
                ))

        threading.Thread(target=_test, daemon=True).start()

    def _testar_impressora_usb(self):
        nome_usb = self._usb_var.get().strip()
        if not nome_usb:
            self._printer_status_lbl.configure(text="⚠ Selecione ou digite o nome da impressora USB!", text_color=COR_VERMELHO)
            return

        self._printer_status_lbl.configure(text="⏳ Enviando comando de teste via USB Spooler...", text_color=COR_AZUL_POINT)
        self.update()

        import threading
        def _test():
            try:
                teste_bytes = (
                    CMD_INIT +
                    CMD_CODEPAGE_CP850 +
                    b"\n" +
                    _encode("================================\n") +
                    _encode("   TESTE ELGIN i8 USB - OK!    \n") +
                    _encode("   Acentuação: Coração & Opção \n") +
                    _encode("   Point Lanches - Sistema     \n") +
                    _encode("================================\n\n\n") +
                    CMD_CUT
                )
                send_to_usb_printer(nome_usb, teste_bytes)
                self.after(0, lambda: self._printer_status_lbl.configure(
                    text=f"✅ Teste USB enviado para '{nome_usb}' com sucesso!",
                    text_color=COR_VERDE
                ))
            except Exception as e:
                self.after(0, lambda: self._printer_status_lbl.configure(
                    text=f"❌ Falha no teste USB: {e}",
                    text_color=COR_VERMELHO
                ))

        threading.Thread(target=_test, daemon=True).start()

    def _carregar_config(self):
        """Recarrega os valores de configuração da impressora nos campos."""
        if hasattr(self, "_tipo_conexao_var"):
            self._tipo_conexao_var.set(get_config("printer_tipo", PRINTER_TIPO_DEFAULT))
            self._alternar_interface_impressora()
        if hasattr(self, "_ip_var"):
            self._ip_var.set(get_config("printer_ip", PRINTER_IP_DEFAULT))
        if hasattr(self, "_usb_var"):
            self._usb_var.set(get_config("printer_usb", PRINTER_USB_DEFAULT))

    # ── BACKUP & PORTABILIDADE (EXPORTAR / IMPORTAR BANCO / JSON) ─────────────

    def _exportar_backup(self):
        from tkinter import filedialog
        from datetime import datetime

        data_s = datetime.now().strftime("%Y-%m-%d_%H%M")
        sugestao_nome = f"PointLanches_Backup_{data_s}.db"

        caminho = filedialog.asksaveasfilename(
            parent=self,
            title="Salvar Backup de Dados",
            initialfile=sugestao_nome,
            defaultextension=".db",
            filetypes=[
                ("Banco SQLite (*.db)", "*.db"),
                ("Banco SQLite (*.sqlite)", "*.sqlite"),
                ("Backup JSON legado (*.json)", "*.json"),
                ("Todos os Arquivos", "*.*")
            ]
        )
        if not caminho:
            return

        self._overlay.show("Exportando dados de backup...")
        self.after(60, lambda: self._executar_exportacao_backup(caminho))

    # Compatibilidade retroativa interna
    _exportar_backup_json = _exportar_backup

    def _executar_exportacao_backup(self, caminho):
        try:
            if caminho.lower().endswith(".json"):
                import json
                dados = exportar_dados_json()
                with open(caminho, "w", encoding="utf-8") as f:
                    json.dump(dados, f, ensure_ascii=False, indent=2)
            else:
                exportar_banco_sqlite(caminho)

            self._overlay.hide()
            self._mostrar_alerta("Backup Exportado!", f"Banco de dados exportado com sucesso para:\n{caminho}", icone="✅")
        except Exception as e:
            self._overlay.hide()
            self._mostrar_alerta("Erro na Exportação", f"Não foi possível salvar o arquivo de backup:\n{str(e)}", icone="❌")

    def _importar_backup(self):
        from tkinter import filedialog

        caminho = filedialog.askopenfilename(
            parent=self,
            title="Selecionar Arquivo de Backup para Importação",
            filetypes=[
                ("Banco SQLite (*.db;*.sqlite)", "*.db;*.sqlite"),
                ("Banco SQLite (*.db)", "*.db"),
                ("Banco SQLite (*.sqlite)", "*.sqlite"),
                ("Backup JSON (*.json)", "*.json"),
                ("Todos os Arquivos", "*.*")
            ]
        )
        if not caminho:
            return

        self._overlay.show("Processando importação e atualização do banco...")
        self.after(60, lambda: self._executar_importacao_backup(caminho))

    # Compatibilidade retroativa interna
    _importar_backup_json = _importar_backup

    def _executar_importacao_backup(self, caminho):
        try:
            if caminho.lower().endswith(".json"):
                import json
                with open(caminho, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                sucesso, msg = importar_dados_json(dados)
            else:
                sucesso, msg = importar_banco_sqlite(caminho)

            self._overlay.hide()
            if sucesso:
                # Recarregar abas do Admin em tempo real
                self._carregar_produtos()
                if hasattr(self, "_carregar_categorias_tab"):
                    self._carregar_categorias_tab()
                self._atualizar_combobox_categorias()
                self._carregar_adicionais()
                self._carregar_taxas()
                if hasattr(self, "_carregar_obs"):
                    self._carregar_obs()
                self._carregar_config()
                if hasattr(self, "_atualizar_balanco"):
                    self._atualizar_balanco()

                # Notificar app pai para atualizar cardápio e telas principais
                if self._on_refresh:
                    try:
                        self._on_refresh()
                    except Exception:
                        pass

                msg_sucesso = (
                    f"Backup importado com sucesso! A estrutura do banco foi atualizada para a "
                    f"versão atual (v{__version__}) mantendo todos os seus registros anteriores."
                )
                self._mostrar_alerta("Importação Concluída!", msg_sucesso, icone="✅")
            else:
                msg_erro = (
                    f"Falha ao importar banco: arquivo inválido ou bloqueado por outro processo.\n"
                    f"Detalhes: {msg}"
                )
                self._mostrar_alerta("Falha na Importação", msg_erro, icone="⚠️")
        except Exception as e:
            self._overlay.hide()
            msg_erro = (
                f"Falha ao importar banco: arquivo inválido ou bloqueado por outro processo.\n"
                f"Detalhes: {str(e)}"
            )
            self._mostrar_alerta("Falha ao Importar", msg_erro, icone="❌")

    def _desconectar_nuvem(self):
        """Encerra a sessão atual com o Supabase e retorna ao modo local."""
        try:
            from services.supabase_auth import auth_manager
            auth_manager.logout()
            self._mostrar_alerta("Sessão Encerrada", "Você foi desconectado da nuvem. O sistema continuará operando normalmente em modo offline local.", icone="📴")
            self.destroy()
        except Exception:
            pass

    def _mostrar_alerta(self, titulo: str, mensagem: str, icone: str = "ℹ️"):
        win = ctk.CTkToplevel(self)
        win.title(titulo)
        win.geometry("420x220")
        win.grab_set()
        win.resizable(False, False)

        win.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - 420) // 2
        py = self.winfo_rooty() + (self.winfo_height() - 220) // 2
        win.geometry(f"+{max(0, px)}+{max(0, py)}")

        ctk.CTkLabel(win, text=icone, font=ctk.CTkFont(size=44)).pack(pady=(16, 2))
        ctk.CTkLabel(win, text=titulo, font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(2, 6))
        ctk.CTkLabel(win, text=mensagem, font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE, wraplength=380, justify="center").pack(padx=20, pady=(0, 14))

        ctk.CTkButton(
            win, text="OK", width=120, height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_PRIMARIA, hover_color=COR_PRIMARIA_HVR,
            corner_radius=8, command=win.destroy
        ).pack(pady=(0, 14))

    def _verificar_atualizacoes_manual(self):
        """Dispara verificação de atualizações com feedback explícito."""
        import threading
        self._overlay.show("Verificando atualizações no GitHub...")

        def _worker():
            try:
                check_for_updates(self, silent_if_uptodate=False)
            finally:
                self.after(0, self._overlay.hide)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

