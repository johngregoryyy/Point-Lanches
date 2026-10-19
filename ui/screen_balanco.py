# ui/screen_balanco.py - Tela de Balanço Geral e Fechamento Financeiro
# =============================================================================

from datetime import datetime
import customtkinter as ctk

from database.db import calcular_balanco_mensal
from config import (
    COR_PRIMARIA, COR_PRIMARIA_HVR, COR_VERDE, COR_VERDE_HVR,
    COR_VERMELHO, COR_VERMELHO_HVR, COR_CINZA_BARRA,
    COR_TEXTO_SUAVE, COR_AZUL_POINT, COR_TEXTO
)


class ScreenBalanco(ctk.CTkToplevel):
    """
    Janela Toplevel isolada de Balanço Geral & Relatório Financeiro Mensal.
    Apresenta:
      - Filtro por Mês e Ano com atualização dinâmica instantânea
      - 4 Cards de Destaque (Faturamento Total, Qtd. Pedidos, Taxas Tele, Ticket Médio)
      - Banner de Lucro Bruto Estimado (Backend preparado para insumos)
      - Gráfico Visual de Barras com Proporção de Meios de Pagamento (PIX, Dinheiro, Débito, Crédito)
      - Detalhamento tabular completo discriminado por modalidade
      - Ação de Copiar Resumo para a Área de Transferência
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("📊  Balanço Geral & Fechamento Financeiro - Point Lanches")

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        # Otimizado para resoluções 1366x768 e Full HD
        mw = min(1080, sw - 40)
        mh = min(620, sh - 85)
        self.geometry(f"{mw}x{mh}")
        self.minsize(860, 480)
        self.grab_set()
        self.resizable(True, True)

        ctk.set_appearance_mode("Dark")

        # Centralizar na tela
        px = max(10, (sw - mw) // 2)
        py = max(10, (sh - mh) // 2)
        self.geometry(f"+{px}+{py}")

        self._build_ui()

    def _build_ui(self):
        # ── 1. Topo: Título e Filtro de Período ──
        header = ctk.CTkFrame(self, height=54, fg_color="#181818", corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Título
        ctk.CTkLabel(
            header,
            text="📊  BALANÇO GERAL / FECHAMENTO FINANCEIRO",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COR_PRIMARIA
        ).pack(side="left", padx=16)

        # Seletor de Período
        filtro_box = ctk.CTkFrame(header, fg_color="transparent")
        filtro_box.pack(side="right", padx=16)

        ctk.CTkLabel(
            filtro_box, text="📅 Mês:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_TEXTO_SUAVE
        ).pack(side="left", padx=(0, 4))

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

        ctk.CTkLabel(
            filtro_box, text="Ano:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_TEXTO_SUAVE
        ).pack(side="left", padx=(8, 4))

        anos = [str(y) for y in range(now.year - 2, now.year + 4)]
        self._opt_ano = ctk.CTkOptionMenu(
            filtro_box, variable=self._ano_var,
            values=anos, width=95, height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#2D3748", button_color="#4A5568",
            command=lambda _: self._atualizar_balanco()
        )
        self._opt_ano.pack(side="left", padx=4)

        ctk.CTkButton(
            filtro_box, text="🔄 Atualizar",
            width=100, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COR_PRIMARIA, hover_color=COR_PRIMARIA_HVR,
            corner_radius=6,
            command=self._atualizar_balanco
        ).pack(side="left", padx=(8, 0))

        # ── 2. Container Central com Scroll ──
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=10)
        scroll.columnconfigure(0, weight=1)

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

        # ── 5. Detalhamento Tabular por Modalidade ──
        table_card = ctk.CTkFrame(scroll, fg_color=COR_CINZA_BARRA, corner_radius=10)
        table_card.pack(fill="x", pady=(0, 12))
        table_card.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            table_card,
            text="💳  DETALHAMENTO CONSOLIDADO POR MODALIDADE",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_TEXTO_SUAVE
        ).pack(anchor="w", padx=16, pady=(12, 8))

        # Cabeçalho da tabela
        th = ctk.CTkFrame(table_card, fg_color="#1E1E1E", height=32, corner_radius=6)
        th.pack(fill="x", padx=12, pady=(0, 4))
        th.columnconfigure(0, weight=2)
        th.columnconfigure(1, weight=1)
        th.columnconfigure(2, weight=1)
        th.columnconfigure(3, weight=1)

        ctk.CTkLabel(th, text="Forma de Pagamento", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=0, padx=12, sticky="w")
        ctk.CTkLabel(th, text="Qtd. Pedidos", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=1, padx=8, sticky="w")
        ctk.CTkLabel(th, text="Total Arrecadado (R$)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=2, padx=8, sticky="e")
        ctk.CTkLabel(th, text="Participação (%)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE).grid(row=0, column=3, padx=12, sticky="e")

        self._table_rows_frame = ctk.CTkFrame(table_card, fg_color="transparent")
        self._table_rows_frame.pack(fill="x", padx=12, pady=(0, 12))

        # ── 6. Barra de Ações Inferior ──
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

        # Carga inicial dos dados
        self._atualizar_balanco()

    def _atualizar_balanco(self):
        mes_str = self._mes_var.get()
        ano_str = self._ano_var.get()
        try:
            mes = int(mes_str.split(" - ")[0])
            ano = int(ano_str)
        except Exception:
            now = datetime.now()
            mes = now.month
            ano = now.year

        self._dados_atuais = calcular_balanco_mensal(mes, ano)
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

        # ── Renderizar Linhas da Tabela ──
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
            row.columnconfigure(0, weight=2)
            row.columnconfigure(1, weight=1)
            row.columnconfigure(2, weight=1)
            row.columnconfigure(3, weight=1)

            ctk.CTkLabel(
                row, text=f"{conf['icone']}  {k}",
                font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
            ).grid(row=0, column=0, padx=12, sticky="w")

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
            ).grid(row=0, column=3, padx=12, sticky="e")

    def _copiar_resumo(self):
        """Copia os dados consolidados do mês atual para o clipboard."""
        if not hasattr(self, "_dados_atuais"):
            return

        dados = self._dados_atuais
        mes_nome = self._mes_var.get()
        ano = self._ano_var.get()

        fat_fmt = f"R$ {dados['faturamento_total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        tax_fmt = f"R$ {dados['total_taxas']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        tm_fmt = f"R$ {dados['ticket_medio']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        lucro_fmt = f"R$ {dados['lucro_bruto']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        linhas = [
            f"=== BALANÇO MENSAL - POINT LANCHES ===",
            f"Período: {mes_nome} / {ano}",
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

        texto_final = "\n".join(linhas)

        self.clipboard_clear()
        self.clipboard_append(texto_final)
        self.update()

        self._copy_feedback_lbl.configure(text="✅ Resumo copiado para a Área de Transferência!")
        self.after(3000, lambda: self._copy_feedback_lbl.configure(text=""))
