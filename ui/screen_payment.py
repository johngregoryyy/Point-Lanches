# ui/screen_payment.py - Tela 3: Forma de pagamento, PIX e impressão
# =============================================================================

import customtkinter as ctk
from database.db import salvar_pedido, get_config
from printer.ticket_formatter import formatar_ticket
from printer.escpos_printer import imprimir_ticket, show_printer_error_popup
from ui.components.widgets import TopBar, habilitar_feedback_clique
from config import (
    COR_PRIMARIA, COR_PRIMARIA_HVR, COR_VERDE, COR_VERDE_HVR,
    COR_VERMELHO, COR_VERMELHO_HVR,
    COR_CINZA_BARRA, COR_FUNDO, COR_TEXTO_SUAVE,
    TROCOS_RAPIDOS, PRINTER_IP_DEFAULT
)


FORMAS_PGTO = [
    ("💰", "Dinheiro"),
    ("📱", "PIX"),
    ("💳", "Débito"),
    ("💳", "Crédito"),
]


class ScreenPayment(ctk.CTkFrame):
    """
    Tela 3 – Forma de pagamento, status de PIX, troco e impressão do pedido.
    Após a impressão, limpa o carrinho e redireciona automaticamente para a tela inicial.
    """

    def __init__(self, master, state: dict,
                 on_back, on_admin, on_novo_pedido,
                 on_historico=None, on_balanco=None, **kwargs):
        super().__init__(master, fg_color=COR_FUNDO, **kwargs)
        self._state          = state
        self._on_back        = on_back
        self._on_novo        = on_novo_pedido
        self._on_historico   = on_historico
        self._on_balanco     = on_balanco
        self._forma_sel      = ctk.StringVar(value="")
        self._troco_para     = ctk.StringVar(value="")
        self._pix_status_var = ctk.StringVar(value="")  # "", "Pago", "Não Pago"

        self._pgto_btns: dict[str, ctk.CTkButton] = {}
        self._pix_btns: dict[str, ctk.CTkButton] = {}

        self._build_ui(on_admin)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self, on_admin):
        TopBar(
            self, "Pagamento",
            on_admin=on_admin,
            on_historico=self._on_historico,
            on_balanco=self._on_balanco
        ).pack(fill="x")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=6)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        # ── Coluna esquerda: forma de pagamento ──
        left = ctk.CTkFrame(body, fg_color=COR_CINZA_BARRA, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=2)
        left.columnconfigure(0, weight=1)

        self._secao(left, "💳  FORMA DE PAGAMENTO", row=0)

        pgto_grid = ctk.CTkFrame(left, fg_color="transparent")
        pgto_grid.grid(row=1, column=0, padx=12, pady=8, sticky="ew")
        pgto_grid.columnconfigure(0, weight=1)
        pgto_grid.columnconfigure(1, weight=1)

        for idx, (emoji, nome) in enumerate(FORMAS_PGTO):
            r, c = divmod(idx, 2)
            btn = ctk.CTkButton(
                pgto_grid,
                text=f"{emoji}  {nome}",
                height=62,
                font=ctk.CTkFont(size=14, weight="bold"),
                corner_radius=10,
                fg_color="#333333",
                hover_color="#444444",
                command=lambda n=nome: self._selecionar_forma(n)
            )
            btn.grid(row=r, column=c, padx=5, pady=5, sticky="ew")
            habilitar_feedback_clique(btn, cor_flash=COR_PRIMARIA_HVR, debounce_ms=100)
            self._pgto_btns[nome] = btn

        # ── Seção PIX (Status selecionável ou branco para caneta) ──
        self._pix_frame = ctk.CTkFrame(left, fg_color="#1F1F1F", corner_radius=10)
        self._pix_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=6)
        self._pix_frame.grid_remove()  # oculto até selecionar PIX

        ctk.CTkLabel(
            self._pix_frame, text="📱  STATUS DO PIX (OPCIONAL):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_PRIMARIA
        ).pack(anchor="w", padx=12, pady=(8, 2))

        pix_btns_row = ctk.CTkFrame(self._pix_frame, fg_color="transparent")
        pix_btns_row.pack(fill="x", padx=12, pady=4)

        btn_pago = ctk.CTkButton(
            pix_btns_row,
            text="✅  Pago",
            height=38, width=110,
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8,
            fg_color="#333", hover_color="#444",
            command=lambda: self._toggle_pix_status("Pago")
        )
        btn_pago.pack(side="left", padx=(0, 6))
        self._pix_btns["Pago"] = btn_pago

        btn_nao_pago = ctk.CTkButton(
            pix_btns_row,
            text="❌  Não Pago",
            height=38, width=110,
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8,
            fg_color="#333", hover_color="#444",
            command=lambda: self._toggle_pix_status("Não Pago")
        )
        btn_nao_pago.pack(side="left", padx=(0, 6))
        self._pix_btns["Não Pago"] = btn_nao_pago

        btn_limpar_pix = ctk.CTkButton(
            pix_btns_row,
            text="⭕  Em Branco",
            height=38, width=100,
            font=ctk.CTkFont(size=12),
            corner_radius=8,
            fg_color="#282828", hover_color="#383838",
            text_color=COR_TEXTO_SUAVE,
            command=self._limpar_pix_status
        )
        btn_limpar_pix.pack(side="left")

        ctk.CTkLabel(
            self._pix_frame,
            text="💡 Se deixar em branco, o cupom imprimirá caixas [  ] para marcação manual com caneta.",
            font=ctk.CTkFont(size=11), text_color=COR_TEXTO_SUAVE, justify="left"
        ).pack(anchor="w", padx=14, pady=(2, 10))

        # ── Seção troco (apenas para dinheiro) ──
        self._troco_frame = ctk.CTkFrame(left, fg_color="transparent")
        self._troco_frame.grid(row=3, column=0, sticky="ew", padx=14, pady=8)
        self._troco_frame.grid_remove()   # oculto até selecionar Dinheiro

        self._secao(self._troco_frame, "🪙  TROCO PARA:", row=0)

        troco_chips = ctk.CTkFrame(self._troco_frame, fg_color="transparent")
        troco_chips.grid(row=1, column=0, sticky="ew", pady=4)

        self._troco_chip_btns: list[ctk.CTkButton] = []

        for val in TROCOS_RAPIDOS:
            txt = f"R$ {int(val)}"
            btn = ctk.CTkButton(
                troco_chips, text=txt,
                height=38, width=82,
                font=ctk.CTkFont(size=13, weight="bold"),
                corner_radius=8,
                fg_color="#333", hover_color="#444",
                command=lambda v=val: self._selecionar_troco(v)
            )
            btn.pack(side="left", padx=3)
            self._troco_chip_btns.append(btn)

        sem_troco_btn = ctk.CTkButton(
            troco_chips, text="Sem Troco",
            height=38, width=90,
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8,
            fg_color="#333", hover_color="#444",
            command=lambda: self._selecionar_troco(0.0)
        )
        sem_troco_btn.pack(side="left", padx=3)
        self._troco_chip_btns.append(sem_troco_btn)

        # Campo livre de troco
        troco_entry_row = ctk.CTkFrame(self._troco_frame, fg_color="transparent")
        troco_entry_row.grid(row=2, column=0, sticky="ew", pady=(4, 0))

        ctk.CTkLabel(
            troco_entry_row, text="R$",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left", padx=(0, 6))

        self._troco_entry = ctk.CTkEntry(
            troco_entry_row, textvariable=self._troco_para,
            width=120, height=34,
            font=ctk.CTkFont(size=14),
            justify="right",
            placeholder_text="0,00"
        )
        self._troco_entry.pack(side="left")
        self._troco_para.trace_add("write", self._atualizar_troco_calc)

        # Resultado do troco
        self._troco_result_lbl = ctk.CTkLabel(
            self._troco_frame, text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_PRIMARIA
        )
        self._troco_result_lbl.grid(row=3, column=0, sticky="w", padx=4, pady=4)

        # ── Coluna direita: resumo + botão ──
        right = ctk.CTkFrame(body, fg_color=COR_CINZA_BARRA, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=2)
        right.columnconfigure(0, weight=1)

        self._secao(right, "📋  RESUMO DO PEDIDO", row=0)

        resumo_frame = ctk.CTkFrame(right, fg_color="#1E1E1E", corner_radius=10)
        resumo_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        resumo_frame.columnconfigure(0, weight=1)

        # Itens resumidos
        self._itens_frame = ctk.CTkScrollableFrame(
            resumo_frame, height=135, fg_color="transparent"
        )
        self._itens_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)

        ctk.CTkFrame(resumo_frame, height=1, fg_color="#444").grid(
            row=1, column=0, sticky="ew", padx=8, pady=3)

        self._sub_lbl = ctk.CTkLabel(
            resumo_frame, text="Subtotal:        R$ 0,00",
            font=ctk.CTkFont(size=12), anchor="w"
        )
        self._sub_lbl.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 1))

        self._taxa_lbl = ctk.CTkLabel(
            resumo_frame, text="Taxa de entrega:  R$ 0,00",
            font=ctk.CTkFont(size=12), anchor="w"
        )
        self._taxa_lbl.grid(row=3, column=0, sticky="ew", padx=12, pady=1)

        ctk.CTkFrame(resumo_frame, height=1, fg_color="#555").grid(
            row=4, column=0, sticky="ew", padx=8, pady=3)

        self._total_lbl = ctk.CTkLabel(
            resumo_frame, text="TOTAL:           R$ 0,00",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COR_PRIMARIA, anchor="w"
        )
        self._total_lbl.grid(row=5, column=0, sticky="ew", padx=12, pady=(1, 8))

        # ── Botões de ação ──
        btn_voltar = ctk.CTkButton(
            right, text="◀  Voltar",
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#444", hover_color="#555",
            corner_radius=10,
            command=self._on_back
        )
        btn_voltar.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 4))
        habilitar_feedback_clique(btn_voltar, cor_flash="#666", debounce_ms=200)

        self._btn_imprimir = ctk.CTkButton(
            right,
            text="✅  CONFIRMAR E IMPRIMIR PEDIDO",
            height=50,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COR_VERDE, hover_color=COR_VERDE_HVR,
            corner_radius=12,
            state="disabled",
            command=self._confirmar_e_imprimir
        )
        self._btn_imprimir.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))
        habilitar_feedback_clique(self._btn_imprimir, cor_flash=COR_VERDE_HVR, debounce_ms=400)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _secao(self, parent, titulo, row):
        ctk.CTkLabel(
            parent, text=titulo,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_TEXTO_SUAVE
        ).grid(row=row, column=0, sticky="w", padx=14, pady=(14, 4))

    def _selecionar_forma(self, nome: str):
        self._forma_sel.set(nome)
        for n, btn in self._pgto_btns.items():
            btn.configure(
                fg_color=COR_PRIMARIA if n == nome else "#333333",
                hover_color=COR_PRIMARIA_HVR if n == nome else "#444444"
            )

        if nome == "Dinheiro":
            self._troco_frame.grid()
            self._pix_frame.grid_remove()
            self._pix_status_var.set("")
        elif nome == "PIX":
            self._troco_frame.grid_remove()
            self._troco_para.set("")
            self._pix_frame.grid()
            self._atualizar_pix_btns()
        else:
            self._troco_frame.grid_remove()
            self._troco_para.set("")
            self._pix_frame.grid_remove()
            self._pix_status_var.set("")

        self._validar_botao()

    def _toggle_pix_status(self, status: str):
        if self._pix_status_var.get() == status:
            self._pix_status_var.set("")  # desmarcar
        else:
            self._pix_status_var.set(status)
        self._atualizar_pix_btns()

    def _limpar_pix_status(self):
        self._pix_status_var.set("")
        self._atualizar_pix_btns()

    def _atualizar_pix_btns(self):
        cur = self._pix_status_var.get()
        for s, btn in self._pix_btns.items():
            if s == cur:
                cor = COR_VERDE if s == "Pago" else COR_VERMELHO
                hvr = COR_VERDE_HVR if s == "Pago" else COR_VERMELHO_HVR
                btn.configure(fg_color=cor, hover_color=hvr)
            else:
                btn.configure(fg_color="#333", hover_color="#444")

    def _selecionar_troco(self, valor: float):
        if valor == 0:
            self._troco_para.set("0")
        else:
            self._troco_para.set(str(int(valor)))
        for btn in self._troco_chip_btns:
            txt = btn.cget("text")
            is_match = (
                (txt == "Sem Troco" and valor == 0.0) or
                (txt != "Sem Troco" and abs(float(txt.replace("R$ ", "")) - valor) < 0.01)
            )
            btn.configure(fg_color=COR_PRIMARIA if is_match else "#333")

    def _atualizar_troco_calc(self, *_):
        total = self._state.get("total", 0)
        try:
            vp = float(self._troco_para.get().replace(",", "."))
        except ValueError:
            vp = 0
        troco = vp - total
        if self._forma_sel.get() == "Dinheiro" and vp > 0:
            if troco >= 0:
                self._troco_result_lbl.configure(
                    text=f"Troco: R$ {troco:.2f}".replace(".", ","),
                    text_color=COR_VERDE
                )
            else:
                self._troco_result_lbl.configure(
                    text=f"⚠  Valor insuficiente! Falta R$ {abs(troco):.2f}".replace(".", ","),
                    text_color=COR_VERMELHO
                )
        else:
            self._troco_result_lbl.configure(text="")
        self._validar_botao()

    def _validar_botao(self):
        forma = self._forma_sel.get()
        ok = bool(forma)
        if forma == "Dinheiro":
            total = self._state.get("total", 0)
            try:
                vp = float(self._troco_para.get().replace(",", "."))
                ok = ok and (vp >= total or vp == 0)
            except ValueError:
                ok = False
        self._btn_imprimir.configure(state="normal" if ok else "disabled")

    def _atualizar_resumo(self):
        sub   = self._state.get("subtotal", 0)
        taxa  = self._state.get("taxa_entrega", 0)
        total = self._state.get("total", 0)

        for w in self._itens_frame.winfo_children():
            w.destroy()

        for item in self._state.get("carrinho", []):
            txt = f"{item['quantidade']}x  {item['nome']}"
            val = f"R$ {item['quantidade'] * item['preco_unit']:.2f}".replace(".", ",")
            row_f = ctk.CTkFrame(self._itens_frame, fg_color="transparent")
            row_f.pack(fill="x", pady=1)
            ctk.CTkLabel(row_f, text=txt, font=ctk.CTkFont(size=12), anchor="w").pack(side="left")
            ctk.CTkLabel(row_f, text=val, font=ctk.CTkFont(size=12), anchor="e").pack(side="right")
            if item.get("observacao"):
                ctk.CTkLabel(
                    self._itens_frame,
                    text=f"  ↳ {item['observacao']}",
                    font=ctk.CTkFont(size=11),
                    text_color=COR_TEXTO_SUAVE, anchor="w"
                ).pack(fill="x")

        self._sub_lbl.configure(text=f"Subtotal:         R$ {sub:.2f}".replace(".", ","))
        self._taxa_lbl.configure(text=f"Taxa de entrega:   R$ {taxa:.2f}".replace(".", ","))
        self._total_lbl.configure(text=f"TOTAL:             R$ {total:.2f}".replace(".", ","))

    # ── Confirmar e Imprimir ──────────────────────────────────────────────────

    def _confirmar_e_imprimir(self):
        forma = self._forma_sel.get()
        total = self._state.get("total", 0)

        try:
            vp = float(self._troco_para.get().replace(",", "."))
        except ValueError:
            vp = 0

        troco = max(0, vp - total) if forma == "Dinheiro" else 0

        # Tratar status do PIX
        pix_status = self._pix_status_var.get().strip() if forma == "PIX" else ""
        if forma == "PIX":
            if pix_status:
                forma_gravada = f"PIX ({pix_status.upper()})"
            else:
                forma_gravada = "PIX"
        else:
            forma_gravada = forma

        self._state["forma_pgto"] = forma_gravada
        self._state["pix_status"] = pix_status
        self._state["valor_pago"] = vp
        self._state["troco"]      = troco

        # 1. Salvar no banco SQLite
        carrinho_atual = list(self._state.get("carrinho", []))
        pedido_id = salvar_pedido(self._state, carrinho_atual)
        numero    = pedido_id

        # 2. Gerar bytes ESC/POS
        ticket_bytes = formatar_ticket(self._state, carrinho_atual, numero)

        self._btn_imprimir.configure(state="disabled", text="⏳  Imprimindo...")

        def on_success():
            self.after(0, self._pos_impressao_sucesso)

        def on_error(msg: str):
            self.after(0, lambda: self._pos_impressao_erro(msg, ticket_bytes))

        imprimir_ticket(ticket_bytes, on_success=on_success, on_error=on_error)

    def _pos_impressao_sucesso(self):
        self._btn_imprimir.configure(state="normal", text="✅  CONFIRMAR E IMPRIMIR PEDIDO")
        self._mostrar_sucesso_e_redirecionar()

    def _pos_impressao_erro(self, msg: str, ticket_bytes: bytes):
        self._btn_imprimir.configure(state="normal", text="✅  CONFIRMAR E IMPRIMIR PEDIDO")

        def retry():
            self._btn_imprimir.configure(state="disabled", text="⏳  Imprimindo...")
            imprimir_ticket(
                ticket_bytes,
                on_success=lambda: self.after(0, self._pos_impressao_sucesso),
                on_error=lambda m: self.after(0, lambda: self._pos_impressao_erro(m, ticket_bytes))
            )

        show_printer_error_popup(self, msg, retry_callback=retry)

    def _mostrar_sucesso_e_redirecionar(self):
        """Notifica sucesso e redireciona automaticamente limpando o pedido."""
        win = ctk.CTkToplevel(self)
        win.title("Pedido Concluído")
        win.geometry("400x230")
        win.grab_set()
        win.resizable(False, False)

        win.update_idletasks()
        px = self.winfo_rootx() + self.winfo_width() // 2 - 200
        py = self.winfo_rooty() + self.winfo_height() // 2 - 115
        win.geometry(f"+{max(0, px)}+{max(0, py)}")

        ctk.CTkLabel(win, text="✅", font=ctk.CTkFont(size=56)).pack(pady=(16, 2))
        ctk.CTkLabel(win, text="Pedido impresso com sucesso!", font=ctk.CTkFont(size=17, weight="bold")).pack()
        ctk.CTkLabel(win, text="Retornando ao cardápio...", font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE).pack(pady=(2, 10))

        def concluir():
            try:
                win.destroy()
            except Exception:
                pass
            self._on_novo()

        ctk.CTkButton(
            win, text="OK (Voltar ao Cardápio)",
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_PRIMARIA, hover_color=COR_PRIMARIA_HVR,
            corner_radius=8,
            command=concluir
        ).pack(fill="x", padx=40, pady=(4, 16))

        win.after(1200, concluir)

    def on_show(self):
        """Chamado quando a tela fica visível."""
        self._atualizar_resumo()
        self._forma_sel.set("")
        self._troco_para.set("")
        self._troco_result_lbl.configure(text="")
        self._pix_status_var.set("")
        self._pix_frame.grid_remove()
        self._troco_frame.grid_remove()
        for btn in self._pgto_btns.values():
            btn.configure(fg_color="#333333")
        for btn in self._pix_btns.values():
            btn.configure(fg_color="#333333")
        self._btn_imprimir.configure(state="disabled")
