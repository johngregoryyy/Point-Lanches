import os
import sys
import customtkinter as ctk

from config import (
    APPEARANCE_MODE, COLOR_THEME,
    LARGURA_JANELA, ALTURA_JANELA, TITULO_APP,
    CHECK_UPDATES_ON_STARTUP
)
from database.db import init_db
from database.seed import run_all_seeds
from services.updater import check_updates_background
from ui.screen_cart import ScreenCart
from ui.screen_delivery import ScreenDelivery
from ui.screen_payment import ScreenPayment
from ui.screen_admin import ScreenAdmin
from ui.screen_history import ScreenHistory
from ui.screen_balanco import ScreenBalanco


# ── Configuração global do CustomTkinter ──────────────────────────────────────
ctk.set_appearance_mode(APPEARANCE_MODE)
ctk.set_default_color_theme(COLOR_THEME)


class App(ctk.CTk):
    """
    Janela raiz do Point Lanches.
    Gerencia o estado compartilhado entre telas e a alternância entre elas.
    """

    def __init__(self):
        super().__init__()
        self.title(TITULO_APP)

        # ── Ícone oficial da aplicação ──
        try:
            icon_path = os.path.join(getattr(sys, '_MEIPASS', os.path.abspath(".")), "assets", "images.ico")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(getattr(sys, '_MEIPASS', os.path.abspath(".")), "Assets", "images.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        # ── Detecção dinâmica de tela (1366x768 vs Full HD) ──
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        # Margem de segurança para barra de tarefas do Windows (~48-60px)
        largura = min(LARGURA_JANELA, sw - 16)
        altura  = min(ALTURA_JANELA, sh - 75)

        self.geometry(f"{largura}x{altura}")
        self.minsize(960, 560)
        self.resizable(True, True)

        # Centralizar na tela
        x = max(0, (sw - largura) // 2)
        y = max(0, (sh - altura) // 2)
        self.geometry(f"+{x}+{y}")

        # Em telas HD (1366x768 ou 1280x720), abre maximizado para aproveitar 100% da área útil do caixa
        if sh <= 800:
            self.after(100, lambda: self.state("zoomed"))

        # ── Estado compartilhado (fluxo do pedido) ────────────────────────────
        self._state: dict = {}
        self._reset_state()

        # ── Container principal (frame que empilha as telas) ──────────────────
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # ── Instanciar as telas ───────────────────────────────────────────────
        self._telas: dict[str, ctk.CTkFrame] = {}

        self._telas["cart"] = ScreenCart(
            container, state=self._state,
            on_next=lambda: self._mostrar("delivery"),
            on_admin=self._abrir_admin,
            on_historico=self._abrir_historico,
            on_balanco=self._abrir_balanco
        )
        self._telas["delivery"] = ScreenDelivery(
            container, state=self._state,
            on_next=lambda: self._mostrar("payment"),
            on_back=lambda: self._mostrar("cart"),
            on_admin=self._abrir_admin,
            on_historico=self._abrir_historico,
            on_balanco=self._abrir_balanco
        )
        self._telas["payment"] = ScreenPayment(
            container, state=self._state,
            on_back=lambda: self._mostrar("delivery"),
            on_admin=self._abrir_admin,
            on_historico=self._abrir_historico,
            on_balanco=self._abrir_balanco,
            on_novo_pedido=self._novo_pedido
        )

        # Empilhar todas no mesmo grid (apenas uma visível por vez)
        for tela in self._telas.values():
            tela.grid(row=0, column=0, sticky="nsew")

        # Iniciar no cardápio
        self._mostrar("cart")

        # Checagem não-bloqueante de atualização via GitHub Releases (2s após carregar a UI)
        if CHECK_UPDATES_ON_STARTUP:
            self.after(2000, lambda: check_updates_background(self))

    # ── Navegação ─────────────────────────────────────────────────────────────

    def _mostrar(self, nome: str):
        """Traz a tela indicada para frente e chama on_show()."""
        tela = self._telas.get(nome)
        if tela:
            tela.tkraise()
            if hasattr(tela, "on_show"):
                tela.on_show()

    def _abrir_admin(self, tab=None):
        """Abre a janela administrativa como Toplevel."""
        admin = ScreenAdmin(self, on_refresh=self._recarregar_dados_sistema, initial_tab=tab)
        admin.focus()

    def _abrir_balanco(self):
        """Abre a janela isolada de Balanço Geral / Relatórios Financeiros."""
        balanco = ScreenBalanco(self)
        balanco.focus()

    def _recarregar_dados_sistema(self):
        """Atualiza cardápio, produtos e taxas das telas quando configurações são importadas."""
        if "cart" in self._telas and hasattr(self._telas["cart"], "on_show"):
            self._telas["cart"].on_show()
        if "delivery" in self._telas and hasattr(self._telas["delivery"], "on_show"):
            self._telas["delivery"].on_show()

    def _abrir_historico(self):
        """Abre a janela de histórico de pedidos."""
        historico = ScreenHistory(self)
        historico.focus()

    def _novo_pedido(self):
        """Reinicia o estado e volta ao cardápio."""
        self._reset_state()
        if "delivery" in self._telas and hasattr(self._telas["delivery"], "limpar_campos"):
            self._telas["delivery"].limpar_campos()
        self._mostrar("cart")

    def _reset_state(self):
        """Limpa/inicializa o estado compartilhado para um novo pedido."""
        self._state.clear()
        self._state.update({
            "carrinho":      [],
            "subtotal":      0.0,
            "taxa_entrega":  0.0,
            "total":         0.0,
            "cliente_nome":  "",
            "cliente_fone":  "",
            "rua":           "",
            "numero":        "",
            "complemento":   "",
            "bairro":        "",
            "referencia":    "",
            "forma_pgto":    "",
            "valor_pago":    0.0,
            "troco":         0.0,
        })


# ── Ponto de entrada ──────────────────────────────────────────────────────────

def main():
    # 1. Inicializar banco de dados e migrações
    init_db()
    # 2. Popular todas as tabelas (cardápio, bebidas, adicionais, taxas)
    run_all_seeds()
    # 3. Iniciar aplicação
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
