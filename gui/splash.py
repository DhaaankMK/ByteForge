"""
gui/splash.py
-----------------

Tela de splash (carregamento inicial) do ByteForge, exibida por um
curto período antes da janela principal, reforçando a identidade
visual da marca e tornando a abertura do aplicativo mais fluida e
agradável.

Esta tela é puramente cosmética: não realiza nenhuma lógica de
inicialização real (toda a configuração de diretórios, logging e
carregamento de configurações já ocorre normalmente em `main.py`
antes ou depois da exibição da splash). Ela apenas anima a logo, um
texto de carregamento com pontos cíclicos e uma barra de progresso
indeterminada, fechando-se automaticamente após `duration_ms`.

Nota de implementação — por que desenhar tudo no Canvas:
    `CTkLabel`/`CTkFrame` com `fg_color="transparent"` resolvem sua
    própria cor de fundo consultando o fg_color *declarado* do seu
    widget mestre — não os pixels efetivamente renderizados por um
    Canvas irmão. Como o fundo da splash é um gradiente (e não uma
    cor sólida), qualquer widget "transparente" posicionado sobre o
    `GradientBanner` acabaria pintando um retângulo sólido (a cor de
    fundo da janela) por engano, ocultando o gradiente. Por isso,
    logo, título, subtítulo e texto de carregamento são desenhados
    diretamente no Canvas via `create_image`/`create_text` — a mesma
    técnica já usada com sucesso nos cabeçalhos das demais abas.
"""

from __future__ import annotations

import logging

import customtkinter as ctk

from gui import theme
from gui.widgets import GradientBanner

logger = logging.getLogger("ByteForge.gui.splash")

try:
    from PIL import Image, ImageTk
    _PIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PIL_AVAILABLE = False

SPLASH_WIDTH = 480
SPLASH_HEIGHT = 320

_DOT_FRAMES = ["", ".", "..", "..."]


class SplashScreen(ctk.CTk):
    """Janela de splash exibida durante a inicialização do ByteForge."""

    def __init__(self, duration_ms: int = 1600) -> None:
        super().__init__()
        self._duration_ms = duration_ms
        self._closed = False
        self._logo_photo = None
        self._loading_text_id = None
        self._dot_frame_index = 0

        ctk.set_appearance_mode("Dark")

        # Janela sem moldura/título, central na tela, para um visual
        # de splash limpo e profissional.
        self.overrideredirect(True)
        self.configure(fg_color=theme.GRADIENT_BLACK)
        self.geometry(f"{SPLASH_WIDTH}x{SPLASH_HEIGHT}")
        self._center_on_screen()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_widgets()

        # Agenda o fechamento automático da splash após a duração
        # configurada, devolvendo o controle para `main.py` seguir
        # com a criação da janela principal.
        self.after(self._duration_ms, self._finish)

    def _center_on_screen(self) -> None:
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - SPLASH_WIDTH) // 2
        y = (screen_h - SPLASH_HEIGHT) // 2
        self.geometry(f"{SPLASH_WIDTH}x{SPLASH_HEIGHT}+{x}+{y}")

    def _build_widgets(self) -> None:
        self.banner = GradientBanner(
            self, height=SPLASH_HEIGHT, show_logo=False, highlightthickness=0,
        )
        self.banner.grid(row=0, column=0, sticky="nsew")

        if _PIL_AVAILABLE and theme.LOGO_PATH.exists():
            try:
                img = Image.open(theme.LOGO_PATH).convert("RGBA").resize((84, 84), Image.LANCZOS)
                self._logo_photo = ImageTk.PhotoImage(img)
            except Exception:  # pragma: no cover
                logger.exception("Falha ao carregar a logo na tela de splash.")

        # Desenha o conteúdo inicial e garante que ele seja redesenhado
        # sempre que o gradiente for redesenhado (ex.: primeiro evento
        # de mapeamento da janela), evitando que o texto "desapareça"
        # por trás do próximo redraw do gradiente.
        self.banner.bind("<Configure>", self._draw_overlay_content, add="+")
        self.after(30, self._draw_overlay_content)

        # Barra de progresso indeterminada nativa do CustomTkinter.
        # Mantida como widget (não desenhada no canvas) porque sua
        # cor de preenchimento é sólida e intencional (não depende de
        # transparência sobre o gradiente).
        self.progress_bar = ctk.CTkProgressBar(
            self, width=260, height=6, mode="indeterminate",
            progress_color=theme.ACCENT_HOVER, fg_color=theme.GRADIENT_NAVY,
        )
        self.progress_bar.place(in_=self.banner, relx=0.5, rely=0.88, anchor="center")
        self.progress_bar.start()

        self._animate_dots()

    def _draw_overlay_content(self, _event=None) -> None:
        banner = self.banner
        width = banner.winfo_width()
        height = banner.winfo_height()
        if width <= 1 or height <= 1:
            return

        banner.delete("overlay")
        cx = width / 2

        if self._logo_photo is not None:
            banner.create_image(cx, height * 0.28, image=self._logo_photo, anchor="center", tags="overlay")

        banner.create_text(
            cx, height * 0.50, text="ByteForge", anchor="center", tags="overlay",
            fill=theme.TEXT_PRIMARY, font=("Segoe UI", 26, "bold"),
        )
        banner.create_text(
            cx, height * 0.60, text="Gerador Profissional de Arquivos Dummy",
            anchor="center", tags="overlay", fill=theme.TEXT_MUTED, font=("Segoe UI", 11),
        )
        self._loading_text_id = banner.create_text(
            cx, height * 0.76, text="Carregando", anchor="center", tags="overlay",
            fill=theme.TEXT_MUTED, font=("Segoe UI", 11),
        )

    def _animate_dots(self) -> None:
        if self._closed or self._loading_text_id is None:
            if not self._closed:
                self.after(60, self._animate_dots)
            return
        try:
            suffix = _DOT_FRAMES[self._dot_frame_index % len(_DOT_FRAMES)]
            self.banner.itemconfig(self._loading_text_id, text=f"Carregando{suffix}")
        except Exception:  # pragma: no cover
            return
        self._dot_frame_index += 1
        self.after(350, self._animate_dots)

    def _finish(self) -> None:
        self._closed = True
        try:
            self.progress_bar.stop()
        except Exception:  # pragma: no cover
            pass
        try:
            self.destroy()
        except Exception:  # pragma: no cover
            pass


def show_splash(duration_ms: int = 1600) -> None:
    """
    Cria, exibe e aguarda o fechamento automático da tela de splash.
    Esta função é bloqueante (executa seu próprio `mainloop`) e
    retorna o controle ao chamador somente após a splash se fechar,
    permitindo que `main.py` siga normalmente para a criação da
    janela principal do ByteForge.
    """
    try:
        splash = SplashScreen(duration_ms=duration_ms)
        splash.mainloop()
    except Exception:  # pragma: no cover - a splash nunca deve impedir o app de abrir
        logger.exception("Falha ao exibir a tela de splash. Prosseguindo sem ela.")
