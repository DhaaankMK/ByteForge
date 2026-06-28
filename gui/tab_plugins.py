"""
gui/tab_plugins.py
---------------------

Aba 'Plugins' da aplicação ByteForge.

Comportamento:
    * Ao ser exibida, varre a pasta `/plugins` em busca de scripts
      `.py` válidos usando `core.plugin_manager`.
    * Se algum plugin for encontrado, lista cada um com nome,
      descrição e um botão de execução.
    * Se NENHUM plugin for encontrado (caso padrão de uma instalação
      nova), exibe uma mensagem elegante "Loja de Plugins: Em breve",
      acompanhada de uma animação de spinner (carregamento) contínua,
      reforçando a sensação de que a funcionalidade está "a
      caminho" em vez de simplesmente ausente.
    * Em paralelo (em uma thread separada, para não bloquear a UI),
      tenta verificar a conectividade com o servidor remoto de
      plugins através de `core.network_utils`, exibindo o resultado
      dessa verificação como um pequeno indicador de status.
"""

from __future__ import annotations

import threading
import logging
from typing import List

import customtkinter as ctk

from core.plugin_manager import discover_plugins, run_plugin, PluginInfo
from core.network_utils import check_plugin_store_connection
from gui import theme

logger = logging.getLogger("ByteForge.gui.plugins")


class _Spinner(ctk.CTkLabel):
    """
    Pequeno widget de animação "spinner" baseado em rotação de
    caracteres ASCII/Unicode, atualizado periodicamente via
    `after()`. Evita dependências externas de GIFs ou imagens para
    uma simples animação de carregamento.
    """

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, master, **kwargs):
        super().__init__(
            master, text=self.FRAMES[0], font=ctk.CTkFont(size=32),
            text_color=theme.ACCENT_HOVER, **kwargs,
        )
        self._frame_index = 0
        self._running = False
        self._after_id = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._animate()

    def stop(self) -> None:
        self._running = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _animate(self) -> None:
        if not self._running:
            return
        self._frame_index = (self._frame_index + 1) % len(self.FRAMES)
        self.configure(text=self.FRAMES[self._frame_index])
        self._after_id = self.after(90, self._animate)


class PluginsTab(ctk.CTkFrame):
    """Frame correspondente à aba 'Plugins' do TabView principal."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        from gui.widgets import GradientBanner
        banner = GradientBanner(self, height=70, show_logo=False, highlightthickness=0)
        banner.grid(row=0, column=0, sticky="ew")
        banner.update_texts(
            title="Loja de Plugins",
            subtitle="Extensões e integrações para expandir o ByteForge",
        )

        self._build_header()
        self._content_container = ctk.CTkFrame(self, fg_color="transparent")
        self._content_container.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        self._content_container.grid_columnconfigure(0, weight=1)

        self._spinner: ctk.CTkBaseClass | None = None
        self._refresh_plugins()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=20, pady=(15, 0))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Plugins instalados", font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        self.status_label = ctk.CTkLabel(
            header, text="Verificando conexão com o servidor...",
            font=ctk.CTkFont(size=12), text_color=("gray40", "gray70"),
            anchor="w", justify="left", wraplength=560,
        )
        self.status_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        refresh_btn = ctk.CTkButton(
            header, text="🔄 Atualizar", width=110, fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER, command=self._refresh_plugins,
        )
        refresh_btn.grid(row=0, column=1, rowspan=2, sticky="ne")

    # ------------------------------------------------------------------
    # Lógica de descoberta de plugins e verificação de rede
    # ------------------------------------------------------------------

    def _refresh_plugins(self) -> None:
        for widget in self._content_container.winfo_children():
            widget.destroy()

        plugins = discover_plugins()

        if plugins:
            self._render_plugin_list(plugins)
        else:
            self._render_coming_soon_panel()

        # A verificação de conectividade é feita em segundo plano,
        # pois pode levar até o tempo configurado de timeout (alguns
        # segundos) e não deve travar a renderização da aba.
        threading.Thread(target=self._check_connectivity_async, daemon=True).start()

    def _render_plugin_list(self, plugins: List[PluginInfo]) -> None:
        for index, plugin in enumerate(plugins):
            card = ctk.CTkFrame(self._content_container)
            card.grid(row=index, column=0, sticky="ew", pady=6)
            card.grid_columnconfigure(1, weight=1)

            icon_text = "✅" if plugin.valid else "⚠️"
            ctk.CTkLabel(card, text=icon_text, font=ctk.CTkFont(size=20)).grid(
                row=0, column=0, rowspan=2, padx=15, pady=10
            )

            ctk.CTkLabel(
                card, text=plugin.name, font=ctk.CTkFont(size=15, weight="bold"), anchor="w"
            ).grid(row=0, column=1, sticky="w", padx=(0, 10), pady=(10, 0))

            description = plugin.description if plugin.valid else (plugin.error_message or "Plugin inválido.")
            ctk.CTkLabel(
                card, text=description, anchor="w", justify="left",
                text_color=("gray40", "gray70"), wraplength=480,
            ).grid(row=1, column=1, sticky="w", padx=(0, 10), pady=(0, 10))

            run_btn = ctk.CTkButton(
                card, text="Executar", width=100, state="normal" if plugin.valid else "disabled",
                fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                command=lambda p=plugin: self._on_run_plugin(p),
            )
            run_btn.grid(row=0, column=2, rowspan=2, padx=15)

    def _render_coming_soon_panel(self) -> None:
        panel = ctk.CTkFrame(
            self._content_container, corner_radius=16,
            border_width=1, border_color=theme.ACCENT_SOFT,
        )
        panel.grid(row=0, column=0, sticky="nsew", pady=40)
        panel.grid_columnconfigure(0, weight=1)
        self._content_container.grid_rowconfigure(0, weight=1)

        self._spinner = _Spinner(panel)
        self._spinner.grid(row=0, column=0, pady=(50, 15))
        self._spinner.start()

        ctk.CTkLabel(
            panel, text="Loja de Plugins: Em breve",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=1, column=0, pady=(0, 8))

        ctk.CTkLabel(
            panel,
            text=(
                "Estamos preparando uma central de extensões para o ByteForge.\n"
                "Em breve você poderá instalar plugins diretamente por aqui.\n\n"
                "Quer testar agora? Adicione um arquivo .py na pasta 'plugins/' "
                "do projeto seguindo a convenção descrita na documentação."
            ),
            justify="center", text_color=("gray40", "gray70"), wraplength=480,
        ).grid(row=2, column=0, padx=40, pady=(0, 50))

    def _on_run_plugin(self, plugin: PluginInfo) -> None:
        from tkinter import messagebox
        result = run_plugin(plugin)
        messagebox.showinfo(f"ByteForge — {plugin.name}", result or "Execução concluída.")

    def _check_connectivity_async(self) -> None:
        result = check_plugin_store_connection()
        self.after(0, self._apply_connectivity_status, result)

    def _apply_connectivity_status(self, result) -> None:
        prefix = "🟢" if result.success else "🟡"
        self.status_label.configure(text=f"{prefix} {result.message}")
