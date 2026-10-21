# services/error_logger.py - Gerenciamento e Captura Centralizada de Logs de Erro
# =============================================================================

import sys
import threading
import traceback
from datetime import datetime


def log_error(modulo: str, mensagem: str, detalhes: str = "", tipo: str = "ERRO") -> int:
    """
    Registra um erro no banco SQLite local e despacha para o Supabase.
    Tipos comuns: 'ERRO', 'EXCEÇÃO', 'IMPRESSORA', 'SUPABASE', 'SISTEMA', 'AVISO'.
    """
    try:
        from database.db import registrar_log_erro
        return registrar_log_erro(modulo=modulo, mensagem=mensagem, detalhes=detalhes, tipo=tipo)
    except Exception as e:
        print(f"[ERROR_LOGGER_FALLBACK] {modulo}: {mensagem} | Detalhes: {detalhes} | Falha ao persistir: {e}")
        return 0


def log_exception(modulo: str, exc: BaseException, contexto: str = "", tipo: str = "EXCEÇÃO") -> int:
    """Captura uma exceção com seu traceback completo formatado."""
    msg = f"{contexto + ': ' if contexto else ''}{type(exc).__name__}: {str(exc)}"
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return log_error(modulo=modulo, mensagem=msg, detalhes=tb, tipo=tipo)


def setup_global_exception_handlers(tk_app=None):
    """
    Configura interceptadores globais de exceções não tratadas:
    - sys.excepthook (threads principais)
    - threading.excepthook (threads em background)
    - Tk.report_callback_exception (callbacks de interface gráfica CustomTkinter/Tkinter)
    """
    def _sys_excepthook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        msg = f"Exceção não tratada: {exc_type.__name__}: {str(exc_value)}"
        print(f"\n[GLOBAL_EXCEPTHOOK] {msg}\n{tb}")
        log_error(modulo="sistema", mensagem=msg, detalhes=tb, tipo="EXCEÇÃO")

    sys.excepthook = _sys_excepthook

    if hasattr(threading, "excepthook"):
        def _threading_excepthook(args):
            if issubclass(args.exc_type, KeyboardInterrupt):
                return
            tb = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
            thread_nome = args.thread.name if args.thread else "desconhecida"
            msg = f"Exceção na thread '{thread_nome}': {args.exc_type.__name__}: {str(args.exc_value)}"
            print(f"\n[THREAD_EXCEPTHOOK] {msg}\n{tb}")
            log_error(modulo="thread", mensagem=msg, detalhes=tb, tipo="EXCEÇÃO")

        threading.excepthook = _threading_excepthook

    if tk_app is not None and hasattr(tk_app, "report_callback_exception"):
        def _tk_callback_exception(exc_type, exc_value, exc_traceback):
            tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            msg = f"Exceção de UI Tkinter: {exc_type.__name__}: {str(exc_value)}"
            print(f"\n[TK_CALLBACK_EXCEPTHOOK] {msg}\n{tb}")
            log_error(modulo="ui", mensagem=msg, detalhes=tb, tipo="EXCEÇÃO")

        tk_app.report_callback_exception = _tk_callback_exception
