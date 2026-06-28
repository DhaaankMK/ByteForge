"""
gui/dialog_terms.py
-----------------------

Janela modal (`CTkToplevel`) que exibe o Termo de Responsabilidade
do ByteForge na primeira execução do aplicativo. O usuário só pode
prosseguir para a janela principal após:

    1. Ler o texto do termo (rolável, dentro de uma caixa de texto).
    2. Marcar explicitamente a caixa de confirmação "Li e concordo
       com os termos acima".
    3. Clicar no botão "Concordar e Continuar" (desabilitado até que
       a caixa esteja marcada).

Caso o usuário feche a janela sem aceitar (ou clique em "Recusar e
Sair"), a aplicação é encerrada imediatamente, já que o uso do
ByteForge sem o aceite do termo não é permitido.

Este diálogo é modal (`grab_set`) e bloqueia qualquer interação com
a janela principal até que uma decisão seja tomada.
"""

from __future__ import annotations

import logging
from typing import Callable

import customtkinter as ctk

from core.terms_manager import TERMS_TEXT, TERMS_VERSION, register_acceptance
from gui import theme

logger = logging.getLogger("ByteForge.gui.terms")


class TermsDialog(ctk.CTkToplevel):
    """Janela modal de aceite do Termo de Responsabilidade."""

    def __init__(self, master, on_accept: Callable[[], None], on_decline: Callable[[], None]):
        super().__init__(master)
        self._on_accept = on_accept
        self._on_decline = on_decline

        self.title("ByteForge — Termo de Responsabilidade")
        self.geometry("620x560")
        self.minsize(560, 480)
        self.resizable(True, True)

        # Impede que a janela principal receba foco/eventos enquanto
        # este diálogo estiver aberto (comportamento modal).
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._handle_decline)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_widgets()

        # Centraliza a janela em relação à janela principal.
        self.after(10, self._center_on_parent)

    def _center_on_parent(self) -> None:
        try:
            self.update_idletasks()
            parent_x = self.master.winfo_x()
            parent_y = self.master.winfo_y()
            parent_w = self.master.winfo_width()
            parent_h = self.master.winfo_height()
            w, h = self.winfo_width(), self.winfo_height()
            x = parent_x + (parent_w - w) // 2
            y = parent_y + (parent_h - h) // 2
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except Exception:  # pragma: no cover
            pass

    def _build_widgets(self) -> None:
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header_frame.grid_columnconfigure(1, weight=1)

        from gui.widgets import load_ctk_image
        logo_image = load_ctk_image(theme.LOGO_PATH, size=(40, 40))
        if logo_image is not None:
            ctk.CTkLabel(header_frame, image=logo_image, text="").grid(row=0, column=0, padx=(0, 12))

        ctk.CTkLabel(
            header_frame, text="⚠️  Termo de Responsabilidade",
            font=ctk.CTkFont(size=20, weight="bold"), text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=1, sticky="w")

        text_box = ctk.CTkTextbox(self, wrap="word")
        text_box.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        text_box.insert("1.0", TERMS_TEXT)
        text_box.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        footer.grid_columnconfigure(0, weight=1)

        self._agree_var = ctk.BooleanVar(value=False)
        self.agree_checkbox = ctk.CTkCheckBox(
            footer,
            text="Li e concordo integralmente com o Termo de Responsabilidade acima.",
            variable=self._agree_var,
            command=self._on_checkbox_toggled,
        )
        self.agree_checkbox.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))

        self.decline_btn = ctk.CTkButton(
            footer, text="Recusar e Sair", width=150,
            fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            command=self._handle_decline,
        )
        self.decline_btn.grid(row=1, column=0, sticky="w")

        self.accept_btn = ctk.CTkButton(
            footer, text="Concordar e Continuar", width=200, state="disabled",
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            command=self._handle_accept,
        )
        self.accept_btn.grid(row=1, column=1, sticky="e")

        version_label = ctk.CTkLabel(
            footer, text=f"Versão do termo: {TERMS_VERSION}",
            font=ctk.CTkFont(size=10), text_color=("gray50", "gray60"),
        )
        version_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _on_checkbox_toggled(self) -> None:
        self.accept_btn.configure(state="normal" if self._agree_var.get() else "disabled")

    def _handle_accept(self) -> None:
        if not self._agree_var.get():
            return
        try:
            register_acceptance()
        except Exception:
            logger.exception("Falha ao registrar o aceite do Termo de Responsabilidade.")
        self.grab_release()
        self.destroy()
        self._on_accept()

    def _handle_decline(self) -> None:
        logger.info("Usuário recusou o Termo de Responsabilidade. Encerrando a aplicação.")
        self.grab_release()
        self.destroy()
        self._on_decline()
