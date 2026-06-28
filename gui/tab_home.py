"""
gui/tab_home.py
------------------

Aba principal ("Home") da aplicação ByteForge. Permite ao usuário:

    * Selecionar o diretório/nome de destino do arquivo dummy.
    * Definir o tamanho do arquivo e a unidade (MB/GB/TB).
    * Iniciar, pausar/retomar e cancelar a geração.
    * Acompanhar o progresso através de uma barra animada,
      velocidade de escrita (MB/s) e tempo estimado restante (ETA).
    * Visualizar um log textual das operações em tempo real.

Toda a comunicação com a thread de geração (`FileGeneratorWorker`)
ocorre através de callbacks que, por sua vez, agendam atualizações
seguras na thread principal da UI usando `after()` do Tkinter — uma
prática essencial, já que widgets Tkinter NÃO são thread-safe e não
devem ser manipulados diretamente a partir de outra thread.
"""

from __future__ import annotations

import os
import logging
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from core.disk_utils import format_bytes
from core.file_generator import (
    FileGeneratorWorker,
    GenerationConfig,
    GenerationProgress,
    parse_size_to_bytes,
    generate_default_filename,
)
from core import file_registry
from gui import theme
from gui.widgets import GradientBanner, SmoothProgress, flash_widget_color, load_ctk_image

logger = logging.getLogger("ByteForge.gui.home")


