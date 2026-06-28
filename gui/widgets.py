"""
gui/widgets.py
------------------

Componentes visuais reutilizáveis e puramente cosméticos do
ByteForge. Nenhuma classe ou função deste módulo contém lógica de
negócio — todas operam exclusivamente sobre a apresentação visual,
podendo ser livremente reutilizadas em qualquer aba da aplicação.

Conteúdo:
    * `GradientBanner`  — cabeçalho com gradiente horizontal (cores
      extraídas da identidade visual oficial do ByteForge), logo e
      título/subtítulo.
    * `SmoothProgress`  — wrapper de animação para `CTkProgressBar`,
      interpolando suavemente entre o valor atual e o valor alvo em
      vez de "saltar" instantaneamente.
    * `pulse_label`     — pequena animação de "pulso" (efeito de
      clique/bounce) aplicada à fonte de um `CTkLabel`.
    * `slide_in_vertical` — efeito de entrada deslizante (slide-in)
      para painéis revelados dinamicamente (ex.: easter eggs).
    * `flash_widget_color` — pisca rapidamente a cor de fundo de um
      widget (ex.: confirmação visual de sucesso) e retorna à cor
      original.
"""

from __future__ import annotations

import tkinter as tk
import logging
from typing import Callable, List, Optional, Tuple

import customtkinter as ctk

from gui import theme

logger = logging.getLogger("ByteForge.gui.widgets")

try:
    from PIL import Image, ImageTk
    _PIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PIL_AVAILABLE = False


# ===========================================================================
# GradientBanner — cabeçalho com gradiente de marca
# ===========================================================================

