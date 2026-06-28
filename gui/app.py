"""
gui/app.py
-------------

Janela principal da aplicação ByteForge, construída com
`customtkinter`. Organiza a interface em cinco abas (Home, Plugins,
Gerenciador, Créditos e Configurações) através de um `CTkTabview`.

Fluxo de inicialização:
    1. As configurações persistidas (`data/config.json`) são
       carregadas através de `core.settings_manager`.
    2. O tema visual (aparência + paleta de cores) é aplicado de
       acordo com as configurações carregadas.
    3. Caso o usuário ainda não tenha aceitado a versão atual do
       Termo de Responsabilidade, a janela principal é exibida em
       estado bloqueado (abas desabilitadas) e o diálogo modal
       `TermsDialog` é apresentado por cima. O uso do aplicativo só
       é liberado após o aceite explícito.
"""

from __future__ import annotations

import logging
import customtkinter as ctk

from gui.tab_home import HomeTab
from gui.tab_plugins import PluginsTab
from gui.tab_manager import ManagerTab
from gui.tab_credits import CreditsTab
from gui.tab_settings import SettingsTab
from gui.dialog_terms import TermsDialog
from gui.widgets import GradientBanner, load_ctk_image
from gui import theme

from core.settings_manager import AppSettings, load_settings, save_settings
from core.terms_manager import has_accepted_current_terms

logger = logging.getLogger("ByteForge.gui.app")

APP_TITLE = "ByteForge — Gerador Profissional de Arquivos Dummy"
APP_MIN_WIDTH = 820
APP_MIN_HEIGHT = 720


class ByteForgeApp(ctk.CTk):
    """Janela raiz da aplicação ByteForge."""

    def __init__(self) -> None:
        super().__init__()

        # As configurações são carregadas do disco (ou criadas com
        # valores padrão seguros, caso seja a primeira execução).
        self._settings: AppSettings = load_settings()

        ctk.set_appearance_mode(self._settings.appearance_mode)
        ctk.set_default_color_theme(self._settings.color_theme)

        self.title(APP_TITLE)
        self.geometry(f"{APP_MIN_WIDTH}x{APP_MIN_HEIGHT}")
        self.minsize(APP_MIN_WIDTH, APP_MIN_HEIGHT)
        self._apply_window_icon()

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.banner = GradientBanner(
            self, height=92,
            title="ByteForge",
            subtitle="Gerador Profissional de Arquivos Dummy  •  por DhaaankMK",
            show_logo=True, logo_size=56,
        )
        self.banner.grid(row=0, column=0, sticky="ew")

        self.tabview = ctk.CTkTabview(self, anchor="nw")
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=(8, 10))

        self.tab_home = self.tabview.add("🏠 Home")
        self.tab_plugins = self.tabview.add("🧩 Plugins")
        self.tab_manager = self.tabview.add("🗂️ Gerenciador")
        self.tab_credits = self.tabview.add("🎖️ Créditos")
        self.tab_settings = self.tabview.add("⚙️ Configurações")

        for tab in (
            self.tab_home, self.tab_plugins, self.tab_manager,
            self.tab_credits, self.tab_settings,
        ):
            tab.grid_rowconfigure(0, weight=1)
            tab.grid_columnconfigure(0, weight=1)

        self._home_tab = HomeTab(self.tab_home, settings_provider=self._get_settings)
        self._home_tab.grid(row=0, column=0, sticky="nsew")

        self._plugins_tab = PluginsTab(self.tab_plugins)
        self._plugins_tab.grid(row=0, column=0, sticky="nsew")

        self._manager_tab = ManagerTab(self.tab_manager, settings_provider=self._get_settings)
        self._manager_tab.grid(row=0, column=0, sticky="nsew")

        self._credits_tab = CreditsTab(self.tab_credits)
        self._credits_tab.grid(row=0, column=0, sticky="nsew")

        self._settings_tab = SettingsTab(
            self.tab_settings, settings=self._settings, on_change=self._on_settings_changed
        )
        self._settings_tab.grid(row=0, column=0, sticky="nsew")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # O Termo de Responsabilidade é verificado por último, após
        # toda a interface principal já estar construída — assim, o
        # diálogo modal aparece sobre uma janela principal completa
        # (porém bloqueada para interação até o aceite).
        self.after(150, self._enforce_terms_acceptance)

    # ------------------------------------------------------------------
    # Identidade visual
    # ------------------------------------------------------------------

    def _apply_window_icon(self) -> None:
        """
        Define a logomarca oficial do ByteForge como ícone da janela
        (barra de título/taskbar), quando disponível. Falhas ao
        carregar o ícone são silenciosamente ignoradas, já que essa é
        uma melhoria puramente cosmética e nunca deve impedir a
        aplicação de abrir.
        """
        try:
            from PIL import Image, ImageTk
            if theme.LOGO_PATH.exists():
                icon_image = Image.open(theme.LOGO_PATH).convert("RGBA")
                self._icon_photo = ImageTk.PhotoImage(icon_image)
                self.iconphoto(True, self._icon_photo)
        except Exception:  # pragma: no cover
            logger.debug("Não foi possível aplicar o ícone da janela do ByteForge.", exc_info=True)

    # ------------------------------------------------------------------
    # Termo de Responsabilidade
    # ------------------------------------------------------------------

    def _enforce_terms_acceptance(self) -> None:
        if has_accepted_current_terms():
            return

        logger.info("Termo de Responsabilidade ainda não aceito. Exibindo diálogo de aceite.")
        self.tabview.configure(state="disabled")
        TermsDialog(
            self,
            on_accept=self._on_terms_accepted,
            on_decline=self._on_terms_declined,
        )

    def _on_terms_accepted(self) -> None:
        logger.info("Termo de Responsabilidade aceito. Liberando o uso do ByteForge.")
        self.tabview.configure(state="normal")

    def _on_terms_declined(self) -> None:
        logger.info("Usuário recusou o Termo de Responsabilidade. Encerrando a aplicação.")
        self.destroy()

    # ------------------------------------------------------------------
    # Configurações compartilhadas
    # ------------------------------------------------------------------

    def _get_settings(self) -> AppSettings:
        """Fornece a instância atual de configurações para outras abas."""
        return self._settings

    def _on_settings_changed(self, new_settings: AppSettings) -> None:
        logger.info("Configurações atualizadas pelo usuário.")
        self._settings = new_settings
        try:
            save_settings(self._settings)
        except Exception:
            logger.exception("Falha ao persistir as configurações atualizadas.")

    # ------------------------------------------------------------------
    # Encerramento
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        """
        Garante um encerramento limpo da aplicação. Threads de
        geração de arquivo são daemon threads, portanto não impedem
        o encerramento do processo principal.
        """
        logger.info("Encerrando a janela principal do ByteForge.")
        self.destroy()
