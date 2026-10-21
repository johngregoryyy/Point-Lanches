# ui/screen_logs.py - Tela de Visualização e Gestão de Logs de Erros
# =============================================================================

from datetime import datetime
import customtkinter as ctk

from database.db import listar_logs_erro, limpar_logs_erro
from config import (
    COR_PRIMARIA, COR_PRIMARIA_HVR, COR_VERDE, COR_VERDE_HVR,
    COR_VERMELHO, COR_VERMELHO_HVR, COR_CINZA_BARRA,
    COR_TEXTO_SUAVE, COR_AZUL_POINT, COR_TEXTO
)


class ScreenLogs(ctk.CTkToplevel):
    """
    Janela Toplevel para visualização, diagnóstico e auditoria de erros do sistema.
    Exibe os logs ordenados cronologicamente e agrupados por data e hora,
    com detalhes técnicos de traceback e status de sincronização no Supabase.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("📜  Logs e Registro de Erros do Sistema - Point Lanches")

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        # Otimizado para resoluções 1366x768 e Full HD
        mw = min(1040, sw - 30)
        mh = min(580, sh - 80)
        self.geometry(f"{mw}x{mh}")
        self.minsize(860, 480)
        self.grab_set()
        self.resizable(True, True)

        ctk.set_appearance_mode("Dark")

        # Centralizar na tela
        px = max(10, (sw - mw) // 2)
        py = max(10, (sh - mh) // 2)
        self.geometry(f"+{px}+{py}")

        self._log_selecionado = None
        self._cards_logs = {}

        self._build_ui()
        self._carregar_logs()

    def _build_ui(self):
        # ── 1. Topbar com Título, Filtro e Ações ──
        top = ctk.CTkFrame(self, height=52, fg_color="#181818", corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkLabel(
            top, text="📜  LOGS DE ERRO DO SISTEMA",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COR_PRIMARIA
        ).pack(side="left", padx=16)

        self._lbl_total_badge = ctk.CTkLabel(
            top, text="(0 registros)",
            font=ctk.CTkFont(size=12),
            text_color=COR_TEXTO_SUAVE
        )
        self._lbl_total_badge.pack(side="left", padx=(0, 16))

        # Ações à direita
        ctk.CTkButton(
            top, text="Fechar", width=80, height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#3A3A3A", hover_color="#4A4A4A",
            corner_radius=6, command=self.destroy
        ).pack(side="right", padx=(6, 16))

        ctk.CTkButton(
            top, text="🗑️ Limpar Logs", width=120, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COR_VERMELHO, hover_color=COR_VERMELHO_HVR,
            corner_radius=6, command=self._confirmar_limpar_logs
        ).pack(side="right", padx=6)

        ctk.CTkButton(
            top, text="🔄 Atualizar", width=110, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COR_PRIMARIA, hover_color=COR_PRIMARIA_HVR,
            corner_radius=6, command=self._on_atualizar_click
        ).pack(side="right", padx=6)

        # Filtro de tipo
        self._filtro_tipo_var = ctk.StringVar(value="TODOS")
        opt_filtro = ctk.CTkOptionMenu(
            top, variable=self._filtro_tipo_var,
            values=["TODOS", "ERRO", "EXCEÇÃO", "IMPRESSORA", "SUPABASE", "SISTEMA", "AVISO"],
            width=130, height=32, font=ctk.CTkFont(size=12),
            fg_color="#2D3748", button_color="#4A5568",
            command=lambda _: self._carregar_logs()
        )
        opt_filtro.pack(side="right", padx=6)

        # ── 2. Corpo Dividido: Lista Agrupada (Esq) e Detalhes Técnicos (Dir) ──
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=10)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        # Coluna Esquerda: Lista de logs com scroll
        left_frame = ctk.CTkFrame(body, fg_color=COR_CINZA_BARRA, corner_radius=10)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_frame.rowconfigure(1, weight=1)
        left_frame.columnconfigure(0, weight=1)

        lh = ctk.CTkFrame(left_frame, fg_color="#1E1E1E", height=34, corner_radius=0)
        lh.grid(row=0, column=0, sticky="ew")
        lh.pack_propagate(False)
        ctk.CTkLabel(
            lh, text="REGISTROS DIVIDIDOS POR DATA E HORA (MAIS RECENTES NO TOPO)",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=COR_TEXTO_SUAVE
        ).pack(side="left", padx=12, pady=8)

        self._scroll_logs = ctk.CTkScrollableFrame(left_frame, fg_color="transparent")
        self._scroll_logs.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self._scroll_logs.columnconfigure(0, weight=1)

        # Coluna Direita: Detalhes do Log Selecionado
        right_frame = ctk.CTkFrame(body, fg_color=COR_CINZA_BARRA, corner_radius=10)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.rowconfigure(1, weight=1)
        right_frame.columnconfigure(0, weight=1)

        rh = ctk.CTkFrame(right_frame, fg_color="#1E1E1E", height=34, corner_radius=0)
        rh.grid(row=0, column=0, sticky="ew")
        rh.pack_propagate(False)
        ctk.CTkLabel(
            rh, text="DETALHES DO ERRO SELECIONADO",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=COR_TEXTO_SUAVE
        ).pack(side="left", padx=12, pady=8)

        # Painel interno de detalhes
        detail_container = ctk.CTkFrame(right_frame, fg_color="transparent")
        detail_container.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        detail_container.rowconfigure(3, weight=1)
        detail_container.columnconfigure(0, weight=1)

        # Metadados
        self._lbl_det_meta = ctk.CTkLabel(
            detail_container, text="Selecione um log na lista ao lado para ver os detalhes.",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_TEXTO_SUAVE, justify="left", anchor="w"
        )
        self._lbl_det_meta.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self._lbl_det_msg = ctk.CTkLabel(
            detail_container, text="",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COR_TEXTO,
            wraplength=380, justify="left", anchor="w"
        )
        self._lbl_det_msg.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(
            detail_container, text="Traceback / Dados Técnicos:",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=COR_TEXTO_SUAVE, anchor="w"
        ).grid(row=2, column=0, sticky="ew", pady=(0, 2))

        self._txt_traceback = ctk.CTkTextbox(
            detail_container, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0F1218", text_color="#E2E8F0", corner_radius=6
        )
        self._txt_traceback.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
        self._txt_traceback.configure(state="disabled")

        # Barra inferior de ações do detalhe
        det_actions = ctk.CTkFrame(detail_container, fg_color="transparent", height=36)
        det_actions.grid(row=4, column=0, sticky="ew")

        self._btn_copiar = ctk.CTkButton(
            det_actions, text="📋 Copiar Detalhes do Erro",
            font=ctk.CTkFont(size=12, weight="bold"), height=32,
            fg_color="#334155", hover_color="#475569", corner_radius=6,
            command=self._copiar_detalhes, state="disabled"
        )
        self._btn_copiar.pack(side="left")

        self._lbl_copiado = ctk.CTkLabel(
            det_actions, text="", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COR_VERDE
        )
        self._lbl_copiado.pack(side="left", padx=8)

    def _on_atualizar_click(self):
        """Atualiza a lista e sincroniza logs pendentes com a nuvem."""
        self._carregar_logs()
        import threading
        def _bg_sync():
            try:
                from services.supabase_sync import sincronizar_logs_pendentes_supabase
                sincronizar_logs_pendentes_supabase(timeout=5)
                self.after(0, self._carregar_logs)
            except Exception:
                pass
        threading.Thread(target=_bg_sync, daemon=True).start()

    def _carregar_logs(self):
        """Carrega e renderiza os logs agrupados por data e hora."""
        for w in self._scroll_logs.winfo_children():
            w.destroy()
        self._cards_logs.clear()

        tipo_filtro = self._filtro_tipo_var.get()
        logs = listar_logs_erro(limite=300, tipo_filtro=tipo_filtro)
        self._lbl_total_badge.configure(text=f"({len(logs)} registros)")

        if not logs:
            ctk.CTkLabel(
                self._scroll_logs,
                text="✅ Nenhum erro registrado no sistema!\nTudo funcionando perfeitamente.",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COR_VERDE, justify="center"
            ).pack(pady=40)
            self._limpar_painel_detalhe()
            return

        hoje_str = datetime.now().strftime("%Y-%m-%d")
        logs_por_data = {}
        for l in logs:
            data_str = (l.get("data_hora") or "")[:10] or "Data Desconhecida"
            logs_por_data.setdefault(data_str, []).append(l)

        primeiro_log = None

        for data_str, itens in logs_por_data.items():
            # Rótulo amigável da data
            if data_str == hoje_str:
                titulo_data = f"📅 Hoje ({data_str[8:10]}/{data_str[5:7]}/{data_str[:4]}) — {len(itens)} ocorrência(s)"
                cor_header = COR_AZUL_POINT
            else:
                try:
                    dt = datetime.strptime(data_str, "%Y-%m-%d")
                    data_fmt = dt.strftime("%d/%m/%Y")
                except Exception:
                    data_fmt = data_str
                titulo_data = f"📅 {data_fmt} — {len(itens)} ocorrência(s)"
                cor_header = COR_TEXTO_SUAVE

            # Header da Data
            data_header = ctk.CTkFrame(self._scroll_logs, fg_color="#1A202C", corner_radius=6, height=28)
            data_header.pack(fill="x", pady=(8, 4), padx=2)
            data_header.pack_propagate(False)
            ctk.CTkLabel(
                data_header, text=titulo_data,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=cor_header
            ).pack(side="left", padx=8, pady=4)

            # Itens daquela data ordenados pela hora
            for item in itens:
                if primeiro_log is None:
                    primeiro_log = item
                self._renderizar_card_log(item)

        # Selecionar automaticamente o primeiro item se nenhum selecionado
        if primeiro_log and (not self._log_selecionado or self._log_selecionado["id"] not in [l["id"] for l in logs]):
            self._selecionar_log(primeiro_log)

    def _renderizar_card_log(self, item: dict):
        """Renderiza um card de log na coluna esquerda."""
        log_id = item["id"]
        tipo = (item.get("tipo") or "ERRO").upper()
        modulo = item.get("modulo") or "sistema"
        hora = (item.get("data_hora") or "")[11:19] or "--:--:--"
        msg = item.get("mensagem") or "(Sem mensagem)"
        supa_id = item.get("supabase_id")

        # Cores por tipo de erro
        cores_tipo = {
            "ERRO":       {"bg": "#7F1D1D", "txt": "#FCA5A5"},
            "EXCEÇÃO":    {"bg": "#991B1B", "txt": "#FECACA"},
            "IMPRESSORA": {"bg": "#581C87", "txt": "#E9D5FF"},
            "SUPABASE":   {"bg": "#1E3A8A", "txt": "#BFDBFE"},
            "SISTEMA":    {"bg": "#374151", "txt": "#E5E7EB"},
            "AVISO":      {"bg": "#78350F", "txt": "#FDE68A"},
        }
        conf = cores_tipo.get(tipo, {"bg": "#374151", "txt": "#E5E7EB"})

        card = ctk.CTkFrame(self._scroll_logs, fg_color="#1E2430", corner_radius=8, cursor="hand2")
        card.pack(fill="x", pady=2, padx=2)
        self._cards_logs[log_id] = card

        # Topo do card: Hora, Tipo, Módulo e Status de Sync
        card_top = ctk.CTkFrame(card, fg_color="transparent")
        card_top.pack(fill="x", padx=8, pady=(6, 2))

        ctk.CTkLabel(
            card_top, text=f"🕒 {hora}",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#E2E8F0"
        ).pack(side="left")

        # Badge do Tipo
        tipo_badge = ctk.CTkFrame(card_top, fg_color=conf["bg"], corner_radius=4)
        tipo_badge.pack(side="left", padx=6)
        ctk.CTkLabel(
            tipo_badge, text=f" {tipo} ",
            font=ctk.CTkFont(size=10, weight="bold"), text_color=conf["txt"]
        ).pack(padx=3, pady=1)

        # Módulo
        ctk.CTkLabel(
            card_top, text=f"[{modulo}]",
            font=ctk.CTkFont(size=11), text_color=COR_TEXTO_SUAVE
        ).pack(side="left")

        # Indicador de Sincronização Supabase
        if supa_id:
            sync_lbl = "☁️ Supabase"
            sync_cor = "#34D399"
        else:
            sync_lbl = "💾 Local"
            sync_cor = "#94A3B8"

        ctk.CTkLabel(
            card_top, text=sync_lbl,
            font=ctk.CTkFont(size=10, weight="bold"), text_color=sync_cor
        ).pack(side="right")

        # Mensagem resumida (até 120 caracteres)
        msg_preview = msg.replace("\n", " ")
        if len(msg_preview) > 90:
            msg_preview = msg_preview[:87] + "..."

        lbl_msg = ctk.CTkLabel(
            card, text=msg_preview,
            font=ctk.CTkFont(size=11), text_color="#CBD5E1",
            anchor="w", justify="left"
        )
        lbl_msg.pack(fill="x", padx=8, pady=(0, 6))

        # Evento de clique para selecionar
        for widget in [card, card_top, lbl_msg]:
            widget.bind("<Button-1>", lambda _, it=item: self._selecionar_log(it))

    def _selecionar_log(self, item: dict):
        """Seleciona o log e exibe no painel de detalhes."""
        self._log_selecionado = item
        log_id = item["id"]

        # Realce visual no card selecionado
        for cid, cframe in self._cards_logs.items():
            if cid == log_id:
                cframe.configure(fg_color="#1E3A5F")
            else:
                cframe.configure(fg_color="#1E2430")

        # Preencher detalhes
        tipo = (item.get("tipo") or "ERRO").upper()
        modulo = item.get("modulo") or "sistema"
        data_hora = item.get("data_hora") or "--"
        versao = item.get("versao_app") or "1.1.6"
        supa_id = item.get("supabase_id")
        sync_txt = f"☁️ Sincronizado (ID #{supa_id})" if supa_id else "💾 Salvo Localmente (Aguardando Sync)"
        sync_cor = "#34D399" if supa_id else "#94A3B8"

        meta_txt = f"📅 {data_hora}   │   [{tipo}] em '{modulo}'   │   v{versao}\nStatus Nuvem: {sync_txt}"
        self._lbl_det_meta.configure(text=meta_txt, text_color=sync_cor)

        self._lbl_det_msg.configure(text=item.get("mensagem") or "(Sem mensagem descritiva)")

        tb = item.get("detalhes") or "Nenhum detalhe técnico ou traceback disponível."
        self._txt_traceback.configure(state="normal")
        self._txt_traceback.delete("1.0", "end")
        self._txt_traceback.insert("1.0", tb)
        self._txt_traceback.configure(state="disabled")

        self._btn_copiar.configure(state="normal")
        self._lbl_copiado.configure(text="")

    def _limpar_painel_detalhe(self):
        """Reseta o painel de detalhes da direita."""
        self._log_selecionado = None
        self._lbl_det_meta.configure(text="Nenhum log para exibir.", text_color=COR_TEXTO_SUAVE)
        self._lbl_det_msg.configure(text="")
        self._txt_traceback.configure(state="normal")
        self._txt_traceback.delete("1.0", "end")
        self._txt_traceback.configure(state="disabled")
        self._btn_copiar.configure(state="disabled")
        self._lbl_copiado.configure(text="")

    def _copiar_detalhes(self):
        """Copia os detalhes e traceback do erro selecionado para o clipboard."""
        if not self._log_selecionado:
            return

        l = self._log_selecionado
        texto = (
            f"=== LOG DE ERRO - POINT LANCHES ===\n"
            f"Data/Hora:  {l.get('data_hora')}\n"
            f"Tipo:       {l.get('tipo')}\n"
            f"Módulo:     {l.get('modulo')}\n"
            f"Versão:     {l.get('versao_app')}\n"
            f"SupabaseID: {l.get('supabase_id') or 'NÃO SINCRONIZADO'}\n"
            f"Mensagem:   {l.get('mensagem')}\n\n"
            f"--- TRACEBACK / DETALHES ---\n"
            f"{l.get('detalhes') or 'Nenhum'}\n"
        )

        self.clipboard_clear()
        self.clipboard_append(texto)
        self.update()

        self._lbl_copiado.configure(text="✅ Detalhes copiados para a Área de Transferência!")
        self.after(3000, lambda: self._lbl_copiado.configure(text=""))

    def _confirmar_limpar_logs(self):
        """Abre modal de confirmação para limpar o banco de logs."""
        modal = ctk.CTkToplevel(self)
        modal.title("Confirmar Limpeza")
        modal.geometry("380x180")
        modal.resizable(False, False)
        modal.grab_set()

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        modal.geometry(f"+{(sw-380)//2}+{(sh-180)//2}")

        ctk.CTkLabel(
            modal, text="Deseja limpar todos os logs de erro locais?",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COR_TEXTO
        ).pack(pady=(20, 8))

        ctk.CTkLabel(
            modal, text="Esta ação removerá o histórico de logs do banco local.",
            font=ctk.CTkFont(size=12), text_color=COR_TEXTO_SUAVE
        ).pack(pady=(0, 20))

        btn_box = ctk.CTkFrame(modal, fg_color="transparent")
        btn_box.pack(fill="x", padx=20)
        btn_box.columnconfigure((0, 1), weight=1)

        def _cancelar():
            modal.destroy()

        def _executar():
            modal.destroy()
            limpar_logs_erro()
            self._carregar_logs()

        ctk.CTkButton(
            btn_box, text="Cancelar", height=36,
            fg_color="#3A3A3A", hover_color="#4A4A4A",
            command=_cancelar
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(
            btn_box, text="Sim, Limpar", height=36,
            fg_color=COR_VERMELHO, hover_color=COR_VERMELHO_HVR,
            font=ctk.CTkFont(weight="bold"),
            command=_executar
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")
