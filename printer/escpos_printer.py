# printer/escpos_printer.py - Impressão ESC/POS (Rede TCP 9100 e Cabo USB Windows)
# =============================================================================

import socket
import threading
import subprocess
import ctypes
import ctypes.wintypes
import customtkinter as ctk

from config import (
    PRINTER_PORT, PRINTER_TIMEOUT,
    PRINTER_TIPO_DEFAULT, PRINTER_IP_DEFAULT, PRINTER_USB_DEFAULT
)


# Comandos ESC/POS
ESC = b'\x1b'
GS  = b'\x1d'

CMD_INIT          = ESC + b'@'           # Inicializar impressora
CMD_ALIGN_LEFT    = ESC + b'a\x00'       # Alinhar à esquerda
CMD_ALIGN_CENTER  = ESC + b'a\x01'       # Centralizar
CMD_ALIGN_RIGHT   = ESC + b'a\x02'       # Alinhar à direita
CMD_BOLD_ON       = ESC + b'E\x01'       # Negrito ligado
CMD_BOLD_OFF      = ESC + b'E\x00'       # Negrito desligado
CMD_DOUBLE_HEIGHT = ESC + b'!\x10'       # Fonte dupla altura
CMD_NORMAL_SIZE   = ESC + b'!\x00'       # Tamanho normal
CMD_FEED_LINE     = b'\n'
CMD_CUT           = GS  + b'V\x00'       # Corte total guilhotina

# ── Seleção de Code Page para acentuação correta na Elgin i8 ──
# ESC t n → Seleciona tabela de caracteres:
#   \x02 = CP850 (Multilingual Latin I - suporta ç, ã, õ, é, etc.)
#   \x03 = CP860 (Portuguese)
# A Elgin i8 suporta ambas; CP850 é mais abrangente.
CMD_CODEPAGE_CP850 = ESC + b't\x02'      # Selecionar CP850

# Tabela de fallback para caracteres que o CP850 não cobre
_FALLBACK_MAP = {
    '\u2013': '-',   # en-dash → hífen
    '\u2014': '-',   # em-dash → hífen
    '\u2018': "'",   # left single quote
    '\u2019': "'",   # right single quote / apóstrofo curvo
    '\u201c': '"',   # left double quote
    '\u201d': '"',   # right double quote
    '\u2026': '...', # ellipsis
    '\u00b0': 'o',   # degree sign → o
    '\u0300': '',    # combining grave accent
    '\u0301': '',    # combining acute accent
    '\u0303': '',    # combining tilde
    '\u0327': '',    # combining cedilla
}


def _normalize_for_print(text: str) -> str:
    """
    Normaliza caracteres especiais que podem não existir na tabela CP850.
    Aplica mapeamento de fallback antes da codificação para evitar '?' ou lixo visual.
    """
    import unicodedata
    # 1. Normalizar para NFC (forma composta) para que ç, ã, é fiquem como um só codepoint
    text = unicodedata.normalize('NFC', text)
    # 2. Aplicar fallback map para caracteres especiais fora do CP850
    for char, replacement in _FALLBACK_MAP.items():
        text = text.replace(char, replacement)
    return text


def _encode(text: str) -> bytes:
    """
    Codifica texto para CP850 (compatível com Elgin i8).
    Aplica normalização prévia para garantir que ç, ã, õ, é, ê, etc.
    sejam impressos corretamente, sem lixo visual na bobina térmica.
    """
    text = _normalize_for_print(text)
    return text.encode("cp850", errors="replace")


class PrinterError(Exception):
    pass


# ── Windows Spooler API (USB / Local RAW) ─────────────────────────────────────

class DOC_INFO_1(ctypes.Structure):
    _fields_ = [
        ("pDocName", ctypes.c_wchar_p),
        ("pOutputFile", ctypes.c_wchar_p),
        ("pDatatype", ctypes.c_wchar_p),
    ]


def _get_winspool():
    try:
        return ctypes.WinDLL("winspool.drv")
    except Exception:
        return None


def listar_impressoras_windows() -> list[str]:
    """Retorna lista de nomes das impressoras instaladas no Windows."""
    try:
        cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Printer | Select-Object -ExpandProperty Name"]
        out = subprocess.check_output(cmd, text=True, timeout=5)
        printers = [p.strip() for p in out.strip().split("\n") if p.strip()]
        return sorted(printers)
    except Exception:
        return ["Elgin i8", "POS-80", "Generic / Text Only"]


