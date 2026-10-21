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
from ui.screen_logs import ScreenLogs
from services.error_logger import setup_global_exception_handlers


# ── Configuração global do CustomTkinter ──────────────────────────────────────
ctk.set_appearance_mode(APPEARANCE_MODE)
ctk.set_default_color_theme(COLOR_THEME)


class App(ctk.CTk):
    """
    Janela raiz do Point Lanches.
    Gerencia o estado compartilhado entre telas e a alternância entre elas.
    """

    def __init__(self, start_hidden: bool = False):
        super().__init__()
        self.title(TITULO_APP)

        if start_hidden:
            self.withdraw()

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

        # ── Estado compartilhado (fluxo do pedido) ────────────────────────────
        self._state: dict = {}
        self._reset_state()
        self._telas: dict[str, ctk.CTkFrame] = {}
        self._admin_window: ScreenAdmin | None = None

        # ── Sincronização automática com Supabase ao fechar a janela ──────────
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar_aplicacao)

        # ── Interceptação global de erros do sistema (UI, threads e exceções) ──
        setup_global_exception_handlers(self)

        if not start_hidden:
            self.setup_ui()
            self.mostrar_janela_principal()

    def setup_ui(self):
        """Constrói o container principal e instancia todas as telas do sistema."""
        if self._telas:
            return

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # ── Instanciar as telas ───────────────────────────────────────────────
        self._telas["cart"] = ScreenCart(
            container, state=self._state,
            on_next=lambda: self._mostrar("delivery"),
            on_admin=self._abrir_admin,
            on_logs=self._abrir_logs,
            on_historico=self._abrir_historico,
            on_balanco=self._abrir_balanco,
            on_login=self._abrir_login,
            on_sync=self._recarregar_dados_sistema
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

        # Pré-aquece a janela administrativa em background para abertura instantânea (0ms)
        self.after(500, self._pre_aquecer_admin)

        # Checagem não-bloqueante de atualização via GitHub Releases (2s após carregar a UI)
        if CHECK_UPDATES_ON_STARTUP:
            self.after(2000, lambda: check_updates_background(self))

    def _pre_aquecer_admin(self):
        """Pré-aquece a janela administrativa em background para abertura instantânea (0ms)."""
        if getattr(self, "_admin_window", None) is None or not self._admin_window.winfo_exists():
            try:
                self._admin_window = ScreenAdmin(
                    self,
                    on_refresh=self._recarregar_dados_sistema,
                    start_hidden=True
                )
            except Exception as e:
                print(f"Aviso pre-warm admin: {e}")

    def mostrar_janela_principal(self):
        """Torna a janela visível e aplica zoom em telas HD."""
        self.deiconify()
        sh = self.winfo_screenheight()
        if sh <= 800:
            self.after(100, lambda: self.state("zoomed"))

    # ── Navegação ─────────────────────────────────────────────────────────────

    def _mostrar(self, nome: str):
        """Traz a tela indicada para frente e chama on_show()."""
        tela = self._telas.get(nome)
        if tela:
            tela.tkraise()
            if hasattr(tela, "on_show"):
                tela.on_show()

    def _abrir_admin(self, tab=None):
        """Abre a janela administrativa instantaneamente (3ms se em cache, ou com tela de carregamento imediata)."""
        if getattr(self, "_admin_window", None) is not None and self._admin_window.winfo_exists():
            self._admin_window.mostrar(tab=tab)
            return

        # Se ainda não existe, cria com start_hidden=False (exibe tela de carregamento na hora)
        self._admin_window = ScreenAdmin(
            self,
            on_refresh=self._recarregar_dados_sistema,
            initial_tab=tab,
            start_hidden=False
        )
        self._admin_window.mostrar(tab=tab)

    def _abrir_balanco(self):
        """Abre a janela isolada de Balanço Geral / Relatórios Financeiros."""
        balanco = ScreenBalanco(self)
        balanco.focus()

    def _abrir_logs(self):
        """Abre a janela de diagnóstico e logs de erro do sistema."""
        logs_win = ScreenLogs(self)
        logs_win.focus()

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

    def _abrir_login(self):
        """Abre a janela de autenticação com o Supabase."""
        from ui.screen_auth import ScreenAuth
        auth_win = ScreenAuth(
            self,
            on_success=self._on_login_sucesso,
            on_offline=self._on_login_offline
        )
        auth_win.focus()

    def _on_login_sucesso(self):
        """Callback acionado após login bem-sucedido."""
        # Garante que todas as TopBars ocultem o botão de login imediatamente
        for tela in getattr(self, "_telas", {}).values():
            if hasattr(tela, "_topbar") and hasattr(tela._topbar, "atualizar_status_auth"):
                tela._topbar.atualizar_status_auth(True)

        # Sincronização em segundo plano não-bloqueante (zero congelamento de interface)
        import threading
        def _sync_worker():
            try:
                from services.supabase_sync import sincronizar_tudo_com_supabase
                sincronizar_tudo_com_supabase(timeout=6)
                self.after(0, self._recarregar_dados_sistema)
            except Exception as e:
                print(f"Aviso na sincronização em segundo plano: {e}")

        threading.Thread(target=_sync_worker, daemon=True).start()

    def _on_login_offline(self):
        """Callback acionado quando o usuário opta por continuar offline."""
        pass

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

    def _ao_fechar_aplicacao(self):
        """Sincroniza pedidos pendentes e dados com o Supabase antes de encerrar o aplicativo."""
        try:
            self.withdraw()  # Oculta a janela de imediato para fechamento visual instantâneo
            from services.supabase_sync import sincronizar_tudo_com_supabase
            sincronizar_tudo_com_supabase(timeout=4)
        except Exception as e:
            print(f"Aviso na sincronização ao fechar: {e}")
        finally:
            self.destroy()


# ── Ponto de entrada ──────────────────────────────────────────────────────────

def main():
    # 1. Instanciar aplicação com janela temporariamente oculta
    app = App(start_hidden=True)

    # 2. Exibir imediatamente a Splash Screen animada
    from ui.components.loading import SplashScreen
    splash = SplashScreen(app, status="Inicializando banco de dados SQLite...")

    # 3. Inicializar banco e migrações
    splash.update_status("Verificando tabelas e migrações...")
    init_db()

    # 4. Popular cardápio, taxas e configurações
    splash.update_status("Carregando cardápio e configurações...")
    run_all_seeds()

    # 5. Montar telas e componentes do PDV
    splash.update_status("Carregando catálogo e telas do PDV...")
    app.setup_ui()

    # 6. Transição suave: fechar splash e autenticar ou abrir tela principal
    from services.supabase_auth import auth_manager
    from ui.screen_auth import ScreenAuth

    def _iniciar_fluxo_autenticacao():
        splash.close()
        if auth_manager.is_authenticated():
            # Já autenticado com sessão salva: abre IMEDIATAMENTE (0ms) e sincroniza em background
            app.mostrar_janela_principal()
            app._on_login_sucesso()
        else:
            # Não autenticado: exibe tela de login antes de abrir a tela principal
            def _ao_sucesso():
                app.mostrar_janela_principal()
                app._on_login_sucesso()

            auth_modal = ScreenAuth(
                app,
                on_success=_ao_sucesso,
                on_offline=lambda: app.mostrar_janela_principal()
            )
            auth_modal.focus()

    splash.update_status("Pronto!")
    app.after(350, _iniciar_fluxo_autenticacao)
    app.mainloop()


if __name__ == "__main__":
    main()
