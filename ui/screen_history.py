# ui/screen_history.py - Histórico de Pedidos e Reimpressão
# =============================================================================

import customtkinter as ctk
from database.db import listar_pedidos, get_pedido_com_itens, get_config, excluir_pedido
from printer.ticket_formatter import formatar_ticket
from printer.escpos_printer import imprimir_ticket, show_printer_error_popup
from config import (
    COR_PRIMARIA, COR_PRIMARIA_HVR, COR_VERDE, COR_VERDE_HVR,
    COR_VERMELHO, COR_VERMELHO_HVR,
    COR_CINZA_BARRA, COR_TEXTO_SUAVE, PRINTER_IP_DEFAULT
)


def _formatar_data_hora(criado_em: str) -> str:
    """Converte 'YYYY-MM-DD HH:MM:SS' para 'DD/MM HH:MM'."""
    s = str(criado_em or "").strip()
    if len(s) >= 16 and "-" in s[:5]:
        try:
            partes = s.split(" ")
            data_parts = partes[0].split("-")
            dia = data_parts[2]
            mes = data_parts[1]
            hora_min = partes[1][:5]
            return f"{dia}/{mes} {hora_min}"
        except Exception:
            return s[:16]
    return s[:16] if s else "—"


class ScreenHistory(ctk.CTkToplevel):
    """
    Janela modal para consulta de pedidos anteriores e reimpressão térmica.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("📋  Histórico de Pedidos Realizados")

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        # Adaptado para 1366x768 (altura máxima ~570px com margem para a barra de tarefas)
        mw = min(1020, sw - 30)
        mh = min(570, sh - 90)
        self.geometry(f"{mw}x{mh}")
        self.minsize(840, 480)
        self.grab_set()
        self.resizable(True, True)

        ctk.set_appearance_mode("Dark")

        # Centralizar na tela
        px = max(10, (sw - mw) // 2)
        py = max(10, (sh - mh) // 2)
        self.geometry(f"+{px}+{py}")

        self._pedido_selecionado = None
        self._itens_selecionados = []
        self._botoes_pedidos: dict[int, ctk.CTkButton] = {}

        self._build_ui()
        self._carregar_pedidos()

    def _build_ui(self):
        # Topbar
        top = ctk.CTkFrame(self, height=48, fg_color="#1E1E1E", corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkLabel(
            top, text="📋  HISTÓRICO DE PEDIDOS REALIZADOS",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COR_PRIMARIA
        ).pack(side="left", padx=16)

        ctk.CTkButton(
            top, text="🔄  Atualizar Lista", width=140, height=34,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#333", hover_color="#444",
            corner_radius=8,
            command=self._carregar_pedidos
        ).pack(side="right", padx=16)

        # Corpo dividido em Lista (esquerda) e Detalhes/Extrato (direita)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=12)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        # ── Coluna Esquerda: Lista de Pedidos ──
        left = ctk.CTkFrame(body, fg_color=COR_CINZA_BARRA, corner_radius=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        header = ctk.CTkFrame(left, fg_color="#1E1E1E", height=38, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="PEDIDO   │   DATA / HORA   │   CLIENTE   │   VALOR TOTAL",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_TEXTO_SUAVE
        ).pack(side="left", padx=14, pady=8)

        self._pedidos_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._pedidos_scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self._pedidos_scroll.columnconfigure(0, weight=1)

        # ── Coluna Direita: Detalhes e Reimpressão ──
        right = ctk.CTkFrame(body, fg_color=COR_CINZA_BARRA, corner_radius=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            right, text="EXTRATO DO PEDIDO SELECIONADO",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_TEXTO_SUAVE
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))

        self._detalhe_text = ctk.CTkTextbox(
            right, font=ctk.CTkFont(family="Consolas", size=12),
            wrap="none", corner_radius=8, fg_color="#181818"
        )
        self._detalhe_text.grid(row=1, column=0, sticky="nsew", padx=14, pady=4)
        self._detalhe_text.configure(state="disabled")

        # Barra inferior com botões de ação (Excluir e Reimpressão)
        bot_right = ctk.CTkFrame(right, fg_color="transparent")
        bot_right.grid(row=2, column=0, sticky="ew", padx=14, pady=10)
        bot_right.columnconfigure(0, weight=1)
        bot_right.columnconfigure(1, weight=2)

        self._btn_excluir = ctk.CTkButton(
            bot_right, text="🗑️  Excluir Pedido",
            height=46, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_VERMELHO, hover_color=COR_VERMELHO_HVR,
            corner_radius=10,
            state="disabled",
            command=self._confirmar_exclusao
        )
        self._btn_excluir.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self._btn_reimprimir = ctk.CTkButton(
            bot_right, text="🖨  REIMPRIMIR (ELGIN i8)",
            height=46, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_VERDE, hover_color=COR_VERDE_HVR,
            corner_radius=10,
            state="disabled",
            command=self._reimprimir_pedido
        )
        self._btn_reimprimir.grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def _carregar_pedidos(self):
        for w in self._pedidos_scroll.winfo_children():
            w.destroy()

        self._botoes_pedidos.clear()
        pedidos = listar_pedidos(limit=100)

        if not pedidos:
            ctk.CTkLabel(
                self._pedidos_scroll, text="Nenhum pedido registrado ainda.",
                font=ctk.CTkFont(size=13), text_color=COR_TEXTO_SUAVE
            ).pack(pady=30)
            self._detalhe_text.configure(state="normal")
            self._detalhe_text.delete("1.0", "end")
            self._detalhe_text.configure(state="disabled")
            self._btn_excluir.configure(state="disabled")
            self._btn_reimprimir.configure(state="disabled")
            return

        for i, ped in enumerate(pedidos):
            ped_id = ped["id"]
            num_val = ped.get("numero") or ped_id
            num_str = f"#{num_val:03d}"
            data_str = _formatar_data_hora(ped.get("criado_em", ""))

            nome_cli = (ped.get("cliente_nome") or "").strip()
            if not nome_cli:
                nome_cli = "Balcão / Tele"
            elif len(nome_cli) > 16:
                nome_cli = nome_cli[:14] + ".."

            total_val = ped.get("total", 0)
            total_str = f"R$ {total_val:.2f}".replace(".", ",")

            # Formato alinhado e padronizado: #002 | 18/10 15:37 | João | R$ 36,00
            btn_label = f"{num_str:<5} │ {data_str:<11} │ {nome_cli:<16} │ {total_str:>9}"

            btn = ctk.CTkButton(
                self._pedidos_scroll,
                text=btn_label,
                font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
                anchor="w",
                fg_color="#272727",
                hover_color="#3A3A3A",
                corner_radius=6,
                height=42,
                command=lambda pid=ped_id: self._selecionar_pedido(pid)
            )
            btn.pack(fill="x", pady=2, padx=2)
            self._botoes_pedidos[ped_id] = btn

        # Selecionar o primeiro da lista automaticamente
        if pedidos:
            self._selecionar_pedido(pedidos[0]["id"])

    def _selecionar_pedido(self, pedido_id: int):
        pedido, itens = get_pedido_com_itens(pedido_id)
        if not pedido:
            return

        self._pedido_selecionado = pedido
        self._itens_selecionados = itens
        self._btn_excluir.configure(state="normal")
        self._btn_reimprimir.configure(state="normal")

        # Destacar botão selecionado
        for pid, b in self._botoes_pedidos.items():
            if pid == pedido_id:
                b.configure(fg_color=COR_PRIMARIA, hover_color=COR_PRIMARIA_HVR)
            else:
                b.configure(fg_color="#272727", hover_color="#3A3A3A")

        # Montar texto legível no extrato
        num = pedido.get("numero") or pedido.get("id")
        linhas = []
        linhas.append("=" * 42)
        linhas.append(f"     POINT LANCHES - EXTRATO #{num:03d}")
        linhas.append(f"     Data: {pedido.get('criado_em', '')}")
        linhas.append("=" * 42)
        linhas.append(f"CLIENTE: {pedido.get('cliente_nome') or 'NÃO INFORMADO'}")
        linhas.append(f"FONE:    {pedido.get('cliente_fone') or '—'}")

        rua = pedido.get("endereco_rua", "")
        num_end = pedido.get("endereco_num", "")
        comp = pedido.get("endereco_comp", "")
        end_completo = rua
        if num_end:
            end_completo += f", {num_end}"
        if comp:
            end_completo += f" - {comp}"
        if end_completo.strip():
            linhas.append(f"END:     {end_completo}")
        if pedido.get("endereco_bairro"):
            linhas.append(f"BAIRRO:  {pedido.get('endereco_bairro')} - Dois Irmãos")
        if pedido.get("endereco_ref"):
            linhas.append(f"REF:     {pedido.get('endereco_ref')}")
        linhas.append("-" * 42)
        linhas.append("QTD  ITEM                              VALOR")
        linhas.append("-" * 42)

        for item in itens:
            q = item.get("quantidade", 1)
            p = item.get("preco_unit", 0)
            tot_i = q * p
            linhas.append(f"{q}x  {item.get('nome', '')[:28]:<28} R$ {tot_i:>6.2f}")
            if item.get("observacao"):
                linhas.append(f"    ↳ Obs: {item['observacao']}")

        linhas.append("-" * 42)
        linhas.append(f"Subtotal:                  R$ {pedido.get('subtotal', 0):>8.2f}")
        linhas.append(f"Taxa Entrega:              R$ {pedido.get('taxa_entrega', 0):>8.2f}")
        linhas.append(f"TOTAL GERAL:               R$ {pedido.get('total', 0):>8.2f}")
        linhas.append("-" * 42)
        linhas.append(f"PAGAMENTO: {pedido.get('forma_pgto', '—')}")
        if pedido.get("valor_pago", 0) > 0:
            linhas.append(f"Valor Pago:                R$ {pedido.get('valor_pago', 0):>8.2f}")
        if pedido.get("troco", 0) > 0:
            linhas.append(f"TROCO:                     R$ {pedido.get('troco', 0):>8.2f}")
        linhas.append("=" * 42)

        texto_final = "\n".join(linhas)

        self._detalhe_text.configure(state="normal")
        self._detalhe_text.delete("1.0", "end")
        self._detalhe_text.insert("1.0", texto_final)
        self._detalhe_text.configure(state="disabled")

    def _confirmar_exclusao(self):
        if not self._pedido_selecionado:
            return

        p = self._pedido_selecionado
        num = p.get("numero") or p.get("id")
        nome_cli = p.get("cliente_nome") or "Balcão / Tele"
        total = p.get("total", 0.0)

        # Diálogo modal de confirmação amigável
        modal = ctk.CTkToplevel(self)
        modal.title("Confirmar Exclusão de Pedido")
        modal.geometry("420x220")
        modal.grab_set()
        modal.resizable(False, False)

        modal.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - 420) // 2
        py = self.winfo_rooty() + (self.winfo_height() - 220) // 2
        modal.geometry(f"+{max(0, px)}+{max(0, py)}")

        ctk.CTkLabel(
            modal, text="⚠️", font=ctk.CTkFont(size=40)
        ).pack(pady=(16, 2))

        ctk.CTkLabel(
            modal,
            text=f"Tem certeza que deseja excluir o Pedido #{num:03d}?",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(2, 4))

        ctk.CTkLabel(
            modal,
            text=f"Cliente: {nome_cli}  •  Total: R$ {total:.2f}\nEsta ação não poderá ser desfeita.",
            font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE, justify="center"
        ).pack(pady=(0, 16))

        btn_box = ctk.CTkFrame(modal, fg_color="transparent")
        btn_box.pack(fill="x", padx=20, pady=(0, 14))
        btn_box.columnconfigure(0, weight=1)
        btn_box.columnconfigure(1, weight=1)

        def cancelar():
            try:
                modal.destroy()
            except Exception:
                pass

        def executar():
            try:
                modal.destroy()
            except Exception:
                pass
            excluir_pedido(p["id"])
            self._pedido_selecionado = None
            self._itens_selecionados = []
            self._detalhe_text.configure(state="normal")
            self._detalhe_text.delete("1.0", "end")
            self._detalhe_text.configure(state="disabled")
            self._btn_excluir.configure(state="disabled")
            self._btn_reimprimir.configure(state="disabled")
            self._carregar_pedidos()

        ctk.CTkButton(
            btn_box, text="Cancelar", height=38,
            font=ctk.CTkFont(size=13),
            fg_color="#3A3A3A", hover_color="#4A4A4A",
            corner_radius=8, command=cancelar
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(
            btn_box, text="🗑️  Sim, Excluir", height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COR_VERMELHO, hover_color=COR_VERMELHO_HVR,
            corner_radius=8, command=executar
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def _reimprimir_pedido(self):
        if not self._pedido_selecionado:
            return

        p = self._pedido_selecionado
        # Normalizar chaves para o formatador
        pedido_fmt = {
            "cliente_nome": p.get("cliente_nome", ""),
            "cliente_fone": p.get("cliente_fone", ""),
            "rua":          p.get("endereco_rua", ""),
            "numero":       p.get("endereco_num", ""),
            "complemento":  p.get("endereco_comp", ""),
            "bairro":       p.get("endereco_bairro", ""),
            "referencia":   p.get("endereco_ref", ""),
            "subtotal":     p.get("subtotal", 0),
            "taxa_entrega": p.get("taxa_entrega", 0),
            "total":        p.get("total", 0),
            "forma_pgto":   p.get("forma_pgto", ""),
            "valor_pago":   p.get("valor_pago", 0),
            "troco":        p.get("troco", 0),
        }
        numero = p.get("numero") or p.get("id")

        ticket_bytes = formatar_ticket(pedido_fmt, self._itens_selecionados, numero)
        ip = get_config("printer_ip", PRINTER_IP_DEFAULT)

        self._btn_reimprimir.configure(state="disabled", text="⏳  Reimprimindo...")

        def on_success():
            self.after(0, lambda: self._btn_reimprimir.configure(
                state="normal", text="✔  Reimpresso com Sucesso!"
            ))
            self.after(2000, lambda: self._btn_reimprimir.configure(
                text="🖨  REIMPRIMIR PEDIDO (ELGIN i8)"
            ))

        def on_error(msg):
            self.after(0, lambda: self._btn_reimprimir.configure(
                state="normal", text="🖨  REIMPRIMIR PEDIDO (ELGIN i8)"
            ))
            show_printer_error_popup(self, msg, retry_callback=self._reimprimir_pedido)

        imprimir_ticket(ticket_bytes, on_success=on_success, on_error=on_error)
