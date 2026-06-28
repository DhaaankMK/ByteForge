"""
gui/tab_manager.py
----------------------

Aba 'Gerenciador' da aplicação ByteForge.

Permite ao usuário visualizar, abrir, editar (redimensionar) e
excluir todos os arquivos já gerados pelo ByteForge, mesmo que o
arquivo tenha sido movido ou apagado manualmente fora do aplicativo
(nesse caso, é exibido com o status "Ausente").

Também exibe estatísticas gerais:
    * Total de arquivos já criados historicamente pelo ByteForge.
    * Total de arquivos atualmente registrados (ativos).
"""

from __future__ import annotations

import os
import logging
import subprocess
import sys
from tkinter import messagebox

import customtkinter as ctk

from core import file_registry
from core.disk_utils import format_bytes
from core.settings_manager import AppSettings
from gui.dialog_resize import ResizeDialog
from gui import theme
from gui.widgets import GradientBanner

logger = logging.getLogger("ByteForge.gui.manager")


class ManagerTab(ctk.CTkFrame):
    """Frame correspondente à aba 'Gerenciador' do TabView principal."""

    def __init__(self, master, settings_provider, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.settings_provider = settings_provider

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        banner = GradientBanner(self, height=70, show_logo=False, highlightthickness=0)
        banner.grid(row=0, column=0, sticky="ew")
        banner.update_texts(
            title="Gerenciador de Arquivos",
            subtitle="Acompanhe, edite e gerencie tudo o que o ByteForge já criou",
        )

        self._build_header()
        self._build_list_container()
        self.refresh()

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=20, pady=(15, 5))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Arquivos Registrados", font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            actions, text="🔄 Atualizar", width=110, fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER, command=self.refresh,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            actions, text="🧹 Limpar Ausentes", width=140, command=self._on_purge_missing
        ).pack(side="left")

        self.stats_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=12), text_color=("gray40", "gray70"),
        )
        self.stats_label.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 10))

    def _build_list_container(self) -> None:
        self.list_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_container.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.list_container.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Atualização de dados
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        for widget in self.list_container.winfo_children():
            widget.destroy()

        entries = file_registry.list_entries()
        lifetime_total = file_registry.get_lifetime_total_created()

        self.stats_label.configure(
            text=(
                f"📊 Total de arquivos já criados pelo ByteForge: {lifetime_total}  |  "
                f"Atualmente registrados: {len(entries)}"
            )
        )

        if not entries:
            empty_label = ctk.CTkLabel(
                self.list_container,
                text="Nenhum arquivo registrado ainda. Gere um arquivo na aba 'Home' "
                     "para vê-lo listado aqui.",
                text_color=("gray40", "gray70"),
            )
            empty_label.grid(row=0, column=0, pady=40)
            return

        # Lista os mais recentes primeiro.
        for index, entry in enumerate(reversed(entries)):
            self._render_entry_card(entry, row=index)

    def _render_entry_card(self, entry: file_registry.FileEntry, row: int) -> None:
        exists = entry.exists_on_disk()
        actual_size = entry.actual_size_on_disk() if exists else None

        card = ctk.CTkFrame(self.list_container)
        card.grid(row=row, column=0, sticky="ew", pady=6)
        card.grid_columnconfigure(1, weight=1)

        status_icon = "✅" if exists else "⚠️"
        ctk.CTkLabel(card, text=status_icon, font=ctk.CTkFont(size=22)).grid(
            row=0, column=0, rowspan=3, padx=15, pady=10
        )

        ctk.CTkLabel(
            card, text=os.path.basename(entry.path), font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(0, 10), pady=(10, 0))

        size_text = format_bytes(entry.size_bytes)
        if exists and actual_size is not None and actual_size != entry.size_bytes:
            size_text += f"  (tamanho real em disco: {format_bytes(actual_size)})"

        status_text = "Disponível" if exists else "Ausente — o arquivo não foi encontrado no disco"

        ctk.CTkLabel(
            card, text=f"{size_text}  •  {status_text}",
            anchor="w", text_color=("gray40", "gray70"), font=ctk.CTkFont(size=12),
        ).grid(row=1, column=1, sticky="w", padx=(0, 10))

        created_display = entry.created_at_utc.split("T")[0] if "T" in entry.created_at_utc else entry.created_at_utc
        ctk.CTkLabel(
            card, text=f"Criado em: {created_display}  •  Caminho: {entry.path}",
            anchor="w", text_color=("gray50", "gray60"), font=ctk.CTkFont(size=10), wraplength=520,
        ).grid(row=2, column=1, sticky="w", padx=(0, 10), pady=(0, 10))

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=0, column=2, rowspan=3, padx=15)

        ctk.CTkButton(
            buttons, text="📂 Abrir pasta", width=120,
            state="normal" if exists else "disabled",
            command=lambda e=entry: self._on_open_folder(e),
        ).pack(pady=(0, 6))

        ctk.CTkButton(
            buttons, text="✏️ Editar tamanho", width=120,
            state="normal" if exists else "disabled",
            command=lambda e=entry: self._on_edit_size(e),
        ).pack(pady=(0, 6))

        ctk.CTkButton(
            buttons, text="🗑️ Excluir", width=120, fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            command=lambda e=entry: self._on_delete(e),
        ).pack()

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------

    def _on_open_folder(self, entry: file_registry.FileEntry) -> None:
        folder = os.path.dirname(entry.path)
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as exc:
            logger.exception("Falha ao abrir a pasta '%s': %s", folder, exc)
            messagebox.showerror("ByteForge", f"Não foi possível abrir a pasta:\n{exc}")

    def _on_edit_size(self, entry: file_registry.FileEntry) -> None:
        settings: AppSettings = self.settings_provider()

        def on_success(new_size_bytes: int) -> None:
            file_registry.update_entry_after_resize(entry.id, new_size_bytes)
            self.refresh()

        ResizeDialog(
            self, file_path=entry.path, current_size_bytes=entry.size_bytes,
            settings=settings, on_success=on_success,
        )

    def _on_delete(self, entry: file_registry.FileEntry) -> None:
        settings: AppSettings = self.settings_provider()

        if settings.confirm_before_delete:
            confirm = messagebox.askyesno(
                "ByteForge",
                f"Tem certeza de que deseja excluir permanentemente o arquivo:\n\n"
                f"{entry.path}\n\nEsta ação não pode ser desfeita.",
            )
            if not confirm:
                return

        try:
            file_registry.remove_entry(entry.id, delete_file_from_disk=True)
        except OSError as exc:
            messagebox.showerror("ByteForge", f"Erro ao excluir o arquivo:\n{exc}")
        finally:
            self.refresh()

    def _on_purge_missing(self) -> None:
        removed = file_registry.purge_missing_entries()
        self.refresh()
        messagebox.showinfo(
            "ByteForge",
            f"{removed} entrada(s) ausente(s) removida(s) do registro."
            if removed else "Nenhuma entrada ausente foi encontrada."
        )
