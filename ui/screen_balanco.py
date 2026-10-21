# ui/screen_balanco.py - Tela de Balanço Geral e Fechamento Financeiro
# =============================================================================

from datetime import datetime
import customtkinter as ctk

from database.db import calcular_balanco_mensal, ranking_produtos_vendidos, obter_estatisticas_pico
from config import (
    COR_PRIMARIA, COR_PRIMARIA_HVR, COR_VERDE, COR_VERDE_HVR,
    COR_VERMELHO, COR_VERMELHO_HVR, COR_CINZA_BARRA,
    COR_TEXTO_SUAVE, COR_AZUL_POINT, COR_TEXTO
)


class ScreenBalanco(ctk.CTkToplevel):
    """
    Janela Toplevel isolada de Balanço Geral & Relatório Financeiro Mensal/Anual.
    Apresenta:
      - Filtro por Período: alternância instantânea entre Por Mês e Visão Anual
      - 4 Cards de Destaque (Faturamento Total, Qtd. Pedidos, Taxas Tele, Ticket Médio)
      - Banner de Lucro Bruto Estimado & Insumos
      - Gráfico Visual de Barras com Proporção de Meios de Pagamento
      - Detalhamento tabular completo discriminado por modalidade com alinhamento rigoroso
      - Relatório completo de Vendas por Item do Cardápio (Ranking com busca e ordenação)
      - Ação de Copiar Resumo para a Área de Transferência
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("📊  Balanço Geral & Fechamento Financeiro - Point Lanches")

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        # Otimizado para resoluções 1366x768 e Full HD
        mw = min(1120, sw - 40)
        mh = min(640, sh - 80)
        self.geometry(f"{mw}x{mh}")
        self.minsize(880, 500)
        self.grab_set()
        self.resizable(True, True)

        ctk.set_appearance_mode("Dark")

        # Centralizar na tela
        px = max(10, (sw - mw) // 2)
        py = max(10, (sh - mh) // 2)
        self.geometry(f"+{px}+{py}")

        self._produtos_ranking_dados = []
        self._build_ui()

    def _build_ui(self):
        # ── 1. Topo: Título e Filtro de Período ──
        header = ctk.CTkFrame(self, height=56, fg_color="#181818", corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Título
        ctk.CTkLabel(
            header,
            text="📊  BALANÇO GERAL / DASHBOARD",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COR_PRIMARIA
        ).pack(side="left", padx=16)

        # Seletor de Período
        filtro_box = ctk.CTkFrame(header, fg_color="transparent")
        filtro_box.pack(side="right", padx=16)

        # Seletor de Modo: Mensal vs Anual
        self._seg_periodo = ctk.CTkSegmentedButton(
            filtro_box, values=["📅 Por Mês", "📆 Visão Anual"],
            command=self._on_mudar_tipo_periodo,
            height=32, font=ctk.CTkFont(size=12, weight="bold"),
            selected_color=COR_PRIMARIA, selected_hover_color=COR_PRIMARIA_HVR
        )
        self._seg_periodo.set("📅 Por Mês")
        self._seg_periodo.pack(side="left", padx=(0, 10))

        # Seletor de Mês
        self._lbl_mes = ctk.CTkLabel(
            filtro_box, text="Mês:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_TEXTO_SUAVE
        )
        self._lbl_mes.pack(side="left", padx=(0, 4))

        now = datetime.now()
        meses_nomes = [
            "01 - Janeiro", "02 - Fevereiro", "03 - Março", "04 - Abril",
            "05 - Maio", "06 - Junho", "07 - Julho", "08 - Agosto",
            "09 - Setembro", "10 - Outubro", "11 - Novembro", "12 - Dezembro"
        ]
        self._mes_var = ctk.StringVar(value=meses_nomes[now.month - 1])
        self._ano_var = ctk.StringVar(value=str(now.year))

        self._opt_mes = ctk.CTkOptionMenu(
            filtro_box, variable=self._mes_var,
            values=meses_nomes, width=145, height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#2D3748", button_color="#4A5568",
            command=lambda _: self._atualizar_balanco()
        )
        self._opt_mes.pack(side="left", padx=4)

        # Seletor de Ano
        ctk.CTkLabel(
            filtro_box, text="Ano:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_TEXTO_SUAVE
        ).pack(side="left", padx=(8, 4))

        anos = [str(y) for y in range(now.year - 2, now.year + 4)]
        self._opt_ano = ctk.CTkOptionMenu(
            filtro_box, variable=self._ano_var,
            values=anos, width=90, height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#2D3748", button_color="#4A5568",
            command=lambda _: self._atualizar_balanco()
        )
        self._opt_ano.pack(side="left", padx=4)

        ctk.CTkButton(
            filtro_box, text="🔄 Atualizar",
            width=95, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COR_PRIMARIA, hover_color=COR_PRIMARIA_HVR,
            corner_radius=6,
            command=self._atualizar_balanco
        ).pack(side="left", padx=(8, 0))

        # ── 2. Container Central com Scroll ──
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=10)
        scroll.columnconfigure(0, weight=1)

        # Subtítulo do Período Ativo
        self._lbl_periodo_ativo = ctk.CTkLabel(
            scroll, text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_AZUL_POINT, anchor="w"
        )
        self._lbl_periodo_ativo.pack(fill="x", pady=(0, 8), padx=2)

        # ── 3. Cards de Métricas Principais ──
        cards_row = ctk.CTkFrame(scroll, fg_color="transparent")
        cards_row.pack(fill="x", pady=(0, 10))
        for c in range(4):
            cards_row.columnconfigure(c, weight=1)

        # Card 1: Faturamento Total
        c1 = ctk.CTkFrame(cards_row, fg_color=COR_CINZA_BARRA, corner_radius=10, height=88)
        c1.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        c1.pack_propagate(False)
        ctk.CTkLabel(c1, text="FATURAMENTO TOTAL", font=ctk.CTkFont(size=11, weight="bold"), text_color=COR_TEXTO_SUAVE).pack(pady=(10, 2), padx=12, anchor="w")
        self._lbl_fat_total = ctk.CTkLabel(c1, text="R$ 0,00", font=ctk.CTkFont(size=20, weight="bold"), text_color=COR_VERDE)
        self._lbl_fat_total.pack(padx=12, anchor="w")

        # Card 2: Total de Pedidos Realizados
        c2 = ctk.CTkFrame(cards_row, fg_color=COR_CINZA_BARRA, corner_radius=10, height=88)
        c2.grid(row=0, column=1, sticky="ew", padx=3)
        c2.pack_propagate(False)
        ctk.CTkLabel(c2, text="PEDIDOS REALIZADOS", font=ctk.CTkFont(size=11, weight="bold"), text_color=COR_TEXTO_SUAVE).pack(pady=(10, 2), padx=12, anchor="w")
        self._lbl_qtd_pedidos = ctk.CTkLabel(c2, text="0 pedidos", font=ctk.CTkFont(size=20, weight="bold"), text_color=COR_AZUL_POINT)
        self._lbl_qtd_pedidos.pack(padx=12, anchor="w")

        # Card 3: Taxas de Entrega
        c3 = ctk.CTkFrame(cards_row, fg_color=COR_CINZA_BARRA, corner_radius=10, height=88)
        c3.grid(row=0, column=2, sticky="ew", padx=3)
        c3.pack_propagate(False)
        ctk.CTkLabel(c3, text="TAXAS DE TELE-ENTREGA", font=ctk.CTkFont(size=11, weight="bold"), text_color=COR_TEXTO_SUAVE).pack(pady=(10, 2), padx=12, anchor="w")
        self._lbl_taxas_total = ctk.CTkLabel(c3, text="R$ 0,00", font=ctk.CTkFont(size=20, weight="bold"), text_color="#38BDF8")
        self._lbl_taxas_total.pack(padx=12, anchor="w")

        # Card 4: Ticket Médio
        c4 = ctk.CTkFrame(cards_row, fg_color=COR_CINZA_BARRA, corner_radius=10, height=88)
        c4.grid(row=0, column=3, sticky="ew", padx=(6, 0))
        c4.pack_propagate(False)
        ctk.CTkLabel(c4, text="TICKET MÉDIO", font=ctk.CTkFont(size=11, weight="bold"), text_color=COR_TEXTO_SUAVE).pack(pady=(10, 2), padx=12, anchor="w")
        self._lbl_ticket_medio = ctk.CTkLabel(c4, text="R$ 0,00", font=ctk.CTkFont(size=20, weight="bold"), text_color="#A78BFA")
        self._lbl_ticket_medio.pack(padx=12, anchor="w")

        # ── Banner de Lucro Bruto Estimado & Insumos ──
        banner_lucro = ctk.CTkFrame(scroll, fg_color="#1E2430", corner_radius=8, height=38)
        banner_lucro.pack(fill="x", pady=(0, 12))
        banner_lucro.pack_propagate(False)
        self._lbl_lucro_bruto = ctk.CTkLabel(
            banner_lucro,
            text="💰  Lucro Bruto: R$ 0,00   │   Custos de Insumos: R$ 0,00 (Preparado no SQLite)",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#E2E8F0"
        )
        self._lbl_lucro_bruto.pack(side="left", padx=14, pady=8)

        # ── 4. Gráfico Visual Nativo de Meios de Pagamento ──
        chart_card = ctk.CTkFrame(scroll, fg_color=COR_CINZA_BARRA, corner_radius=10)
        chart_card.pack(fill="x", pady=(0, 12))
        chart_card.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            chart_card,
            text="📊  DISTRIBUIÇÃO VISUAL DAS VENDAS POR FORMA DE PAGAMENTO",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_PRIMARIA
        ).pack(anchor="w", padx=16, pady=(12, 8))

        self._chart_container = ctk.CTkFrame(chart_card, fg_color="transparent")
        self._chart_container.pack(fill="x", padx=16, pady=(0, 14))

        # ── 5. Detalhamento Tabular por Modalidade (Alinhamento Rigoroso) ──
        table_card = ctk.CTkFrame(scroll, fg_color=COR_CINZA_BARRA, corner_radius=10)
        table_card.pack(fill="x", pady=(0, 12))
        table_card.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            table_card,
            text="💳  DETALHAMENTO CONSOLIDADO POR MODALIDADE",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_TEXTO_SUAVE
        ).pack(anchor="w", padx=16, pady=(12, 8))

        # Cabeçalho da tabela com minsize e alinhamentos padronizados
        th = ctk.CTkFrame(table_card, fg_color="#1E1E1E", height=32, corner_radius=6)
        th.pack(fill="x", padx=12, pady=(0, 4))
        th.columnconfigure(0, weight=2, minsize=160)
        th.columnconfigure(1, weight=1, minsize=100)
        th.columnconfigure(2, weight=1, minsize=130)
        th.columnconfigure(3, weight=1, minsize=90)

        ctk.CTkLabel(th, text="Forma de Pagamento", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=0, padx=(12, 8), sticky="w")
        ctk.CTkLabel(th, text="Qtd. Pedidos", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=1, padx=8, sticky="w")
        ctk.CTkLabel(th, text="Total Arrecadado (R$)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=2, padx=8, sticky="e")
        ctk.CTkLabel(th, text="Participação (%)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=3, padx=(8, 12), sticky="e")

        self._table_rows_frame = ctk.CTkFrame(table_card, fg_color="transparent")
        self._table_rows_frame.pack(fill="x", padx=12, pady=(0, 12))

        # ── 5B. Gráfico Visual de Picos de Pedidos (Horários e Dias) ──
        picos_card = ctk.CTkFrame(scroll, fg_color=COR_CINZA_BARRA, corner_radius=10)
        picos_card.pack(fill="x", pady=(0, 12))
        picos_card.columnconfigure(0, weight=1)

        picos_top = ctk.CTkFrame(picos_card, fg_color="transparent")
        picos_top.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            picos_top,
            text="⏰  HORÁRIOS & DIAS DE MAIOR PICO DE PEDIDOS",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_PRIMARIA
        ).pack(side="left")

        # Seletor de visualização dos picos: Por Horário, Por Dia da Semana, Evolução
        self._seg_picos_tipo = ctk.CTkSegmentedButton(
            picos_top,
            values=["⏰ Por Horário do Dia", "📅 Por Dia da Semana", "📆 Evolução Diária / Mensal"],
            command=lambda _: self._renderizar_grafico_picos(),
            height=28, font=ctk.CTkFont(size=11, weight="bold"),
            selected_color=COR_PRIMARIA, selected_hover_color=COR_PRIMARIA_HVR
        )
        self._seg_picos_tipo.set("⏰ Por Horário do Dia")
        self._seg_picos_tipo.pack(side="right")

        # Banner de Destaque / Resumo do Pico (ex: Horário mais movimentado)
        self._picos_highlight_frame = ctk.CTkFrame(picos_card, fg_color="#1E2430", corner_radius=8, height=36)
        self._picos_highlight_frame.pack(fill="x", padx=16, pady=(2, 10))
        self._picos_highlight_frame.pack_propagate(False)

        self._lbl_picos_destaque = ctk.CTkLabel(
            self._picos_highlight_frame,
            text="🔥 Identificando horário de maior movimento...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#F59E0B"
        )
        self._lbl_picos_destaque.pack(side="left", padx=12, pady=6)

        # Container dos gráficos/barras
        self._picos_container = ctk.CTkFrame(picos_card, fg_color="transparent")
        self._picos_container.pack(fill="x", padx=16, pady=(0, 14))

        # ── 6. Relatório / Ranking Completo de Vendas por Item do Cardápio ──
        ranking_card = ctk.CTkFrame(scroll, fg_color=COR_CINZA_BARRA, corner_radius=10)
        ranking_card.pack(fill="x", pady=(0, 12))
        ranking_card.columnconfigure(0, weight=1)

        ranking_top = ctk.CTkFrame(ranking_card, fg_color="transparent")
        ranking_top.pack(fill="x", padx=16, pady=(12, 8))

        self._lbl_ranking_titulo = ctk.CTkLabel(
            ranking_top,
            text="🍔  VENDAS POR PRODUTO / RANKING DO CARDÁPIO",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_PRIMARIA
        )
        self._lbl_ranking_titulo.pack(side="left")

        # Busca rápida no ranking
        self._ranking_busca_var = ctk.StringVar()
        entry_busca = ctk.CTkEntry(
            ranking_top, width=220, height=30,
            placeholder_text="🔍 Filtrar produto...",
            textvariable=self._ranking_busca_var,
            font=ctk.CTkFont(size=11)
        )
        entry_busca.pack(side="right")
        entry_busca.bind("<KeyRelease>", lambda _: self._filtrar_ranking_produtos())

        # Cabeçalho da tabela de ranking
        r_th = ctk.CTkFrame(ranking_card, fg_color="#1E1E1E", height=32, corner_radius=6)
        r_th.pack(fill="x", padx=12, pady=(0, 4))
        r_th.columnconfigure(0, weight=0, minsize=55)
        r_th.columnconfigure(1, weight=3, minsize=200)
        r_th.columnconfigure(2, weight=1, minsize=130)
        r_th.columnconfigure(3, weight=1, minsize=90)
        r_th.columnconfigure(4, weight=1, minsize=130)
        r_th.columnconfigure(5, weight=1, minsize=90)

        ctk.CTkLabel(r_th, text="Pos.", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=0, padx=(12, 4), sticky="w")
        ctk.CTkLabel(r_th, text="Produto do Cardápio", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=1, padx=8, sticky="w")
        ctk.CTkLabel(r_th, text="Categoria", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=2, padx=8, sticky="w")
        ctk.CTkLabel(r_th, text="Qtd. Vendida", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=3, padx=8)
        ctk.CTkLabel(r_th, text="Total Faturado (R$)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=4, padx=8, sticky="e")
        ctk.CTkLabel(r_th, text="Part. (%)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=5, padx=(8, 12), sticky="e")

        self._ranking_rows_frame = ctk.CTkFrame(ranking_card, fg_color="transparent")
        self._ranking_rows_frame.pack(fill="x", padx=12, pady=(0, 12))

        # ── 7. Barra de Ações Inferior ──
        actions_bar = ctk.CTkFrame(self, height=48, fg_color="#181818", corner_radius=0)
        actions_bar.pack(fill="x", side="bottom")
        actions_bar.pack_propagate(False)

        ctk.CTkButton(
            actions_bar, text="📋  Copiar Resumo Financeiro",
            width=210, height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#334155", hover_color="#475569",
            corner_radius=6,
            command=self._copiar_resumo
        ).pack(side="left", padx=16, pady=7)

        self._copy_feedback_lbl = ctk.CTkLabel(
            actions_bar, text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_VERDE
        )
        self._copy_feedback_lbl.pack(side="left", padx=8)

        ctk.CTkButton(
            actions_bar, text="Fechar",
            width=100, height=34,
            font=ctk.CTkFont(size=12),
            fg_color="#3A3A3A", hover_color="#4A4A4A",
            corner_radius=6,
            command=self.destroy
        ).pack(side="right", padx=16, pady=7)

        from ui.components.loading import LoadingOverlay
        self._overlay = LoadingOverlay(self, text="Consolidando dados financeiros...")

        # Carga inicial dos dados
        self._atualizar_balanco()

    def _on_mudar_tipo_periodo(self, valor):
        if valor == "📆 Visão Anual":
            self._opt_mes.configure(state="disabled")
            self._lbl_mes.configure(text_color="#555555")
        else:
            self._opt_mes.configure(state="normal")
            self._lbl_mes.configure(text_color=COR_TEXTO_SUAVE)
        self._atualizar_balanco()

    def _atualizar_balanco(self):
        if hasattr(self, "_overlay"):
            self._overlay.show("Consolidando balanço financeiro...")
            self.after(50, self._executar_atualizacao_balanco)
        else:
            self._executar_atualizacao_balanco()

    def _executar_atualizacao_balanco(self):
        try:
            is_anual = (self._seg_periodo.get() == "📆 Visão Anual")
            ano_str = self._ano_var.get()
            try:
                ano = int(ano_str)
            except Exception:
                ano = datetime.now().year

            if is_anual:
                mes = None
                periodo_rotulo = f"📅 Período: Ano Completo de {ano} (Acumulado de 12 Meses)"
                titulo_ranking = f"🍔  VENDAS POR PRODUTO / RANKING DO CARDÁPIO ({ano} - ACUMULADO ANUAL)"
            else:
                mes_str = self._mes_var.get()
                try:
                    mes = int(mes_str.split(" - ")[0])
                except Exception:
                    mes = datetime.now().month
                periodo_rotulo = f"📅 Período: {mes_str} / {ano}"
                titulo_ranking = f"🍔  VENDAS POR PRODUTO / RANKING DO CARDÁPIO ({mes_str.split(' - ')[1]}/{ano})"

            self._lbl_periodo_ativo.configure(text=periodo_rotulo)
            self._lbl_ranking_titulo.configure(text=titulo_ranking)

            self._dados_atuais = calcular_balanco_mensal(mes=mes, ano=ano)
            dados = self._dados_atuais

            fat = dados["faturamento_total"]
            qtd = dados["total_pedidos"]
            tax = dados["total_taxas"]
            tm = dados["ticket_medio"]
            custo = dados["custo_insumos"]
            lucro = dados["lucro_bruto"]

            fat_fmt = f"R$ {fat:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            tax_fmt = f"R$ {tax:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            tm_fmt = f"R$ {tm:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            custo_fmt = f"R$ {custo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            lucro_fmt = f"R$ {lucro:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            self._lbl_fat_total.configure(text=fat_fmt)
            self._lbl_qtd_pedidos.configure(text=f"{qtd} pedidos")
            self._lbl_taxas_total.configure(text=tax_fmt)
            self._lbl_ticket_medio.configure(text=tm_fmt)
            self._lbl_lucro_bruto.configure(
                text=f"💰  Lucro Bruto Estimado: {lucro_fmt}   │   Custos de Insumos: {custo_fmt} (Módulo preparado no SQLite)"
            )

            # ── Renderizar Gráfico Visual de Barras ──
            for w in self._chart_container.winfo_children():
                w.destroy()

            ordem_mod = ["PIX", "Dinheiro", "Cartão de Débito", "Cartão de Crédito", "Outros"]
            config_visual = {
                "PIX":              {"icone": "📱", "cor": "#10B981"},  # Verde esmeralda
                "Dinheiro":         {"icone": "💵", "cor": "#0284C7"},  # Azul Point Primário
                "Cartão de Débito": {"icone": "💳", "cor": "#38BDF8"},  # Azul celeste
                "Cartão de Crédito":{"icone": "💳", "cor": "#818CF8"},  # Roxo / Índigo
                "Outros":           {"icone": "🧾", "cor": "#94A3B8"},  # Cinza ardósia
            }

            for k in ordem_mod:
                item = dados["modalidades"].get(k, {"total": 0.0, "qtd": 0})
                if k == "Outros" and item["qtd"] == 0:
                    continue

                part = (item["total"] / fat * 100) if fat > 0 else 0.0
                prop = (item["total"] / fat) if fat > 0 else 0.0
                conf = config_visual.get(k, {"icone": "💳", "cor": COR_PRIMARIA})

                row_chart = ctk.CTkFrame(self._chart_container, fg_color="transparent", height=32)
                row_chart.pack(fill="x", pady=4)
                row_chart.pack_propagate(False)

                # Rótulo Modalidade
                ctk.CTkLabel(
                    row_chart,
                    text=f"{conf['icone']}  {k}",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    width=150, anchor="w"
                ).pack(side="left", padx=(4, 8))

                # Barra de Progresso / Proporção
                bar = ctk.CTkProgressBar(
                    row_chart,
                    height=16,
                    corner_radius=8,
                    fg_color="#262D3D",
                    progress_color=conf["cor"]
                )
                bar.pack(side="left", fill="x", expand=True, padx=(0, 12))
                bar.set(prop)

                # Porcentagem
                ctk.CTkLabel(
                    row_chart,
                    text=f"{part:5.1f} %",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=conf["cor"] if part > 0 else COR_TEXTO_SUAVE,
                    width=65, anchor="e"
                ).pack(side="left", padx=4)

                # Valor Total R$
                val_fmt = f"R$ {item['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                ctk.CTkLabel(
                    row_chart,
                    text=val_fmt,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COR_TEXTO,
                    width=110, anchor="e"
                ).pack(side="left", padx=4)

                # Quantidade de Pedidos
                ctk.CTkLabel(
                    row_chart,
                    text=f"({item['qtd']} ped.)",
                    font=ctk.CTkFont(size=11),
                    text_color=COR_TEXTO_SUAVE,
                    width=75, anchor="e"
                ).pack(side="left", padx=(4, 0))

            # ── Renderizar Linhas da Tabela de Modalidades (Alinhamento Rigoroso) ──
            for w in self._table_rows_frame.winfo_children():
                w.destroy()

            for idx, k in enumerate(ordem_mod):
                item = dados["modalidades"].get(k, {"total": 0.0, "qtd": 0})
                if k == "Outros" and item["qtd"] == 0:
                    continue

                part = (item["total"] / fat * 100) if fat > 0 else 0.0
                conf = config_visual.get(k, {"icone": "💳", "cor": COR_PRIMARIA})

                bg = "#252B37" if idx % 2 == 0 else "#1F2430"
                row = ctk.CTkFrame(self._table_rows_frame, fg_color=bg, corner_radius=6, height=36)
                row.pack(fill="x", pady=2)
                row.columnconfigure(0, weight=2, minsize=160)
                row.columnconfigure(1, weight=1, minsize=100)
                row.columnconfigure(2, weight=1, minsize=130)
                row.columnconfigure(3, weight=1, minsize=90)

                ctk.CTkLabel(
                    row, text=f"{conf['icone']}  {k}",
                    font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
                ).grid(row=0, column=0, padx=(12, 8), sticky="w")

                ctk.CTkLabel(
                    row, text=f"{item['qtd']} pedido(s)",
                    font=ctk.CTkFont(size=12), anchor="w"
                ).grid(row=0, column=1, padx=8, sticky="w")

                val_fmt = f"R$ {item['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                ctk.CTkLabel(
                    row, text=val_fmt,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COR_VERDE if item["total"] > 0 else COR_TEXTO_SUAVE
                ).grid(row=0, column=2, padx=8, sticky="e")

                ctk.CTkLabel(
                    row, text=f"{part:.1f} %",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=conf["cor"] if part > 0 else COR_TEXTO_SUAVE
                ).grid(row=0, column=3, padx=(8, 12), sticky="e")

            # ── Carregar e Renderizar Picos de Pedidos (Horários e Dias) ──
            self._estatisticas_pico = obter_estatisticas_pico(mes=mes, ano=ano)
            self._renderizar_grafico_picos()

            # ── Carregar e Renderizar Ranking de Produtos Vendidos ──
            self._produtos_ranking_dados = ranking_produtos_vendidos(mes=mes, ano=ano)
            self._filtrar_ranking_produtos()

        finally:
            if hasattr(self, "_overlay"):
                self._overlay.hide()

    def _renderizar_grafico_picos(self):
        """Renderiza o gráfico de barras dos horários ou dias de maior pico de pedidos."""
        if not hasattr(self, "_estatisticas_pico") or not self._estatisticas_pico:
            return

        for w in self._picos_container.winfo_children():
            w.destroy()

        stats = self._estatisticas_pico
        modo = self._seg_picos_tipo.get()
        tot_ped = stats["tot_pedidos"]

        if tot_ped == 0:
            self._lbl_picos_destaque.configure(
                text="ℹ️ Nenhum pedido registrado no período selecionado.",
                text_color=COR_TEXTO_SUAVE
            )
            ctk.CTkLabel(
                self._picos_container,
                text="Sem dados para exibir gráficos de pico neste período.",
                font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE
            ).pack(pady=16)
            return

        if modo == "⏰ Por Horário do Dia":
            hp = stats.get("hora_pico")
            if hp and hp["qtd"] > 0:
                hp_val_fmt = f"R$ {hp['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                self._lbl_picos_destaque.configure(
                    text=f"🔥 Horário de Maior Pico: {hp['rotulo']} com {hp['qtd']} pedidos ({hp['part']:.1f}% do total) — {hp_val_fmt}",
                    text_color="#F59E0B"
                )
            else:
                self._lbl_picos_destaque.configure(
                    text="⏰ Distribuição de pedidos por faixa horária do dia.",
                    text_color="#38BDF8"
                )

            itens = stats["horas"]
            max_qtd = max((it["qtd"] for it in itens), default=1) or 1

            for it in itens:
                row = ctk.CTkFrame(self._picos_container, fg_color="transparent", height=32)
                row.pack(fill="x", pady=3)
                row.pack_propagate(False)

                eh_pico = (hp and it["hora"] == hp["hora"] and it["qtd"] > 0)
                cor_barra = "#F59E0B" if eh_pico else (COR_PRIMARIA if it["qtd"] > 0 else "#262D3D")
                cor_txt = "#F59E0B" if eh_pico else (COR_TEXTO if it["qtd"] > 0 else COR_TEXTO_SUAVE)

                lbl_txt = f"{'🔥 ' if eh_pico else '⏰ '}{it['rotulo']}"
                ctk.CTkLabel(
                    row, text=lbl_txt,
                    font=ctk.CTkFont(size=12, weight="bold" if eh_pico else "normal"),
                    text_color=cor_txt, width=170, anchor="w"
                ).pack(side="left", padx=(4, 8))

                prop = (it["qtd"] / max_qtd) if max_qtd > 0 else 0.0
                bar = ctk.CTkProgressBar(
                    row, height=16, corner_radius=8,
                    fg_color="#262D3D", progress_color=cor_barra
                )
                bar.pack(side="left", fill="x", expand=True, padx=(0, 12))
                bar.set(prop)

                ctk.CTkLabel(
                    row, text=f"{it['qtd']} ped.",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=cor_txt, width=65, anchor="e"
                ).pack(side="left", padx=4)

                val_fmt = f"R$ {it['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                ctk.CTkLabel(
                    row, text=val_fmt,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COR_VERDE if it["total"] > 0 else COR_TEXTO_SUAVE,
                    width=100, anchor="e"
                ).pack(side="left", padx=4)

                ctk.CTkLabel(
                    row, text=f"({it['part']:.1f}%)",
                    font=ctk.CTkFont(size=11),
                    text_color=COR_TEXTO_SUAVE, width=65, anchor="e"
                ).pack(side="left", padx=(4, 0))

        elif modo == "📅 Por Dia da Semana":
            dp = stats.get("dia_pico")
            if dp and dp["qtd"] > 0:
                dp_val_fmt = f"R$ {dp['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                self._lbl_picos_destaque.configure(
                    text=f"🏆 Dia Mais Movimentado da Semana: {dp['nome']} com {dp['qtd']} pedidos ({dp['part']:.1f}% do total) — {dp_val_fmt}",
                    text_color="#F59E0B"
                )
            else:
                self._lbl_picos_destaque.configure(
                    text="📅 Volume de vendas por dia da semana (Domingo a Sábado).",
                    text_color="#38BDF8"
                )

            itens = stats["dias_semana"]
            max_qtd = max((it["qtd"] for it in itens), default=1) or 1

            for it in itens:
                row = ctk.CTkFrame(self._picos_container, fg_color="transparent", height=32)
                row.pack(fill="x", pady=3)
                row.pack_propagate(False)

                eh_pico = (dp and it["dia_idx"] == dp["dia_idx"] and it["qtd"] > 0)
                cor_barra = "#F59E0B" if eh_pico else (COR_AZUL_POINT if it["qtd"] > 0 else "#262D3D")
                cor_txt = "#F59E0B" if eh_pico else (COR_TEXTO if it["qtd"] > 0 else COR_TEXTO_SUAVE)

                lbl_txt = f"{it['icone']}  {it['nome']}"
                ctk.CTkLabel(
                    row, text=lbl_txt,
                    font=ctk.CTkFont(size=12, weight="bold" if eh_pico else "normal"),
                    text_color=cor_txt, width=170, anchor="w"
                ).pack(side="left", padx=(4, 8))

                prop = (it["qtd"] / max_qtd) if max_qtd > 0 else 0.0
                bar = ctk.CTkProgressBar(
                    row, height=16, corner_radius=8,
                    fg_color="#262D3D", progress_color=cor_barra
                )
                bar.pack(side="left", fill="x", expand=True, padx=(0, 12))
                bar.set(prop)

                ctk.CTkLabel(
                    row, text=f"{it['qtd']} ped.",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=cor_txt, width=65, anchor="e"
                ).pack(side="left", padx=4)

                val_fmt = f"R$ {it['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                ctk.CTkLabel(
                    row, text=val_fmt,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COR_VERDE if it["total"] > 0 else COR_TEXTO_SUAVE,
                    width=100, anchor="e"
                ).pack(side="left", padx=4)

                ctk.CTkLabel(
                    row, text=f"({it['part']:.1f}%)",
                    font=ctk.CTkFont(size=11),
                    text_color=COR_TEXTO_SUAVE, width=65, anchor="e"
                ).pack(side="left", padx=(4, 0))

        else:  # "📆 Evolução Diária / Mensal"
            is_mensal = stats.get("is_mensal", True)
            if is_mensal:
                self._lbl_picos_destaque.configure(
                    text="📆 Evolução de vendas dia a dia no mês selecionado.",
                    text_color="#38BDF8"
                )
            else:
                self._lbl_picos_destaque.configure(
                    text="📆 Distribuição mensal acumulada ao longo do ano.",
                    text_color="#38BDF8"
                )

            itens = stats["periodo"]
            max_qtd = max((it["qtd"] for it in itens), default=1) or 1

            for it in itens:
                if it["qtd"] == 0 and len(itens) > 12:
                    continue  # Omite dias vazios para manter layout limpo

                row = ctk.CTkFrame(self._picos_container, fg_color="transparent", height=32)
                row.pack(fill="x", pady=3)
                row.pack_propagate(False)

                cor_barra = "#818CF8" if it["qtd"] > 0 else "#262D3D"
                cor_txt = COR_TEXTO if it["qtd"] > 0 else COR_TEXTO_SUAVE

                ctk.CTkLabel(
                    row, text=f"📌  {it['rotulo']}",
                    font=ctk.CTkFont(size=12, weight="bold" if it["qtd"] > 0 else "normal"),
                    text_color=cor_txt, width=170, anchor="w"
                ).pack(side="left", padx=(4, 8))

                prop = (it["qtd"] / max_qtd) if max_qtd > 0 else 0.0
                bar = ctk.CTkProgressBar(
                    row, height=16, corner_radius=8,
                    fg_color="#262D3D", progress_color=cor_barra
                )
                bar.pack(side="left", fill="x", expand=True, padx=(0, 12))
                bar.set(prop)

                ctk.CTkLabel(
                    row, text=f"{it['qtd']} ped.",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=cor_txt, width=65, anchor="e"
                ).pack(side="left", padx=4)

                val_fmt = f"R$ {it['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                ctk.CTkLabel(
                    row, text=val_fmt,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COR_VERDE if it["total"] > 0 else COR_TEXTO_SUAVE,
                    width=100, anchor="e"
                ).pack(side="left", padx=4)

                ctk.CTkLabel(
                    row, text=f"({it['part']:.1f}%)",
                    font=ctk.CTkFont(size=11),
                    text_color=COR_TEXTO_SUAVE, width=65, anchor="e"
                ).pack(side="left", padx=(4, 0))

    def _filtrar_ranking_produtos(self):
        """Filtra e renderiza as linhas da tabela de produtos vendidos."""
        for w in self._ranking_rows_frame.winfo_children():
            w.destroy()

        termo = self._ranking_busca_var.get().lower().strip()
        prods = self._produtos_ranking_dados
        if termo:
            prods = [p for p in prods if termo in p["produto_nome"].lower() or termo in p["categoria_nome"].lower()]

        if not prods:
            ctk.CTkLabel(
                self._ranking_rows_frame,
                text="Nenhum item vendido registrado no período selecionado." if not termo else f"Nenhum produto encontrado para '{termo}'.",
                font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE
            ).pack(pady=16)
            return

        fat_total = self._dados_atuais["faturamento_total"] if hasattr(self, "_dados_atuais") else 0.0

        for idx, p in enumerate(prods):
            bg = "#252B37" if idx % 2 == 0 else "#1F2430"
            row = ctk.CTkFrame(self._ranking_rows_frame, fg_color=bg, corner_radius=6, height=36)
            row.pack(fill="x", pady=2)
            row.columnconfigure(0, weight=0, minsize=55)
            row.columnconfigure(1, weight=3, minsize=200)
            row.columnconfigure(2, weight=1, minsize=130)
            row.columnconfigure(3, weight=1, minsize=90)
            row.columnconfigure(4, weight=1, minsize=130)
            row.columnconfigure(5, weight=1, minsize=90)

            # Cor de medalha para os 3 primeiros colocados
            pos = idx + 1
            if pos == 1:
                cor_pos = "#F59E0B"  # Ouro
                pos_txt = "🥇 #1"
            elif pos == 2:
                cor_pos = "#94A3B8"  # Prata
                pos_txt = "🥈 #2"
            elif pos == 3:
                cor_pos = "#CD7F32"  # Bronze
                pos_txt = "🥉 #3"
            else:
                cor_pos = COR_TEXTO_SUAVE
                pos_txt = f"#{pos}"

            ctk.CTkLabel(
                row, text=pos_txt,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=cor_pos
            ).grid(row=0, column=0, padx=(12, 4), sticky="w")

            ctk.CTkLabel(
                row, text=p["produto_nome"],
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w"
            ).grid(row=0, column=1, padx=8, sticky="w")

            ctk.CTkLabel(
                row, text=p["categoria_nome"],
                font=ctk.CTkFont(size=11),
                text_color=COR_TEXTO_SUAVE,
                anchor="w"
            ).grid(row=0, column=2, padx=8, sticky="w")

            ctk.CTkLabel(
                row, text=f"{p['total_qtd']} un.",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COR_AZUL_POINT,
                anchor="center"
            ).grid(row=0, column=3, padx=8)

            val_prod_fmt = f"R$ {p['total_valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            ctk.CTkLabel(
                row, text=val_prod_fmt,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COR_VERDE
            ).grid(row=0, column=4, padx=8, sticky="e")

            part_prod = (p["total_valor"] / fat_total * 100) if fat_total > 0 else 0.0
            ctk.CTkLabel(
                row, text=f"{part_prod:.1f} %",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COR_TEXTO_SUAVE
            ).grid(row=0, column=5, padx=(8, 12), sticky="e")

    def _copiar_resumo(self):
        """Copia os dados consolidados do período selecionado para o clipboard."""
        if not hasattr(self, "_dados_atuais"):
            return

        dados = self._dados_atuais
        is_anual = (self._seg_periodo.get() == "📆 Visão Anual")
        ano = self._ano_var.get()
        periodo_desc = f"Ano Completo {ano}" if is_anual else f"{self._mes_var.get()} / {ano}"

        fat_fmt = f"R$ {dados['faturamento_total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        tax_fmt = f"R$ {dados['total_taxas']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        tm_fmt = f"R$ {dados['ticket_medio']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        lucro_fmt = f"R$ {dados['lucro_bruto']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        linhas = [
            f"=== BALANÇO FINANCEIRO - POINT LANCHES ===",
            f"Período: {periodo_desc}",
            f"Faturamento Total: {fat_fmt}",
            f"Pedidos Realizados: {dados['total_pedidos']}",
            f"Taxas de Tele-Entrega: {tax_fmt}",
            f"Ticket Médio: {tm_fmt}",
            f"Lucro Bruto: {lucro_fmt}",
            "",
            "--- FORMAS DE PAGAMENTO ---"
        ]

        for k in ["PIX", "Dinheiro", "Cartão de Débito", "Cartão de Crédito", "Outros"]:
            item = dados["modalidades"].get(k, {"total": 0.0, "qtd": 0})
            if item["qtd"] > 0:
                val = f"R$ {item['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                part = (item["total"] / dados["faturamento_total"] * 100) if dados["faturamento_total"] > 0 else 0.0
                linhas.append(f"• {k}: {val} ({item['qtd']} pedidos - {part:.1f}%)")

        if hasattr(self, "_estatisticas_pico") and self._estatisticas_pico:
            hp = self._estatisticas_pico.get("hora_pico")
            dp = self._estatisticas_pico.get("dia_pico")
            if (hp and hp["qtd"] > 0) or (dp and dp["qtd"] > 0):
                linhas.append("")
                linhas.append("--- PICOS DE MOVIMENTO ---")
                if hp and hp["qtd"] > 0:
                    linhas.append(f"• Horário de Maior Pico: {hp['rotulo']} ({hp['qtd']} pedidos - {hp['part']:.1f}%)")
                if dp and dp["qtd"] > 0:
                    linhas.append(f"• Dia Mais Movimentado: {dp['nome']} ({dp['qtd']} pedidos - {dp['part']:.1f}%)")

        if self._produtos_ranking_dados:
            linhas.append("")
            linhas.append("--- TOP 5 PRODUTOS MAIS VENDIDOS ---")
            for i, p in enumerate(self._produtos_ranking_dados[:5]):
                v_fmt = f"R$ {p['total_valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                linhas.append(f"{i+1}. {p['produto_nome']} ({p['categoria_nome']}): {p['total_qtd']} un. - {v_fmt}")

        texto_final = "\n".join(linhas)

        self.clipboard_clear()
        self.clipboard_append(texto_final)
        self.update()

        self._copy_feedback_lbl.configure(text="✅ Resumo copiado para a Área de Transferência!")
        self.after(3000, lambda: self._copy_feedback_lbl.configure(text=""))