def send_to_usb_printer(printer_name: str, data: bytes) -> None:
    """
    Envia bytes ESC/POS diretamente para uma impressora USB no Windows Spooler.
    Suporta também portas seriais COM virtuais (ex: COM1, COM3).
    """
    if not printer_name:
        raise PrinterError("Nome da impressora USB não informado.")

    # Suporte a porta COM virtual (se informado COMx)
    if printer_name.upper().startswith("COM"):
        try:
            with open(rf"\\.\{printer_name.upper()}", "wb", buffering=0) as f:
                f.write(data)
            return
        except Exception as exc:
            raise PrinterError(f"Erro ao comunicar com porta {printer_name}: {exc}") from exc

    winspool = _get_winspool()
    if not winspool:
        raise PrinterError("winspool.drv não disponível neste sistema operacional.")

    OpenPrinterW = winspool.OpenPrinterW
    OpenPrinterW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.wintypes.HANDLE), ctypes.c_void_p]
    OpenPrinterW.restype = ctypes.wintypes.BOOL

    ClosePrinter = winspool.ClosePrinter
    ClosePrinter.argtypes = [ctypes.wintypes.HANDLE]
    ClosePrinter.restype = ctypes.wintypes.BOOL

    StartDocPrinterW = winspool.StartDocPrinterW
    StartDocPrinterW.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD, ctypes.POINTER(DOC_INFO_1)]
    StartDocPrinterW.restype = ctypes.wintypes.DWORD

    EndDocPrinter = winspool.EndDocPrinter
    EndDocPrinter.argtypes = [ctypes.wintypes.HANDLE]
    EndDocPrinter.restype = ctypes.wintypes.BOOL

    StartPagePrinter = winspool.StartPagePrinter
    StartPagePrinter.argtypes = [ctypes.wintypes.HANDLE]
    StartPagePrinter.restype = ctypes.wintypes.BOOL

    EndPagePrinter = winspool.EndPagePrinter
    EndPagePrinter.argtypes = [ctypes.wintypes.HANDLE]
    EndPagePrinter.restype = ctypes.wintypes.BOOL

    WritePrinter = winspool.WritePrinter
    WritePrinter.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.c_char_p,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(ctypes.wintypes.DWORD),
    ]
    WritePrinter.restype = ctypes.wintypes.BOOL

    hPrinter = ctypes.wintypes.HANDLE()
    if not OpenPrinterW(printer_name, ctypes.byref(hPrinter), None):
        err = ctypes.GetLastError()
        raise PrinterError(
            f"Impressora USB '{printer_name}' não encontrada ou desconectada (Código {err}).\n"
            f"Verifique se o cabo USB está plugado e se o driver da Elgin i8 está instalado."
        )

    try:
        doc_info = DOC_INFO_1(
            pDocName="Point Lanches - Pedido",
            pOutputFile=None,
            pDatatype="RAW"
        )
        job_id = StartDocPrinterW(hPrinter, 1, ctypes.byref(doc_info))
        if job_id == 0:
            err = ctypes.GetLastError()
            raise PrinterError(f"Falha ao abrir fila de impressão na impressora '{printer_name}' (Código {err}).")

        try:
            if not StartPagePrinter(hPrinter):
                err = ctypes.GetLastError()
                raise PrinterError(f"Falha ao iniciar página na impressora '{printer_name}' (Código {err}).")

            try:
                bytes_written = ctypes.wintypes.DWORD(0)
                if not WritePrinter(hPrinter, data, len(data), ctypes.byref(bytes_written)):
                    err = ctypes.GetLastError()
                    raise PrinterError(f"Erro ao transmitir dados para a impressora '{printer_name}' (Código {err}).")
            finally:
                EndPagePrinter(hPrinter)
        finally:
            EndDocPrinter(hPrinter)
    finally:
        ClosePrinter(hPrinter)


def test_connection_usb(printer_name: str) -> bool:
    """Testa se a impressora USB no Windows pode ser aberta."""
    if not printer_name:
        return False
    if printer_name.upper().startswith("COM"):
        try:
            with open(rf"\\.\{printer_name.upper()}", "wb", buffering=0):
                return True
        except Exception:
            return False

    winspool = _get_winspool()
    if not winspool:
        return False

    OpenPrinterW = winspool.OpenPrinterW
    OpenPrinterW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.wintypes.HANDLE), ctypes.c_void_p]
    OpenPrinterW.restype = ctypes.wintypes.BOOL

    ClosePrinter = winspool.ClosePrinter
    ClosePrinter.argtypes = [ctypes.wintypes.HANDLE]
    ClosePrinter.restype = ctypes.wintypes.BOOL

    hPrinter = ctypes.wintypes.HANDLE()
    if OpenPrinterW(printer_name, ctypes.byref(hPrinter), None):
        ClosePrinter(hPrinter)
        return True
    return False


# ── Conexão Rede TCP Socket ───────────────────────────────────────────────────

