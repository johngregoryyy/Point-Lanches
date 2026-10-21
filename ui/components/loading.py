# ui/components/loading.py - Componente de Loading e Splash Screen com GIF animado
# =============================================================================

import os
import sys
import tkinter as tk
from PIL import Image, ImageSequence
import customtkinter as ctk

from config import (
    COR_FUNDO, COR_CINZA_BARRA, COR_TEXTO, COR_TEXTO_SUAVE,
    COR_AZUL_POINT, COR_SECUNDARIA, COR_PRIMARIA
)


def get_asset_path(filename: str) -> str:
    """
    Retorna o caminho absoluto do asset, compatível com PyInstaller (_MEIPASS)
    e ambiente de desenvolvimento.
    """
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    for folder in ("assets", "Assets"):
        p = os.path.join(base, folder, filename)
        if os.path.exists(p):
            return p
    return os.path.join(base, "assets", filename)


# Cache global de frames pré-renderizados para evitar decodificação repetida
_GIF_CACHE: dict[tuple, tuple[list, list]] = {}


class AnimatedGif(ctk.CTkFrame):
    """
    Widget CustomTkinter que renderiza um GIF animado usando Pillow e CustomTkinter.
    Controla o ciclo de animação via after() do Tkinter de forma não-bloqueante.
    """

    def __init__(
        self,
        parent,
        gif_path: str = None,
        size: tuple[int, int] = (200, 113),
        bg_color: str = "transparent",
        autoplay: bool = True,
        **kwargs
    ):
        super().__init__(parent, fg_color=bg_color, **kwargs)
        self._size = size
        self._gif_path = gif_path or get_asset_path("loading.gif")
        self._frames: list[ctk.CTkImage] = []
        self._durations: list[int] = []
        self._current_idx = 0
        self._after_id = None
        self._is_running = False

        self._label = ctk.CTkLabel(self, text="", fg_color="transparent")
        self._label.pack(expand=True, fill="both")

        self._load_frames()

        if autoplay and self._frames:
            self.start()

    def _load_frames(self):
        """Carrega e converte frames do GIF com cache em memória e amostragem inteligente."""
        cache_key = (self._gif_path, self._size)
        if cache_key in _GIF_CACHE:
            cached_frames, cached_durs = _GIF_CACHE[cache_key]
            self._frames = list(cached_frames)
            self._durations = list(cached_durs)
            if self._frames:
                self._label.configure(image=self._frames[0])
            return

        if not os.path.isfile(self._gif_path):
            return

        try:
            with Image.open(self._gif_path) as im:
                frames_raw = list(ImageSequence.Iterator(im))
                total = len(frames_raw)
                # Amostragem para manter ~30 frames fluidos sem travar a CPU
                step = max(1, total // 35) if total > 35 else 1

                for idx in range(0, total, step):
                    frame = frames_raw[idx]
                    f_rgba = frame.convert("RGBA")
                    if self._size:
                        f_rgba = f_rgba.resize(self._size, Image.Resampling.BILINEAR)
                    ctk_img = ctk.CTkImage(
                        light_image=f_rgba,
                        dark_image=f_rgba,
                        size=self._size
                    )
                    self._frames.append(ctk_img)
                    dur = frame.info.get("duration", 50)
                    dur_total = dur * step if dur else 50 * step
                    self._durations.append(max(30, min(200, dur_total)))

            if self._frames:
                _GIF_CACHE[cache_key] = (list(self._frames), list(self._durations))
                self._label.configure(image=self._frames[0])
        except Exception:
            pass

    def start(self):
        """Inicia a animação."""
        if self._is_running or not self._frames:
            return
        self._is_running = True
        self._animate()

    def stop(self):
        """Pausa/interrompe a animação."""
        self._is_running = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _animate(self):
        """Passa para o próximo frame e agenda o seguinte."""
        if not self._is_running or not self._frames:
            return

        self._current_idx = (self._current_idx + 1) % len(self._frames)
        try:
            self._label.configure(image=self._frames[self._current_idx])
            delay = self._durations[self._current_idx]
            self._after_id = self.after(delay, self._animate)
        except Exception:
            self._is_running = False

    def destroy(self):
        """Garante cancelamento do loop de after ao destruir o widget."""
        self.stop()
        super().destroy()


class LoadingOverlay(ctk.CTkFrame):
    """
    Overlay escuro com GIF de loading centralizado e mensagem de status.
    Pode ser colocado sobre qualquer frame ou janela durante operações demoradas.
    """

    def __init__(
        self,
        parent,
        text: str = "Carregando...",
        size: tuple[int, int] = (160, 90),
        bg_color: str = COR_FUNDO,
        **kwargs
    ):
        super().__init__(parent, fg_color=bg_color, corner_radius=0, **kwargs)
        self._text_var = ctk.StringVar(value=text)

        # Card central
        card = ctk.CTkFrame(
            self,
            fg_color=COR_CINZA_BARRA,
            corner_radius=12,
            border_width=1,
            border_color=COR_SECUNDARIA
        )
        card.place(relx=0.5, rely=0.5, anchor="center")

        # GIF animado
        self._gif = AnimatedGif(
            card,
            size=size,
            bg_color="transparent",
            autoplay=False
        )
        self._gif.pack(padx=20, pady=(16, 8))

        # Texto de status
        self._lbl = ctk.CTkLabel(
            card,
            textvariable=self._text_var,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COR_TEXTO
        )
        self._lbl.pack(padx=20, pady=(0, 16))

    def show(self, text: str = None):
        """Exibe o overlay com animação ativa."""
        if text:
            self._text_var.set(text)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.tkraise()
        self._gif.start()
        try:
            self.update_idletasks()
        except Exception:
            pass

    def update_text(self, text: str):
        """Atualiza a mensagem em tempo real."""
        self._text_var.set(text)
        try:
            self.update_idletasks()
        except Exception:
            pass

    def hide(self):
        """Oculta o overlay e pausa o GIF."""
        self._gif.stop()
        self.place_forget()

    def destroy(self):
        self._gif.stop()
        super().destroy()


class SplashScreen(ctk.CTkToplevel):
    """
    Janela de Splash Screen inicial exibida imediatamente na inicialização
    enquanto os recursos pesados do PDV são carregados em segundo plano.
    """

    def __init__(
        self,
        parent,
        status: str = "Iniciando Point Lanches...",
        width: int = 380,
        height: int = 260,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self._status_var = ctk.StringVar(value=status)

        # Configurações de janela: sem barra de título, sempre no topo
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=COR_FUNDO)

        # Centralizar na tela
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Borda e card decorativo
        card = ctk.CTkFrame(
            self,
            fg_color=COR_CINZA_BARRA,
            corner_radius=12,
            border_width=2,
            border_color=COR_SECUNDARIA
        )
        card.pack(fill="both", expand=True, padx=4, pady=4)

        # Cabeçalho
        ctk.CTkLabel(
            card,
            text="🍔  POINT LANCHES",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=COR_AZUL_POINT
        ).pack(pady=(16, 2))

        ctk.CTkLabel(
            card,
            text="Sistema Comercial PDV & Tele-Entrega",
            font=ctk.CTkFont(size=11),
            text_color=COR_TEXTO_SUAVE
        ).pack(pady=(0, 10))

        # GIF animado
        self._gif = AnimatedGif(
            card,
            size=(190, 107),
            bg_color="transparent",
            autoplay=True
        )
        self._gif.pack(pady=(0, 10))

        # Status
        self._lbl_status = ctk.CTkLabel(
            card,
            textvariable=self._status_var,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COR_TEXTO_SUAVE
        )
        self._lbl_status.pack(pady=(0, 12))

        try:
            self.update()
        except Exception:
            pass

    def update_status(self, text: str):
        """Atualiza a mensagem de status da splash screen."""
        self._status_var.set(text)
        try:
            self.update()
        except Exception:
            pass

    def close(self):
        """Para a animação e destrói a splash screen."""
        try:
            self._gif.stop()
            self.destroy()
        except Exception:
            pass
