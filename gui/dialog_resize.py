"""
gui/dialog_resize.py
------------------------

Janela modal utilizada pelo Gerenciador de Arquivos para editar o
tamanho de um arquivo já gerado pelo ByteForge. A operação consiste
em regenerar completamente o conteúdo do arquivo (novos dados
pseudoaleatórios + marca d'água) no mesmo caminho, com o novo
tamanho solicitado.

A regeneração ocorre em uma thread separada (`FileGeneratorWorker`),
com uma barra de progresso própria, reaproveitando toda a lógica de
segurança (verificação de espaço em disco) e marca d'água já
existente em `core.file_generator`.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import customtkinter as ctk
from tkinter import messagebox

from core.disk_utils import format_bytes
from core.file_generator import (
    FileGeneratorWorker,
    GenerationConfig,
    GenerationProgress,
    parse_size_to_bytes,
)
from core.settings_manager import AppSettings
from gui import theme

logger = logging.getLogger("ByteForge.gui.resize")


class ResizeDialog(ctk.CTkToplevel):
    """Janela modal para editar o tamanho de um arquivo já registrado."""

    SIZE_UNITS = ("MB", "GB", "TB")

    def __init__(
        self,
        master,
        file_path: str,
        current_size_bytes: int,
        settings: AppSettings,
        on_success: Callable[[int], None],
    ):
        super().__init__(master)
        self.file_path = file_path
        self.settings = settings
        self._on_success = on_success
        self._worker: Optional[FileGeneratorWorker] = None

        self.title("ByteForge — Editar Tamanho do Arquivo")
        self.geometry("480x320")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close_attempt)

        self.grid_columnconfigure(0, weight=1)
        self._build_widgets(current_size_bytes)

    def _build_widgets(self, current_size_bytes: int) -> None:
        ctk.CTkLabel(
            self, text="Editar Tamanho do Arquivo",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 5))

        ctk.CTkLabel(
            self, text=self.file_path, wraplength=440, justify="left",
            text_color=("gray40", "gray70"), font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            self, text=f"Tamanho atual: {format_bytes(current_size_bytes)}",
        ).grid(row=2, column=0, sticky="w", padx=20, pady=(0, 15))

        warning = ctk.CTkLabel(
            self,
            text=(
                "⚠️ Esta operação substitui completamente o conteúdo atual do "
                "arquivo por novos dados pseudoaleatórios com marca d'água."
            ),
            text_color=theme.WARNING, wraplength=440, justify="left",
            font=ctk.CTkFont(size=11),
        )
        warning.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 15))

        size_frame = ctk.CTkFrame(self, fg_color="transparent")
        size_frame.grid(row=4, column=0, sticky="w", padx=20)

        ctk.CTkLabel(size_frame, text="Novo tamanho:").pack(side="left", padx=(0, 10))
        self.size_entry = ctk.CTkEntry(size_frame, width=110, placeholder_text="Ex: 200")
        self.size_entry.pack(side="left", padx=(0, 10))
        self.unit_combo = ctk.CTkComboBox(size_frame, values=list(self.SIZE_UNITS), width=90)
        self.unit_combo.set("MB")
        self.unit_combo.pack(side="left")

        self.progress_bar = ctk.CTkProgressBar(self, height=14, progress_color=theme.ACCENT_HOVER)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=5, column=0, sticky="ew", padx=20, pady=(20, 5))

        self.status_label = ctk.CTkLabel(self, text="Aguardando...", font=ctk.CTkFont(size=11))
        self.status_label.grid(row=6, column=0, sticky="w", padx=20)

        buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        buttons_frame.grid(row=7, column=0, sticky="e", padx=20, pady=20)

        self.cancel_btn = ctk.CTkButton(
            buttons_frame, text="Cancelar", width=110, fg_color="gray40",
            hover_color="gray30", command=self._on_close_attempt,
        )
        self.cancel_btn.pack(side="left", padx=(0, 10))

        self.confirm_btn = ctk.CTkButton(
            buttons_frame, text="Aplicar Novo Tamanho", width=180,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            command=self._on_confirm,
        )
        self.confirm_btn.pack(side="left")

    def _on_confirm(self) -> None:
        try:
            value = float(self.size_entry.get().strip().replace(",", "."))
            if value <= 0:
                raise ValueError
            unit = self.unit_combo.get()
            total_bytes = parse_size_to_bytes(value, unit)
        except ValueError:
            messagebox.showwarning("ByteForge", "Informe um tamanho numérico válido e maior que zero.")
            return

        config = GenerationConfig(
            output_path=self.file_path,
            total_size_bytes=total_bytes,
            chunk_size_bytes=self.settings.chunk_size_bytes,
            watermark_interval_bytes=self.settings.watermark_interval_bytes,
            min_free_space_gb=self.settings.effective_min_free_space_gb(),
        )

        self.confirm_btn.configure(state="disabled")
        self.size_entry.configure(state="disabled")
        self.unit_combo.configure(state="disabled")

        self._worker = FileGeneratorWorker(
            config=config,
            on_progress=lambda p: self.after(0, self._apply_progress, p, total_bytes),
            on_log=lambda m: self.after(0, self.status_label.configure, {"text": m}),
        )
        self._worker.start()

    def _apply_progress(self, progress: GenerationProgress, total_bytes: int) -> None:
        self.progress_bar.set(progress.percentage / 100.0)

        if progress.finished:
            self.status_label.configure(text="Arquivo redimensionado com sucesso.")
            self._on_success(total_bytes)
            self.grab_release()
            self.destroy()
        elif progress.error:
            self.status_label.configure(text=f"Erro: {progress.error}")
            messagebox.showerror("ByteForge", progress.error)
            self.confirm_btn.configure(state="normal")
            self.size_entry.configure(state="normal")
            self.unit_combo.configure(state="normal")
        elif progress.cancelled:
            self.status_label.configure(text="Operação cancelada.")
            self.confirm_btn.configure(state="normal")
            self.size_entry.configure(state="normal")
            self.unit_combo.configure(state="normal")
        else:
            self.status_label.configure(
                text=f"Gravando... {progress.speed_mb_s:.2f} MB/s"
            )

    def _on_close_attempt(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            self._worker.request_cancel()
        self.grab_release()
        self.destroy()
