import re
import unicodedata
import customtkinter as ctk
from database.db import (
    listar_taxas, listar_ruas,
    registrar_callback_ruas_modificadas, desregistrar_callback_ruas_modificadas
)
from ui.components.widgets import TopBar, ChipButton, habilitar_feedback_clique
from config import (
    COR_PRIMARIA, COR_PRIMARIA_HVR, COR_VERDE, COR_VERDE_HVR,
    COR_CINZA_BARRA, COR_FUNDO, COR_TEXTO, COR_TEXTO_SUAVE,
    RUAS_DOIS_IRMAOS, BAIRROS_DOIS_IRMAOS, TAXAS_RAPIDAS
)

# ── Gerador Dinâmico de Acrônimos e Siglas de Ruas ─────────────────────────────
GENERICOS_VIAS = {
    'rua', 'r', 'avenida', 'av', 'travessa', 'trav',
    'estrada', 'estr', 'alameda', 'al', 'beco', 'rodovia', 'rod'
}
PREPOSICOES_VIAS = {'de', 'da', 'do', 'dos', 'das', 'e'}


def _strip_accents(text: str) -> str:
    """Remove acentos e converte para minúsculas (ex: 'São' -> 'sao')."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()


def gerar_acronimos_rua(nome: str) -> set[str]:
    """
    Gera dinamicamente siglas e acrônimos automáticos para qualquer rua sem listas fixas.
    Exemplos:
      'Avenida São Miguel'   -> {'sm', 'asm'}
      'Rua Alberto Rübenich' -> {'ar', 'rar'}
      'Rua 10 de Setembro'   -> {'10', '10s', 'r10', 'r10s'}
      'Rua Novo Hamburgo'    -> {'nh', 'rnh'}
      'Rua São Leopoldo'     -> {'sl', 'rsl'}
      'Avenida Florestal'    -> {'fl', 'flo', 'af'}
      'Avenida Sapiranga'    -> {'sap', 'as', 'sa'}
    """
    clean = _strip_accents(nome)
    tokens = re.findall(r'[a-z0-9]+', clean)
    if not tokens:
        return set()

    acronyms = set()
    has_generic = tokens[0] in GENERICOS_VIAS
    gen_initial = tokens[0][0] if has_generic else ""
    sig_tokens = [t for t in (tokens[1:] if has_generic else tokens) if t not in PREPOSICOES_VIAS]

    if not sig_tokens:
        sig_tokens = tokens

    # 1. Sigla pelas palavras significativas restantes
    parts = [t if t.isdigit() else t[0] for t in sig_tokens]
    sigla_base = "".join(parts)
    if len(sigla_base) >= 2 or sigla_base.isdigit():
        acronyms.add(sigla_base)
        if gen_initial:
            acronyms.add(gen_initial + sigla_base)

    # 2. Casos com números (ex: 10, 25)
    for t in sig_tokens:
        if t.isdigit():
            acronyms.add(t)
            if gen_initial:
                acronyms.add(gen_initial + t)

    # 3. Se houver apenas 1 palavra significativa (ex: Florestal -> fl, flo, af)
    if len(sig_tokens) == 1:
        w = sig_tokens[0]
        if not w.isdigit():
            if len(w) >= 2:
                acronyms.add(w[:2])
            if len(w) >= 3:
                acronyms.add(w[:3])
            if gen_initial:
                acronyms.add(gen_initial + w[0])
    elif len(sig_tokens) >= 2:
        p1 = sig_tokens[0] if sig_tokens[0].isdigit() else sig_tokens[0][0]
        p2 = sig_tokens[1] if sig_tokens[1].isdigit() else sig_tokens[1][0]
        sigla_dupla = f"{p1}{p2}"
        acronyms.add(sigla_dupla)
        if gen_initial:
            acronyms.add(f"{gen_initial}{sigla_dupla}")

    return {a for a in acronyms if len(a) >= 2 or a.isdigit()}


class ScreenDelivery(ctk.CTkFrame):
    """
    Tela 2 – Dados de entrega + Taxa de tele com Multi-Grid de ruas e botões dinâmicos.
    """

    def __init__(self, master, state: dict, on_next, on_back, on_admin,
                 on_historico=None, on_balanco=None, **kwargs):
        super().__init__(master, fg_color=COR_FUNDO, **kwargs)
        self._state        = state
        self._on_next      = on_next
        self._on_back      = on_back
        self._on_historico = on_historico
        self._on_balanco   = on_balanco

        self._taxa_var     = ctk.StringVar(value="0")
        self._bairro_sel   = ctk.StringVar()
        self._rua_var      = ctk.StringVar()
        self._busca_rua    = ctk.StringVar()

        self._rua_botoes: list[tuple[str, ctk.CTkButton]] = []
        self._debounce_id = None
        self._taxa_chips: list[ChipButton] = []
        self._bairro_chips: list[ChipButton] = []

        self._ruas_todas: list[str] = []
        self._ruas_indices: list[tuple[str, str, set[str]]] = []
        self._ruas_map: dict[str, dict] = {}
        self._carregar_ruas()

        # Inscrição para sincronização em tempo real de novas ruas
        registrar_callback_ruas_modificadas(self._ao_notificar_ruas_modificadas)

        self._build_ui(on_admin)

    def _ao_notificar_ruas_modificadas(self):
        try:
            self.after(0, self._carregar_ruas)
        except Exception:
            pass

    def destroy(self):
        try:
            desregistrar_callback_ruas_modificadas(self._ao_notificar_ruas_modificadas)
        except Exception:
            pass
        super().destroy()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self, on_admin):
        TopBar(
            self, "Entrega",
            on_admin=on_admin,
            on_historico=self._on_historico,
            on_balanco=self._on_balanco
        ).pack(fill="x")

        # Layout com 2 colunas principais (Scrollable)
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=6)
        scroll.columnconfigure(0, weight=6)
        scroll.columnconfigure(1, weight=4)

        # ── Coluna Esquerda: Cliente e Ruas (Multi-Grid) ──
        left = ctk.CTkFrame(scroll, fg_color=COR_CINZA_BARRA, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=2)
        left.columnconfigure(0, weight=1)

        self._secao(left, "👤  DADOS DO CLIENTE", row=0)

        # Linha Nome + Telefone lado a lado
        cli_frame = ctk.CTkFrame(left, fg_color="transparent")
        cli_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        cli_frame.columnconfigure(0, weight=3)
        cli_frame.columnconfigure(1, weight=2)

        self._nome_var = ctk.StringVar()
        self._fone_var = ctk.StringVar()

        f_nome = ctk.CTkFrame(cli_frame, fg_color="transparent")
        f_nome.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkLabel(f_nome, text="Nome do Cliente", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w")
        ctk.CTkEntry(f_nome, textvariable=self._nome_var, placeholder_text="Nome do cliente", height=34, font=ctk.CTkFont(size=13)).pack(fill="x", pady=(2, 0))

        f_fone = ctk.CTkFrame(cli_frame, fg_color="transparent")
        f_fone.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ctk.CTkLabel(f_fone, text="Telefone / WhatsApp", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w")
        ctk.CTkEntry(f_fone, textvariable=self._fone_var, placeholder_text="(51) 99999-9999", height=34, font=ctk.CTkFont(size=13)).pack(fill="x", pady=(2, 0))

        # ── Endereço: Seleção de Rua em Multi-Grid ──
        self._secao(left, "📍  SELEÇÃO DE RUA (CLIQUE OU BUSQUE)", row=2)

        # Campo de busca e visualização da rua selecionada
        busca_box = ctk.CTkFrame(left, fg_color="#1F1F1F", corner_radius=8)
        busca_box.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 4))
        busca_box.columnconfigure(1, weight=1)

        ctk.CTkLabel(busca_box, text="🔍  Rua Selecionada:", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_PRIMARIA).grid(row=0, column=0, padx=8, pady=6)
        self._entry_rua = ctk.CTkEntry(
            busca_box, textvariable=self._rua_var,
            placeholder_text="Clique na rua abaixo ou digite aqui para buscar...",
            height=34, font=ctk.CTkFont(size=13)
        )
        self._entry_rua.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)
        self._rua_var.trace_add("write", self._filtrar_grid_ruas)

        # Container Multi-Grid de Ruas (3 colunas de botões lado a lado, sem setas nem paginação)
        self._ruas_container = ctk.CTkScrollableFrame(left, height=175, fg_color="#181818", corner_radius=8)
        self._ruas_container.grid(row=4, column=0, sticky="nsew", padx=12, pady=(0, 8))
        for col_idx in range(3):
            self._ruas_container.columnconfigure(col_idx, weight=1)

        self._renderizar_grid_ruas(self._ruas_todas[:30])

        # Número, Complemento e Referência
        end_detalhe = ctk.CTkFrame(left, fg_color="transparent")
        end_detalhe.grid(row=5, column=0, sticky="ew", padx=14, pady=(0, 12))
        end_detalhe.columnconfigure(0, weight=1)
        end_detalhe.columnconfigure(1, weight=2)
        end_detalhe.columnconfigure(2, weight=2)

        self._num_var  = ctk.StringVar()
        self._comp_var = ctk.StringVar()
        self._ref_var  = ctk.StringVar()

        f_num = ctk.CTkFrame(end_detalhe, fg_color="transparent")
        f_num.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkLabel(f_num, text="Número", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w")
        ctk.CTkEntry(f_num, textvariable=self._num_var, placeholder_text="123", height=34, font=ctk.CTkFont(size=13)).pack(fill="x", pady=(2, 0))

        f_comp = ctk.CTkFrame(end_detalhe, fg_color="transparent")
        f_comp.grid(row=0, column=1, sticky="ew", padx=4)
        ctk.CTkLabel(f_comp, text="Compl. / Apto", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w")
        ctk.CTkEntry(f_comp, textvariable=self._comp_var, placeholder_text="Apto 201, Bl B", height=34, font=ctk.CTkFont(size=13)).pack(fill="x", pady=(2, 0))

        f_ref = ctk.CTkFrame(end_detalhe, fg_color="transparent")
        f_ref.grid(row=0, column=2, sticky="ew", padx=(4, 0))
        ctk.CTkLabel(f_ref, text="Ponto de Ref.", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(anchor="w")
        ctk.CTkEntry(f_ref, textvariable=self._ref_var, placeholder_text="Próximo à praça", height=34, font=ctk.CTkFont(size=13)).pack(fill="x", pady=(2, 0))

        # ── Bairros (Chips Rápidos) ──
        self._secao(left, "🏘  BAIRRO DE DOIS IRMÃOS", row=6)
        bairro_frame = ctk.CTkFrame(left, fg_color="transparent")
        bairro_frame.grid(row=7, column=0, sticky="ew", padx=12, pady=(0, 10))

        for idx, b in enumerate(BAIRROS_DOIS_IRMAOS):
            chip = ChipButton(
                bairro_frame, text=b,
                on_select=lambda t, s, bairro=b: self._selecionar_bairro(bairro, s)
            )
            chip.grid(row=idx // 4, column=idx % 4, padx=3, pady=2, sticky="w")
            self._bairro_chips.append(chip)

        # ── Coluna Direita: Taxa de Tele e Resumo do Pedido ──
        right = ctk.CTkFrame(scroll, fg_color=COR_CINZA_BARRA, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=2)
        right.columnconfigure(0, weight=1)

        self._secao(right, "🛵  TAXA DE TELE-ENTREGA", row=0)

        # Container dinâmico dos botões de taxa rápida (carregados do DB)
        self._taxas_chips_frame = ctk.CTkFrame(right, fg_color="transparent")
        self._taxas_chips_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        self._carregar_chips_taxas()

        # Campo personalizado de taxa
        taxa_custom_frame = ctk.CTkFrame(right, fg_color="transparent")
        taxa_custom_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(taxa_custom_frame, text="Outro valor: R$", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(side="left", padx=(0, 6))
        self._taxa_entry = ctk.CTkEntry(
            taxa_custom_frame, textvariable=self._taxa_var,
            width=100, height=34, font=ctk.CTkFont(size=14, weight="bold"), justify="right"
        )
        self._taxa_entry.pack(side="left")
        self._taxa_var.trace_add("write", self._on_taxa_change)

        # ── Resumo do Pedido ──
        self._secao(right, "📋  RESUMO DO PEDIDO", row=3)

        resumo_card = ctk.CTkFrame(right, fg_color="#1E1E1E", corner_radius=10)
        resumo_card.grid(row=4, column=0, sticky="ew", padx=12, pady=4)
        resumo_card.columnconfigure(0, weight=1)

        self._sub_lbl = ctk.CTkLabel(resumo_card, text="Subtotal:      R$ 0,00", font=ctk.CTkFont(size=13), anchor="w")
        self._sub_lbl.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 2))

        self._taxa_lbl = ctk.CTkLabel(resumo_card, text="Taxa entrega:  R$ 0,00", font=ctk.CTkFont(size=13), anchor="w")
        self._taxa_lbl.grid(row=1, column=0, sticky="ew", padx=12, pady=2)

        ctk.CTkFrame(resumo_card, height=1, fg_color="#444").grid(row=2, column=0, sticky="ew", padx=8, pady=3)

        self._total_lbl = ctk.CTkLabel(
            resumo_card, text="TOTAL:         R$ 0,00",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=COR_PRIMARIA, anchor="w"
        )
        self._total_lbl.grid(row=3, column=0, sticky="ew", padx=12, pady=(2, 10))

        # ── Navegação ──
        nav_frame = ctk.CTkFrame(right, fg_color="transparent")
        nav_frame.grid(row=5, column=0, sticky="ew", padx=12, pady=12)
        nav_frame.columnconfigure(0, weight=1)
        nav_frame.columnconfigure(1, weight=1)

        btn_voltar = ctk.CTkButton(
            nav_frame, text="◀  Voltar",
            height=42, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#444", hover_color="#555",
            corner_radius=10,
            command=self._on_back
        )
        btn_voltar.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        habilitar_feedback_clique(btn_voltar, cor_flash="#666", debounce_ms=200)

        btn_avancar = ctk.CTkButton(
            nav_frame, text="Avançar para Pagamento  ➜",
            height=42, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_VERDE, hover_color=COR_VERDE_HVR,
            corner_radius=10,
            command=self._avancar
        )
        btn_avancar.grid(row=0, column=1, padx=(4, 0), sticky="ew")
        habilitar_feedback_clique(btn_avancar, cor_flash=COR_VERDE_HVR, debounce_ms=250)

    # ── Helpers e Grid de Ruas ────────────────────────────────────────────────

    def _secao(self, parent, titulo, row):
        ctk.CTkLabel(
            parent, text=titulo,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_TEXTO_SUAVE
        ).grid(row=row, column=0, sticky="w", padx=14, pady=(12, 4))

    def _renderizar_grid_ruas(self, ruas: list[str]):
        """Renderiza botões de ruas em 3 colunas lado a lado sem paginação."""
        for w in self._ruas_container.winfo_children():
            w.destroy()

        self._rua_botoes.clear()
        COLS = 3
        rua_atual = self._rua_var.get().strip()

        for idx, rua in enumerate(ruas):
            r, c = divmod(idx, COLS)
            is_selected = (rua.lower() == rua_atual.lower())
            btn = ctk.CTkButton(
                self._ruas_container,
                text=rua,
                height=34,
                font=ctk.CTkFont(size=11),
                fg_color=COR_PRIMARIA if is_selected else "#282828",
                hover_color=COR_PRIMARIA_HVR if is_selected else "#3A3A3A",
                text_color="#FFFFFF" if is_selected else "#DDDDDD",
                corner_radius=6,
                anchor="center",
                command=lambda nome=rua: self._selecionar_rua(nome)
            )
            btn.grid(row=r, column=c, padx=3, pady=3, sticky="ew")
            habilitar_feedback_clique(btn, cor_flash=COR_PRIMARIA_HVR, debounce_ms=100)
            self._rua_botoes.append((rua, btn))

    def _carregar_ruas(self):
        """Carrega ruas do SQLite local e indexa com algoritmo dinâmico de siglas."""
        try:
            ruas_db = listar_ruas(apenas_ativas=True)
            if ruas_db:
                self._ruas_todas = [r["nome"] for r in ruas_db]
                self._ruas_map = {r["nome"]: r for r in ruas_db}
            else:
                self._ruas_todas = list(RUAS_DOIS_IRMAOS)
                self._ruas_map = {}
        except Exception:
            self._ruas_todas = list(RUAS_DOIS_IRMAOS)
            self._ruas_map = {}

        self._ruas_indices = [
            (rua, _strip_accents(rua), gerar_acronimos_rua(rua))
            for rua in self._ruas_todas
        ]

    def _filtrar_grid_ruas(self, *_):
        """Filtro com debounce de 180ms para evitar engasgos da UI ao digitar."""
        if self._debounce_id:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(180, self._executar_filtro_ruas)

    def _executar_filtro_ruas(self):
        """
        Executa a busca inteligente de ruas combinando:
        1. Busca textual parcial (sem distinção de maiúsculas/minúsculas e sem acentos).
        2. Busca por siglas e acrônimos gerados automaticamente para cada via.
        3. Limite de renderização aos 30 resultados mais relevantes (performance CustomTkinter).
        """
        self._debounce_id = None
        filtro_raw = self._rua_var.get().strip()
        if not filtro_raw:
            self._renderizar_grid_ruas(self._ruas_todas[:30])
            return

        filtro_norm = _strip_accents(filtro_raw)

        scored_matches = []
        for rua, rua_norm, acronyms in self._ruas_indices:
            score = 0
            if filtro_norm in acronyms:
                score += 100
            words_norm = rua_norm.split()
            if any(w.startswith(filtro_norm) for w in words_norm):
                score += 50
            elif filtro_norm in rua_norm:
                score += 10

            if score > 0:
                scored_matches.append((score, rua))

        if scored_matches:
            scored_matches.sort(key=lambda x: (-x[0], x[1]))
            ruas_filtradas = [m[1] for m in scored_matches[:30]]
        else:
            ruas_filtradas = self._ruas_todas[:30]

        self._renderizar_grid_ruas(ruas_filtradas)

    def _selecionar_rua(self, rua: str):
        self._rua_var.set(rua)
        # Atualizar destaque visual de todos os botões no grid
        for nome_btn, btn in self._rua_botoes:
            is_match = (nome_btn.lower() == rua.lower())
            btn.configure(
                fg_color=COR_PRIMARIA if is_match else "#282828",
                hover_color=COR_PRIMARIA_HVR if is_match else "#3A3A3A",
                text_color="#FFFFFF" if is_match else "#DDDDDD"
            )

        # Sugestão automática de bairro e taxa associados à via se disponíveis
        rua_info = getattr(self, "_ruas_map", {}).get(rua)
        if rua_info:
            bairro_rua = rua_info.get("bairro")
            if bairro_rua and not self._bairro_sel.get():
                self._selecionar_bairro(bairro_rua)

            taxa_rua = float(rua_info.get("taxa") or 0.0)
            if taxa_rua > 0:
                try:
                    taxa_atual = float(self._taxa_var.get().replace(",", "."))
                except ValueError:
                    taxa_atual = 0.0
                if taxa_atual == 0.0:
                    self._selecionar_taxa(taxa_rua)

    def _selecionar_bairro(self, bairro: str, selecionado: bool = True):
        if selecionado:
            self._bairro_sel.set(bairro)
            for chip in self._bairro_chips:
                chip.set_selected(chip._text == bairro)
        else:
            if self._bairro_sel.get() == bairro:
                self._bairro_sel.set("")
            for chip in self._bairro_chips:
                if chip._text == bairro:
                    chip.set_selected(False)

    def _carregar_chips_taxas(self):
        for w in self._taxas_chips_frame.winfo_children():
            w.destroy()

        self._taxa_chips.clear()
        taxas_db = listar_taxas(apenas_ativas=True)

        if not taxas_db:
            opcoes = [(0.0, "Grátis")] + [(t, f"R$ {int(t) if t == int(t) else t}") for t in TAXAS_RAPIDAS]
        else:
            opcoes = [(t["valor"], t["label"]) for t in taxas_db]

        for idx, (val, label) in enumerate(opcoes):
            chip = ChipButton(
                self._taxas_chips_frame,
                text=label,
                on_select=lambda t, s, v=val: self._selecionar_taxa(v) if s else None
            )
            chip.grid(row=idx // 3, column=idx % 3, padx=4, pady=4, sticky="w")
            self._taxa_chips.append(chip)

    def _selecionar_taxa(self, valor: float):
        for chip in self._taxa_chips:
            chip.set_selected(False)

        val_str = f"{valor:.2f}".replace(".", ",")
        for chip in self._taxa_chips:
            txt = chip._text.replace("R$ ", "").replace("Grátis", "0").strip()
            try:
                if abs(float(txt.replace(",", ".")) - valor) < 0.01:
                    chip.set_selected(True)
                    break
            except ValueError:
                if valor == 0 and "grátis" in chip._text.lower():
                    chip.set_selected(True)
                    break

        self._taxa_var.set(str(valor).replace(".", ","))
        self._atualizar_resumo()

    def _on_taxa_change(self, *_):
        self._atualizar_resumo()

    def _atualizar_resumo(self):
        sub = self._state.get("subtotal", 0)
        try:
            taxa_str = self._taxa_var.get().replace(",", ".").strip()
            taxa = float(taxa_str) if taxa_str else 0
        except ValueError:
            taxa = 0

        self._state["taxa_entrega"] = taxa
        total = sub + taxa
        self._state["total"] = total

        self._sub_lbl.configure(text=f"Subtotal:     R$ {sub:.2f}".replace(".", ","))
        self._taxa_lbl.configure(text=f"Taxa entrega:  R$ {taxa:.2f}".replace(".", ","))
        self._total_lbl.configure(text=f"TOTAL:        R$ {total:.2f}".replace(".", ","))

    def _avancar(self):
        self._state["cliente_nome"] = self._nome_var.get().strip()
        self._state["cliente_fone"] = self._fone_var.get().strip()
        self._state["rua"]          = self._rua_var.get().strip()
        self._state["numero"]       = self._num_var.get().strip()
        self._state["complemento"]  = self._comp_var.get().strip()
        self._state["bairro"]       = self._bairro_sel.get().strip()
        self._state["referencia"]   = self._ref_var.get().strip()
        self._atualizar_resumo()
        self._on_next()

    def limpar_campos(self):
        """Limpa todos os campos da tela de entrega para um novo pedido."""
        self._nome_var.set("")
        self._fone_var.set("")
        self._rua_var.set("")
        self._num_var.set("")
        self._comp_var.set("")
        self._ref_var.set("")
        self._bairro_sel.set("")
        self._taxa_var.set("0")
        for chip in self._bairro_chips:
            chip.set_selected(False)
        for chip in self._taxa_chips:
            chip.set_selected(False)
        self._carregar_ruas()
        self._renderizar_grid_ruas(self._ruas_todas[:30])

    def on_show(self):
        """Chamado quando a tela fica visível. Sincroniza campos com o estado atual."""
        self._carregar_ruas()
        # Se for um novo pedido (sem dados de cliente nem endereço no state), limpa a tela
        if not self._state.get("cliente_nome") and not self._state.get("rua"):
            self.limpar_campos()
        else:
            # Sincroniza bairro com o estado atual
            b_atual = self._state.get("bairro", "").strip()
            self._bairro_sel.set(b_atual)
            for chip in self._bairro_chips:
                chip.set_selected(chip._text == b_atual if b_atual else False)

        self._carregar_chips_taxas()
        self._atualizar_resumo()

