"""
gui/tab_credits.py
----------------------

Aba 'Créditos' da aplicação ByteForge.

Contém um "Easter Egg": ao clicar na logomarca oficial, uma pequena
animação de "pulso" é disparada e um painel detalhado de créditos é
revelado com um efeito de entrada deslizante (slide-in), atribuindo
o crédito total da criação do software ao desenvolvedor identificado
publicamente como "DhaaankMK".

Esta versão da aba substitui o antigo placeholder textual ("🛠️
ByteForge") pela logomarca oficial do projeto, exibida sobre um
cabeçalho com o gradiente característico da marca, tornando a tela
visualmente consistente com a identidade do ByteForge.

Nota de privacidade
--------------------
Por solicitação explícita do autor do projeto, o nome civil do
desenvolvedor é informação privada e NUNCA é exibido pelo software.
Em qualquer tela, log, metadado interno do arquivo ou painel de
créditos, a identidade exibida é exclusivamente o pseudônimo público
"DhaaankMK".
"""

from __future__ import annotations

import customtkinter as ctk

from gui import theme
from gui.widgets import GradientBanner, load_ctk_image, pulse_label, slide_in_vertical

AUTHOR_PUBLIC_NAME = "DhaaankMK"

LOGO_BASE_SIZE = 96
LOGO_PEAK_SIZE = 108


class CreditsTab(ctk.CTkFrame):
    """Frame correspondente à aba 'Créditos' do TabView principal."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._egg_revealed = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_widgets()

    def _build_widgets(self) -> None:
        # Cabeçalho decorativo com o gradiente oficial da marca,
        # reforçando a identidade visual também dentro da aba.
        header = GradientBanner(self, height=70, show_logo=False, highlightthickness=0)
        header.grid(row=0, column=0, sticky="ew")
        header.update_texts(
            title="Créditos & Identidade",
            subtitle="A história e a autoria por trás do ByteForge",
        )

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=1, column=0, pady=(40, 20))
        container.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Logomarca oficial, clicável — substitui o antigo placeholder
        # textual por uma imagem real, com cursor de "mão" indicando
        # que é interativa.
        logo_image = load_ctk_image(theme.LOGO_PATH, size=(LOGO_BASE_SIZE, LOGO_BASE_SIZE))
        self.logo_label = ctk.CTkLabel(
            container, text="" if logo_image else "🛠️ ByteForge",
            image=logo_image,
            font=ctk.CTkFont(size=34, weight="bold"),
            cursor="hand2",
        )
        self.logo_label.grid(row=0, column=0, pady=(0, 10))
        self.logo_label.bind("<Button-1>", self._on_logo_clicked)

        self.app_name_label = ctk.CTkLabel(
            container, text="ByteForge", font=ctk.CTkFont(size=24, weight="bold"),
            cursor="hand2", text_color=theme.TEXT_PRIMARY,
        )
        self.app_name_label.grid(row=1, column=0, pady=(0, 4))
        self.app_name_label.bind("<Button-1>", self._on_logo_clicked)

        self.hint_label = ctk.CTkLabel(
            container,
            text="Gerador profissional de arquivos de preenchimento",
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray70"),
        )
        self.hint_label.grid(row=2, column=0, pady=(0, 30))

        # Painel de créditos, inicialmente oculto. É revelado/escondido
        # através do clique repetido na logo/título acima, com efeito
        # de entrada deslizante (slide-in) a cada revelação.
        self.credits_panel = ctk.CTkFrame(
            container, corner_radius=18, border_width=1, border_color=theme.ACCENT_SOFT,
        )
        self.credits_panel.grid(row=3, column=0, padx=20)
        self.credits_panel.grid_remove()  # começa escondido

        ctk.CTkLabel(
            self.credits_panel, text="✨ Créditos Especiais ✨",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, padx=40, pady=(25, 5))

        ctk.CTkLabel(
            self.credits_panel,
            text="Idealização, desenvolvimento e arquitetura completa do ByteForge:",
            font=ctk.CTkFont(size=13), text_color=("gray40", "gray70"),
        ).grid(row=1, column=0, padx=40, pady=(0, 5))

        ctk.CTkLabel(
            self.credits_panel, text=AUTHOR_PUBLIC_NAME,
            font=ctk.CTkFont(size=26, weight="bold"), text_color=theme.ACCENT_HOVER,
        ).grid(row=2, column=0, padx=40, pady=(0, 5))

        ctk.CTkLabel(
            self.credits_panel,
            text="Todos os direitos de criação e crédito técnico deste software pertencem a DhaaankMK.",
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color=("gray40", "gray70"), wraplength=380, justify="center",
        ).grid(row=3, column=0, padx=40, pady=(0, 10))

        ctk.CTkLabel(
            self.credits_panel,
            text="Construído com Python, CustomTkinter, threading e muita atenção a detalhes de segurança.",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"), wraplength=380, justify="center",
        ).grid(row=4, column=0, padx=40, pady=(0, 25))

        self.toggle_hint = ctk.CTkLabel(
            container, text="💡 Clique na logo para ver os créditos",
            font=ctk.CTkFont(size=11), text_color=("gray50", "gray60"),
        )
        self.toggle_hint.grid(row=4, column=0, pady=(15, 0))

    def _on_logo_clicked(self, _event=None) -> None:
        # Pequeno efeito de "pulso" na logo a cada clique, dando
        # feedback visual imediato de que a interação foi registrada.
        pulse_label(self.app_name_label, base_size=24, peak_size=30)

        self._egg_revealed = not self._egg_revealed
        if self._egg_revealed:
            self.credits_panel.grid()
            slide_in_vertical(self.credits_panel, steps=12, start_offset=60, interval_ms=12)
            self.toggle_hint.configure(text="💡 Clique na logo novamente para ocultar os créditos")
        else:
            self.credits_panel.grid_remove()
            self.toggle_hint.configure(text="💡 Clique na logo para ver os créditos")