class GradientBanner(tk.Canvas):
    """
    Canvas que desenha um gradiente horizontal multi-tonal (extraído
    da arte oficial do ByteForge), com a logomarca e um título/
    subtítulo sobrepostos. Redesenha automaticamente ao ser
    redimensionado, mantendo o visual fluido em qualquer tamanho de
    janela.
    """

    def __init__(
        self,
        master,
        height: int = 110,
        title: str = "",
        subtitle: str = "",
        show_logo: bool = True,
        logo_size: int = 60,
        stops: Optional[List[str]] = None,
        title_font_size: int = 21,
        subtitle_font_size: int = 12,
        **kwargs,
    ) -> None:
        super().__init__(master, height=height, **kwargs)
        self.configure(highlightthickness=0, bd=0)
        self._height = height
        self._title_text = title
        self._subtitle_text = subtitle
        self._show_logo = show_logo
        self._logo_size = logo_size
        self._stops = stops or theme.BRAND_GRADIENT_STOPS
        self._title_font_size = title_font_size
        self._subtitle_font_size = subtitle_font_size
        self._logo_photo: Optional["ImageTk.PhotoImage"] = None

        self._load_logo()
        self.bind("<Configure>", self._on_resize)

    def _load_logo(self) -> None:
        if not self._show_logo or not _PIL_AVAILABLE:
            return
        try:
            if theme.LOGO_PATH.exists():
                img = Image.open(theme.LOGO_PATH).convert("RGBA")
                img = img.resize((self._logo_size, self._logo_size), Image.LANCZOS)
                self._logo_photo = ImageTk.PhotoImage(img)
        except Exception:  # pragma: no cover
            logger.exception("Falha ao carregar a logo do ByteForge para o banner.")
            self._logo_photo = None

    def _on_resize(self, event) -> None:
        self._redraw(event.width, event.height)

    def _redraw(self, width: int, height: int) -> None:
        self.delete("all")
        if width <= 1 or height <= 1:
            return

        strip_count = max(1, min(160, width // 3))
        colors = theme.multi_stop_gradient(self._stops, strip_count)
        strip_width = width / strip_count

        for i, color in enumerate(colors):
            x0 = i * strip_width
            x1 = x0 + strip_width + 1
            self.create_rectangle(x0, 0, x1, height, fill=color, outline=color)

        text_x = 26
        if self._logo_photo is not None:
            logo_cx = 26 + self._logo_size / 2
            self.create_image(logo_cx, height / 2, image=self._logo_photo, anchor="center")
            text_x = 26 + self._logo_size + 18

        if self._title_text:
            y_title = height / 2 - (11 if self._subtitle_text else 0)
            self.create_text(
                text_x, y_title, text=self._title_text, anchor="w",
                fill=theme.TEXT_PRIMARY, font=("Segoe UI", self._title_font_size, "bold"),
            )
        if self._subtitle_text:
            self.create_text(
                text_x, height / 2 + 16, text=self._subtitle_text, anchor="w",
                fill=theme.TEXT_MUTED, font=("Segoe UI", self._subtitle_font_size),
            )

    def update_texts(self, title: Optional[str] = None, subtitle: Optional[str] = None) -> None:
        """Permite atualizar os textos do banner sem recriar o widget."""
        if title is not None:
            self._title_text = title
        if subtitle is not None:
            self._subtitle_text = subtitle
        self._redraw(self.winfo_width(), self.winfo_height())


def load_ctk_image(path, size: Tuple[int, int]) -> Optional[ctk.CTkImage]:
    """
    Carrega uma imagem do disco e a converte em um `CTkImage` no
    tamanho solicitado, pronta para ser usada em `CTkLabel` ou
    `CTkButton`. Retorna None silenciosamente caso a imagem não
    exista ou o Pillow não esteja disponível, garantindo que a
    ausência de um asset visual nunca derrube a aplicação.
    """
    if not _PIL_AVAILABLE:
        return None
    try:
        pil_image = Image.open(path).convert("RGBA")
        return ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=size)
    except Exception:  # pragma: no cover
        logger.exception("Falha ao carregar imagem '%s' como CTkImage.", path)
        return None


# ===========================================================================
# SmoothProgress — animação suave de barra de progresso
# ===========================================================================

class SmoothProgress:
    """
    Encapsula um `CTkProgressBar`, animando suavemente a transição
    entre o valor atualmente exibido e um novo valor-alvo, em vez de
    saltar instantaneamente — tornando a barra de progresso
    visualmente mais fluida durante a geração de arquivos.
    """

    def __init__(self, progress_bar: ctk.CTkProgressBar, steps: int = 10, interval_ms: int = 14):
        self._bar = progress_bar
        self._steps = max(1, steps)
        self._interval_ms = interval_ms
        self._current = 0.0
        self._after_id: Optional[str] = None

    def set_immediate(self, value: float) -> None:
        """Define o valor instantaneamente, sem animação (ex.: reset)."""
        self._cancel_pending()
        value = max(0.0, min(1.0, value))
        self._current = value
        self._bar.set(value)

    def animate_to(self, target: float) -> None:
        """Anima suavemente da posição atual até o valor `target` (0.0 a 1.0)."""
        target = max(0.0, min(1.0, target))
        self._cancel_pending()

        start = self._current
        delta = (target - start) / self._steps

        def _step(i: int = 0, value: float = start) -> None:
            next_value = target if i >= self._steps - 1 else value + delta
            try:
                self._bar.set(next_value)
            except Exception:  # pragma: no cover - widget pode já ter sido destruído
                return
            self._current = next_value
            if i < self._steps - 1:
                self._after_id = self._bar.after(self._interval_ms, lambda: _step(i + 1, next_value))
            else:
                self._after_id = None

        _step()

    def _cancel_pending(self) -> None:
        if self._after_id is not None:
            try:
                self._bar.after_cancel(self._after_id)
            except Exception:  # pragma: no cover
                pass
            self._after_id = None


# ===========================================================================
# Pequenas animações de interação (pulso, slide-in, flash de cor)
# ===========================================================================

def pulse_label(label: ctk.CTkLabel, base_size: int, peak_size: int, weight: str = "bold") -> None:
    """
    Aplica uma pequena animação de "pulso" (efeito de bounce) à
    fonte de um `CTkLabel`, aumentando e depois retornando ao
    tamanho original — usado como feedback visual de clique (ex.:
    easter egg de créditos).
    """
    sequence = [base_size, base_size + (peak_size - base_size) // 2, peak_size,
                base_size + (peak_size - base_size) // 2, base_size]

    def _step(i: int = 0) -> None:
        if i >= len(sequence):
            return
        try:
            label.configure(font=ctk.CTkFont(size=sequence[i], weight=weight))
        except Exception:  # pragma: no cover
            return
        label.after(45, lambda: _step(i + 1))

    _step()


def slide_in_vertical(widget, steps: int = 10, start_offset: int = 70, interval_ms: int = 14) -> None:
    """
    Aplica um efeito de "entrada deslizante" (slide-in) a um widget
    já posicionado via `grid()`, animando o espaçamento vertical
    (`pady`) de um valor inicial elevado até zero, criando a
    sensação de o painel "deslizar" suavemente para sua posição
    final. Útil para revelar painéis dinamicamente (ex.: easter
    eggs, mensagens de sucesso).
    """
    try:
        grid_info = widget.grid_info()
    except Exception:  # pragma: no cover
        return

    if not grid_info:
        return

    def _step(i: int = 0) -> None:
        if i >= steps:
            widget.grid_configure(pady=(0, 10))
            return
        fraction = 1.0 - (i / steps)
        current_pad = int(start_offset * fraction)
        try:
            widget.grid_configure(pady=(current_pad, max(0, 10 - current_pad // 4)))
        except Exception:  # pragma: no cover
            return
        widget.after(interval_ms, lambda: _step(i + 1))

    _step()


def flash_widget_color(
    widget,
    flash_color: str,
    original_color,
    duration_ms: int = 220,
) -> None:
    """
    Pisca rapidamente a cor de preenchimento (`fg_color`) de um
    widget CustomTkinter (ex.: um botão) para `flash_color` e, após
    `duration_ms`, retorna à cor original — usado como confirmação
    visual sutil de uma ação concluída com sucesso, sem alterar
    nenhum comportamento funcional do widget.
    """
    try:
        widget.configure(fg_color=flash_color)
    except Exception:  # pragma: no cover
        return

    def _restore() -> None:
        try:
            widget.configure(fg_color=original_color)
        except Exception:  # pragma: no cover
            pass

    widget.after(duration_ms, _restore)


def animate_dots_cycle(
    label: ctk.CTkLabel,
    base_text: str,
    cancel_flag: Callable[[], bool],
    interval_ms: int = 350,
) -> None:
    """
    Anima um sufixo de pontos cíclico ("", ".", "..", "...") em um
    `CTkLabel`, criando um efeito simples e leve de "carregando...".
    A animação para automaticamente quando `cancel_flag()` retornar
    True, evitando vazamento de callbacks `after()` após o widget
    ser destruído ou a tela trocada.
    """
    frames = ["", ".", "..", "..."]

    def _step(i: int = 0) -> None:
        if cancel_flag():
            return
        try:
            label.configure(text=f"{base_text}{frames[i % len(frames)]}")
        except Exception:  # pragma: no cover
            return
        label.after(interval_ms, lambda: _step(i + 1))

    _step()