class HomeTab(ctk.CTkFrame):
    """Frame correspondente à aba 'Home' do TabView principal."""

    SIZE_UNITS = ("MB", "GB", "TB")

    def __init__(self, master, settings_provider, **kwargs):
        """
        Parâmetros
        ----------
        master : widget pai (CTkTabview)
        settings_provider : objeto/callable que expõe as
            configurações atuais definidas na aba 'Configurações'
            (ex.: limite mínimo de espaço livre, tamanho de chunk,
            texto da watermark), permitindo que a aba Home sempre
            utilize os valores mais recentes sem acoplamento direto.
        """
        super().__init__(master, fg_color="transparent", **kwargs)
        self.settings_provider = settings_provider
        self._worker: Optional[FileGeneratorWorker] = None
        self._is_paused: bool = False
        self._pending_output_path: Optional[str] = None
        self._pending_total_bytes: int = 0

        self.grid_columnconfigure(0, weight=1)
        self._build_widgets()

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------

    def _build_widgets(self) -> None:
        header = GradientBanner(self, height=78, show_logo=False, highlightthickness=0)
        header.grid(row=0, column=0, sticky="ew")
        header.update_texts(
            title="Gerador de Arquivos Dummy",
            subtitle="Dados pseudoaleatórios + marca d'água interna para identificação",
        )

        intro_frame = ctk.CTkFrame(self, fg_color="transparent")
        intro_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(15, 5))
        intro_frame.grid_columnconfigure(0, weight=1)

        subtitle = ctk.CTkLabel(
            intro_frame,
            text=(
                "Gere arquivos de preenchimento de qualquer tamanho, com dados\n"
                "pseudoaleatórios e marcas d'água internas para identificação."
            ),
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray70"),
            justify="left",
        )
        subtitle.grid(row=0, column=0, sticky="w")

        illustration = load_ctk_image(theme.COVER_PATH, size=(150, 84))
        if illustration is not None:
            ctk.CTkLabel(
                intro_frame, image=illustration, text="",
                corner_radius=10,
            ).grid(row=0, column=1, sticky="e", padx=(10, 0))

        form_frame = ctk.CTkFrame(self)
        form_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        form_frame.grid_columnconfigure(1, weight=1)

        # --- Linha: Diretório/arquivo de destino ---------------------
        ctk.CTkLabel(form_frame, text="Arquivo de destino:").grid(
            row=0, column=0, sticky="w", padx=15, pady=(15, 5)
        )
        self.path_entry = ctk.CTkEntry(
            form_frame, placeholder_text="Selecione onde salvar o arquivo..."
        )
        self.path_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5), pady=(15, 5))
        self._apply_default_path()

        browse_btn = ctk.CTkButton(
            form_frame, text="Procurar...", width=110, command=self._browse_destination
        )
        browse_btn.grid(row=0, column=2, padx=(0, 15), pady=(15, 5))

        # --- Linha: Tamanho do arquivo ---------------------------------
        ctk.CTkLabel(form_frame, text="Tamanho do arquivo:").grid(
            row=1, column=0, sticky="w", padx=15, pady=5
        )

        size_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        size_frame.grid(row=1, column=1, columnspan=2, sticky="w", padx=(0, 15), pady=5)

        self.size_entry = ctk.CTkEntry(size_frame, width=120, placeholder_text="Ex: 500")
        self.size_entry.insert(0, "500")
        self.size_entry.pack(side="left", padx=(0, 10))

        self.unit_combo = ctk.CTkComboBox(size_frame, values=list(self.SIZE_UNITS), width=90)
        self.unit_combo.set("MB")
        self.unit_combo.pack(side="left")

        # --- Linha: Botões de ação --------------------------------------
        actions_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        actions_frame.grid(row=2, column=0, columnspan=3, sticky="w", padx=15, pady=(10, 15))

        self.generate_btn = ctk.CTkButton(
            actions_frame, text="🚀  Gerar Arquivo", width=160,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            command=self._on_generate_clicked,
        )
        self.generate_btn.pack(side="left", padx=(0, 10))

        self.pause_btn = ctk.CTkButton(
            actions_frame, text="⏸  Pausar", width=110, state="disabled",
            command=self._on_pause_clicked,
        )
        self.pause_btn.pack(side="left", padx=(0, 10))

        self.cancel_btn = ctk.CTkButton(
            actions_frame, text="✖  Cancelar", width=110, state="disabled",
            fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            command=self._on_cancel_clicked,
        )
        self.cancel_btn.pack(side="left")

        # --- Bloco de progresso -----------------------------------------
        progress_frame = ctk.CTkFrame(self)
        progress_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=10)
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(
            progress_frame, height=18, progress_color=theme.ACCENT_HOVER,
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 8))
        self._smooth_progress = SmoothProgress(self.progress_bar, steps=8, interval_ms=12)

        stats_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        stats_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.percentage_label = ctk.CTkLabel(stats_frame, text="0,0%")
        self.percentage_label.grid(row=0, column=0, sticky="w")

        self.speed_label = ctk.CTkLabel(stats_frame, text="Velocidade: -- MB/s")
        self.speed_label.grid(row=0, column=1)

        self.eta_label = ctk.CTkLabel(stats_frame, text="ETA: --")
        self.eta_label.grid(row=0, column=2)

        self.written_label = ctk.CTkLabel(stats_frame, text="0 B / 0 B")
        self.written_label.grid(row=0, column=3, sticky="e")

        # --- Log textual --------------------------------------------------
        log_label = ctk.CTkLabel(self, text="Log de operações:", anchor="w")
        log_label.grid(row=4, column=0, sticky="w", padx=20, pady=(10, 0))

        self.log_box = ctk.CTkTextbox(self, height=160, wrap="word")
        self.log_box.grid(row=5, column=0, sticky="nsew", padx=20, pady=(5, 20))
        self.log_box.configure(state="disabled")
        self.grid_rowconfigure(5, weight=1)

    # ------------------------------------------------------------------
    # Manipuladores de evento (thread principal/UI)
    # ------------------------------------------------------------------

    def _apply_default_path(self) -> None:
        """
        Preenche o campo de destino com um caminho sugerido dentro da
        pasta padrão configurada (por padrão, 'output/' dentro do
        próprio ByteForge), já utilizando um nome de arquivo que
        carrega a marca registrada do software.
        """
        settings = self.settings_provider()
        os.makedirs(settings.output_directory, exist_ok=True)
        suggested_name = generate_default_filename(".bin")
        self.path_entry.insert(0, os.path.join(settings.output_directory, suggested_name))

    def _browse_destination(self) -> None:
        settings = self.settings_provider()
        initial_dir = settings.output_directory if os.path.isdir(settings.output_directory) else os.path.expanduser("~")
        path = filedialog.asksaveasfilename(
            title="Selecione onde salvar o arquivo dummy",
            initialdir=initial_dir,
            initialfile=generate_default_filename(".bin"),
            defaultextension=".bin",
            filetypes=[("Arquivo binário", "*.bin"), ("Todos os arquivos", "*.*")],
        )
        if path:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, path)

    def _on_generate_clicked(self) -> None:
        output_path = self.path_entry.get().strip()
        size_text = self.size_entry.get().strip()
        unit = self.unit_combo.get()

        if not output_path:
            messagebox.showwarning("ByteForge", "Selecione um caminho de destino válido.")
            return

        try:
            size_value = float(size_text.replace(",", "."))
            if size_value <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "ByteForge", "Informe um tamanho numérico válido e maior que zero."
            )
            return

        try:
            total_bytes = parse_size_to_bytes(size_value, unit)
        except ValueError as exc:
            messagebox.showerror("ByteForge", str(exc))
            return

        settings = self.settings_provider()

        config = GenerationConfig(
            output_path=output_path,
            total_size_bytes=total_bytes,
            chunk_size_bytes=settings.chunk_size_bytes,
            watermark_interval_bytes=settings.watermark_interval_bytes,
            min_free_space_gb=settings.effective_min_free_space_gb(),
        )

        if os.path.exists(output_path) and settings.confirm_before_overwrite:
            overwrite = messagebox.askyesno(
                "ByteForge",
                f"O arquivo '{os.path.basename(output_path)}' já existe. Deseja sobrescrevê-lo?",
            )
            if not overwrite:
                return

        self._append_log(f"Solicitação de geração recebida: {format_bytes(total_bytes)} em '{output_path}'.")
        self._pending_output_path = output_path
        self._pending_total_bytes = total_bytes

        self._worker = FileGeneratorWorker(
            config=config,
            on_progress=self._handle_progress_threadsafe,
            on_log=self._handle_log_threadsafe,
        )

        self.progress_bar.set(0)
        self._smooth_progress.set_immediate(0.0)
        self._set_controls_running_state()
        self._worker.start()

    def _on_pause_clicked(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            return
        self._is_paused = self._worker.toggle_pause()
        self.pause_btn.configure(text="▶  Retomar" if self._is_paused else "⏸  Pausar")

    def _on_cancel_clicked(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            return
        confirm = messagebox.askyesno(
            "ByteForge", "Tem certeza de que deseja cancelar a geração em andamento?"
        )
        if confirm:
            self._worker.request_cancel()

    # ------------------------------------------------------------------
    # Callbacks vindos da thread de geração (NÃO tocar widgets aqui
    # diretamente; usamos self.after(0, ...) para repassar à thread
    # principal do Tkinter, que é a única thread autorizada a
    # manipular widgets com segurança).
    # ------------------------------------------------------------------

    def _handle_progress_threadsafe(self, progress: GenerationProgress) -> None:
        self.after(0, self._apply_progress, progress)

    def _handle_log_threadsafe(self, message: str) -> None:
        self.after(0, self._append_log, message)

    def _apply_progress(self, progress: GenerationProgress) -> None:
        self._smooth_progress.animate_to(progress.percentage / 100.0)
        self.percentage_label.configure(text=f"{progress.percentage:.1f}%")
        self.written_label.configure(
            text=f"{format_bytes(progress.bytes_written)} / {format_bytes(progress.total_bytes)}"
        )

        if progress.finished or progress.cancelled or progress.error:
            self._set_controls_idle_state()

            if progress.finished:
                self.speed_label.configure(text="Velocidade: concluído")
                self.eta_label.configure(text="ETA: 00:00")
                self._register_generated_file()
                flash_widget_color(self.generate_btn, theme.SUCCESS, theme.ACCENT, duration_ms=600)
                messagebox.showinfo("ByteForge", "Arquivo gerado com sucesso!")
            elif progress.cancelled:
                self.speed_label.configure(text="Velocidade: --")
                self.eta_label.configure(text="ETA: cancelado")
            elif progress.error:
                self.speed_label.configure(text="Velocidade: erro")
                self.eta_label.configure(text="ETA: --")
                messagebox.showerror("ByteForge - Erro", progress.error)
        else:
            self.speed_label.configure(text=f"Velocidade: {progress.speed_mb_s:.2f} MB/s")
            self.eta_label.configure(text=f"ETA: {self._format_eta(progress.eta_seconds)}")

    def _append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"• {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _register_generated_file(self) -> None:
        """
        Registra o arquivo recém-gerado no histórico persistente do
        ByteForge (`core.file_registry`), incrementando o contador
        histórico de arquivos criados, e abre a pasta de destino
        automaticamente caso essa opção esteja habilitada nas
        Configurações.
        """
        if not self._pending_output_path:
            return

        try:
            file_registry.register_new_file(self._pending_output_path, self._pending_total_bytes)
        except Exception:
            logger.exception("Falha ao registrar o arquivo gerado no histórico do ByteForge.")

        settings = self.settings_provider()
        if settings.auto_open_folder_after_generation:
            self._open_containing_folder(self._pending_output_path)

        self._pending_output_path = None
        self._pending_total_bytes = 0

    @staticmethod
    def _open_containing_folder(file_path: str) -> None:
        import subprocess
        import sys as _sys

        folder = os.path.dirname(file_path)
        try:
            if _sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif _sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            logger.exception("Falha ao abrir automaticamente a pasta '%s'.", folder)

    # ------------------------------------------------------------------
    # Utilitários de estado da UI
    # ------------------------------------------------------------------

    def _set_controls_running_state(self) -> None:
        self.generate_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal", text="⏸  Pausar")
        self.cancel_btn.configure(state="normal")

    def _set_controls_idle_state(self) -> None:
        self.generate_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled", text="⏸  Pausar")
        self.cancel_btn.configure(state="disabled")
        self._is_paused = False

    @staticmethod
    def _format_eta(seconds: Optional[float]) -> str:
        if seconds is None:
            return "calculando..."
        seconds = max(0, int(seconds))
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