def send_to_network_printer(ip: str, data: bytes, port: int = PRINTER_PORT) -> None:
    """Envia bytes ESC/POS via TCP Socket na porta especificada."""
    try:
        with socket.create_connection((ip, port), timeout=PRINTER_TIMEOUT) as s:
            s.sendall(data)
    except (socket.timeout, ConnectionRefusedError, OSError) as exc:
        raise PrinterError(f"Impressora Elgin i8 offline ou inacessível em {ip}:{port}\n{exc}") from exc


def test_connection_network(ip: str, port: int = PRINTER_PORT) -> bool:
    """Testa se consegue abrir socket para a impressora de rede."""
    try:
        with socket.create_connection((ip, port), timeout=PRINTER_TIMEOUT):
            return True
    except Exception:
        return False


# ── Ponto Central de Envio e Teste ────────────────────────────────────────────

def test_connection(destino: str = None, tipo: str = None) -> bool:
    """Testa a conexão de acordo com o tipo ('rede' ou 'usb')."""
    from database.db import get_config
    if not tipo:
        tipo = get_config("printer_tipo", PRINTER_TIPO_DEFAULT)
    if tipo == "usb":
        printer_name = destino or get_config("printer_usb", PRINTER_USB_DEFAULT)
        return test_connection_usb(printer_name)
    else:
        ip = destino or get_config("printer_ip", PRINTER_IP_DEFAULT)
        return test_connection_network(ip)


def send_to_printer(destino: str, data: bytes) -> None:
    """
    Roteador de envio de dados:
    Determina automaticamente se 'destino' é IP de rede ou nome USB do Windows.
    """
    from database.db import get_config
    tipo = get_config("printer_tipo", PRINTER_TIPO_DEFAULT)

    # Se tipo for explicitamente usb ou destino não for formato IP
    if tipo == "usb" or not any(char.isdigit() and "." in destino for char in destino):
        send_to_usb_printer(destino, data)
    else:
        send_to_network_printer(destino, data)


def imprimir_ticket(arg1, arg2=None, on_success=None, on_error=None) -> None:
    """
    Envia o ticket em thread assíncrona para não travar a interface gráfica.
    Compatível com chamadas:
      - imprimir_ticket(ticket_bytes, on_success=..., on_error=...)
      - imprimir_ticket(destino, ticket_bytes, on_success=..., on_error=...)
    """
    from database.db import get_config

    if isinstance(arg1, bytes):
        ticket_bytes = arg1
        tipo = get_config("printer_tipo", PRINTER_TIPO_DEFAULT)
        if tipo == "usb":
            destino = get_config("printer_usb", PRINTER_USB_DEFAULT)
        else:
            destino = get_config("printer_ip", PRINTER_IP_DEFAULT)
    else:
        destino = arg1
        ticket_bytes = arg2

    def _run():
        try:
            send_to_printer(destino, ticket_bytes)
            if on_success:
                on_success()
        except Exception as e:
            if on_error:
                on_error(str(e))

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def show_printer_error_popup(parent, mensagem: str, retry_callback=None):
    """Exibe pop-up amigável de erro de impressão com opção de retry."""
    win = ctk.CTkToplevel(parent)
    win.title("Erro de Impressão")
    win.geometry("500x290")
    win.grab_set()
    win.resizable(False, False)

    win.update_idletasks()
    px = parent.winfo_rootx() + parent.winfo_width() // 2 - 250
    py = parent.winfo_rooty() + parent.winfo_height() // 2 - 145
    win.geometry(f"+{max(0, px)}+{max(0, py)}")

    ctk.CTkLabel(
        win, text="⚠️  Falha na Impressora Elgin i8",
        font=ctk.CTkFont(size=19, weight="bold")
    ).pack(pady=(22, 6))

    ctk.CTkLabel(
        win, text=mensagem,
        wraplength=440, justify="center",
        font=ctk.CTkFont(size=12)
    ).pack(pady=8, padx=20)

    btn_frame = ctk.CTkFrame(win, fg_color="transparent")
    btn_frame.pack(pady=16, fill="x", padx=30)

    if retry_callback:
        ctk.CTkButton(
            btn_frame, text="🔄  Tentar Novamente",
            width=180, height=44,
            fg_color="#0284C7", hover_color="#0369A1",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: [win.destroy(), retry_callback()]
        ).pack(side="left", padx=8)

    ctk.CTkButton(
        btn_frame, text="✖  Fechar",
        width=130, height=44,
        fg_color="#E74C3C", hover_color="#C0392B",
        font=ctk.CTkFont(size=14, weight="bold"),
        command=win.destroy
    ).pack(side="right", padx=8)
