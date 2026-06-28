"""
gui/tab_settings.py
----------------------

Aba 'Configurações' da aplicação ByteForge (versão expandida e
persistente).

Novidades desta versão:
    * Todas as configurações são salvas em disco (`data/config.json`)
      através de `core.settings_manager`, e carregadas automaticamente
      na próxima abertura do aplicativo.
    * A assinatura da marca d'água é exibida apenas como informação
      **somente leitura** — não pode mais ser editada pelo usuário,
      permanecendo permanentemente fixa em "ByteForge - DhaaankMK".
    * Nova opção para escolher a pasta padrão onde os arquivos serão
      salvos (por padrão, a pasta `output/` dentro do próprio
      ByteForge).
    * Tema visual expandido: modo de aparência (Claro/Escuro/Sistema)
      e paleta de cores (Azul/Verde/Azul-escuro).
    * Novas opções de comportamento: confirmar antes de sobrescrever,
      confirmar antes de excluir e abrir a pasta automaticamente após
      a geração.
"""

from __future__ import annotations

import os
import logging
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.settings_manager import (
    AppSettings,
    HARD_FLOOR_MIN_FREE_GB,
    save_settings,
    VALID_APPEARANCE_MODES,
    VALID_COLOR_THEMES,
)
from gui import theme
from gui.widgets import GradientBanner, flash_widget_color

logger = logging.getLogger("ByteForge.gui.settings")


class SettingsTab(ctk.CTkFrame):
    """Frame correspondente à aba 'Configurações' do TabView principal."""

    def __init__(self, master, settings: AppSettings, on_change=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.settings = settings
        self._on_change = on_change
        self.grid_columnconfigure(0, weight=1)
        self._build_widgets()

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------

    def _build_widgets(self) -> None:
        header = GradientBanner(self, height=78, show_logo=False, highlightthickness=0)
        header.grid(row=0, column=0, sticky="ew")
        header.update_texts(
            title="Configurações Avançadas",
            subtitle="Personalize o comportamento, segurança e visual do ByteForge",
        )

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(15, 10))
        scroll.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_storage_section(scroll, row=0)
        self._build_security_section(scroll, row=1)
        self._build_performance_section(scroll, row=2)
        self._build_appearance_section(scroll, row=3)
        self._build_behavior_section(scroll, row=4)
        self._build_watermark_section(scroll, row=5)

        self.save_btn = ctk.CTkButton(
            self, text="💾 Salvar Configurações", fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER, command=self._on_save,
        )
        self.save_btn.grid(row=2, column=0, sticky="w", padx=20, pady=(5, 20))

    def _section_frame(self, parent, row: int, title: str) -> ctk.CTkFrame:
        outer = ctk.CTkFrame(parent, border_width=1, border_color=theme.ACCENT_SOFT)
        outer.grid(row=row, column=0, sticky="ew", pady=8)
        outer.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            outer, text=title, font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(12, 8))
        return outer

    # --- Seção: Local de salvamento -------------------------------------------------

    def _build_storage_section(self, parent, row: int) -> None:
        section = self._section_frame(parent, row, "📁 Local de Salvamento")

        ctk.CTkLabel(section, text="Pasta padrão para novos arquivos:").grid(
            row=1, column=0, sticky="w", padx=15, pady=(0, 12)
        )

        self.output_dir_entry = ctk.CTkEntry(section)
        self.output_dir_entry.insert(0, self.settings.output_directory)
        self.output_dir_entry.grid(row=1, column=1, sticky="ew", padx=(0, 5), pady=(0, 12))

        ctk.CTkButton(
            section, text="Procurar...", width=110, command=self._browse_output_dir
        ).grid(row=1, column=2, padx=(0, 15), pady=(0, 12))

        ctk.CTkLabel(
            section,
            text=(
                "Por padrão, os arquivos são salvos dentro da própria pasta do "
                "ByteForge (subpasta 'output/'), facilitando a organização e o "
                "gerenciamento pela aba 'Gerenciador'."
            ),
            font=ctk.CTkFont(size=11), text_color=("gray45", "gray65"),
            wraplength=520, justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=15, pady=(0, 12))

    def _browse_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Selecione a pasta padrão de salvamento")
        if path:
            self.output_dir_entry.delete(0, "end")
            self.output_dir_entry.insert(0, path)

    # --- Seção: Segurança de disco ----------------------------------------------------

    def _build_security_section(self, parent, row: int) -> None:
        section = self._section_frame(parent, row, "🛡️ Segurança de Disco")

        ctk.CTkLabel(section, text="Espaço mínimo livre obrigatório (GB):").grid(
            row=1, column=0, sticky="w", padx=15, pady=(0, 5)
        )
        self.min_free_entry = ctk.CTkEntry(section, width=120)
        self.min_free_entry.insert(0, str(self.settings.min_free_space_gb))
        self.min_free_entry.grid(row=1, column=1, sticky="w", padx=15, pady=(0, 5))

        ctk.CTkLabel(
            section,
            text=(
                f"Por segurança, este valor nunca pode ser inferior a "
                f"{HARD_FLOOR_MIN_FREE_GB:.0f} GB, mesmo que um valor menor seja "
                f"digitado — o ByteForge aplicará automaticamente o piso mínimo."
            ),
            font=ctk.CTkFont(size=11), text_color=("gray45", "gray65"),
            wraplength=520, justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=15, pady=(0, 12))

    # --- Seção: Performance --------------------------------------------------------------

    def _build_performance_section(self, parent, row: int) -> None:
        section = self._section_frame(parent, row, "⚡ Desempenho de Escrita")

        ctk.CTkLabel(section, text="Tamanho do bloco de escrita (MB):").grid(
            row=1, column=0, sticky="w", padx=15, pady=(0, 5)
        )
        self.chunk_entry = ctk.CTkEntry(section, width=120)
        self.chunk_entry.insert(0, str(self.settings.chunk_size_mb))
        self.chunk_entry.grid(row=1, column=1, sticky="w", padx=15, pady=(0, 5))

        ctk.CTkLabel(section, text="Intervalo entre marcas d'água (MB):").grid(
            row=2, column=0, sticky="w", padx=15, pady=(0, 12)
        )
        self.watermark_interval_entry = ctk.CTkEntry(section, width=120)
        self.watermark_interval_entry.insert(0, str(self.settings.watermark_interval_mb))
        self.watermark_interval_entry.grid(row=2, column=1, sticky="w", padx=15, pady=(0, 12))

    # --- Seção: Aparência --------------------------------------------------------------------

    def _build_appearance_section(self, parent, row: int) -> None:
        section = self._section_frame(parent, row, "🎨 Aparência")

        ctk.CTkLabel(section, text="Modo de aparência:").grid(
            row=1, column=0, sticky="w", padx=15, pady=(0, 5)
        )
        self.appearance_combo = ctk.CTkComboBox(
            section, values=list(VALID_APPEARANCE_MODES), width=140,
            command=self._on_appearance_changed,
        )
        self.appearance_combo.set(self.settings.appearance_mode)
        self.appearance_combo.grid(row=1, column=1, sticky="w", padx=15, pady=(0, 5))

        ctk.CTkLabel(section, text="Paleta de cores:").grid(
            row=2, column=0, sticky="w", padx=15, pady=(0, 12)
        )
        self.color_theme_combo = ctk.CTkComboBox(
            section, values=list(VALID_COLOR_THEMES), width=140,
        )
        self.color_theme_combo.set(self.settings.color_theme)
        self.color_theme_combo.grid(row=2, column=1, sticky="w", padx=15, pady=(0, 12))

        ctk.CTkLabel(
            section,
            text=(
                "Alterações na paleta de cores são aplicadas após salvar e reiniciar "
                "o ByteForge. O modo de aparência é aplicado imediatamente."
            ),
            font=ctk.CTkFont(size=11), text_color=("gray45", "gray65"),
            wraplength=520, justify="left",
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=15, pady=(0, 12))

    def _on_appearance_changed(self, value: str) -> None:
        ctk.set_appearance_mode(value)

    # --- Seção: Comportamento -----------------------------------------------------------------

    def _build_behavior_section(self, parent, row: int) -> None:
        section = self._section_frame(parent, row, "⚙️ Comportamento Geral")

        self.confirm_overwrite_var = ctk.BooleanVar(value=self.settings.confirm_before_overwrite)
        ctk.CTkCheckBox(
            section, text="Pedir confirmação antes de sobrescrever um arquivo existente",
            variable=self.confirm_overwrite_var,
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=15, pady=(0, 8))

        self.confirm_delete_var = ctk.BooleanVar(value=self.settings.confirm_before_delete)
        ctk.CTkCheckBox(
            section, text="Pedir confirmação antes de excluir um arquivo no Gerenciador",
            variable=self.confirm_delete_var,
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=15, pady=(0, 8))

        self.auto_open_var = ctk.BooleanVar(value=self.settings.auto_open_folder_after_generation)
        ctk.CTkCheckBox(
            section, text="Abrir automaticamente a pasta de destino após gerar um arquivo",
            variable=self.auto_open_var,
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=15, pady=(0, 12))

    # --- Seção: Marca d'água (somente leitura) ------------------------------------------------

    def _build_watermark_section(self, parent, row: int) -> None:
        section = self._section_frame(parent, row, "🔒 Marca D'água (Permanente)")

        watermark_value = ctk.CTkEntry(section)
        watermark_value.insert(0, self.settings.watermark_signature)
        watermark_value.configure(state="disabled")
        watermark_value.grid(row=1, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 5))

        ctk.CTkLabel(
            section,
            text=(
                "Por motivos de rastreabilidade e segurança, a assinatura da marca "
                "d'água é fixa e não pode ser alterada pelo usuário. Todo arquivo "
                "gerado pelo ByteForge sempre conterá esta assinatura internamente."
            ),
            font=ctk.CTkFont(size=11), text_color=("gray45", "gray65"),
            wraplength=520, justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=15, pady=(0, 12))

    # ------------------------------------------------------------------
    # Salvamento
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        try:
            min_free_gb = float(self.min_free_entry.get().replace(",", "."))
            chunk_mb = float(self.chunk_entry.get().replace(",", "."))
            watermark_mb = float(self.watermark_interval_entry.get().replace(",", "."))
            output_directory = self.output_dir_entry.get().strip()
            appearance_mode = self.appearance_combo.get()
            color_theme = self.color_theme_combo.get()

            if chunk_mb <= 0:
                raise ValueError("O tamanho do bloco deve ser maior que zero.")
            if watermark_mb <= 0:
                raise ValueError("O intervalo de marca d'água deve ser maior que zero.")
            if not output_directory:
                raise ValueError("A pasta de salvamento não pode ficar vazia.")

            os.makedirs(output_directory, exist_ok=True)

            self.settings.min_free_space_gb = min_free_gb
            self.settings.chunk_size_mb = chunk_mb
            self.settings.watermark_interval_mb = watermark_mb
            self.settings.output_directory = output_directory
            self.settings.appearance_mode = appearance_mode
            self.settings.color_theme = color_theme
            self.settings.confirm_before_overwrite = self.confirm_overwrite_var.get()
            self.settings.confirm_before_delete = self.confirm_delete_var.get()
            self.settings.auto_open_folder_after_generation = self.auto_open_var.get()

            self.settings.validate_and_clamp()
            save_settings(self.settings)

            # Reflete de volta no campo de espaço mínimo, caso o piso de
            # segurança tenha corrigido o valor digitado pelo usuário.
            self.min_free_entry.delete(0, "end")
            self.min_free_entry.insert(0, str(self.settings.min_free_space_gb))

            if self._on_change:
                self._on_change(self.settings)

            flash_widget_color(self.save_btn, theme.SUCCESS, theme.ACCENT, duration_ms=500)
            messagebox.showinfo(
                "ByteForge",
                "Configurações salvas com sucesso.\n\n"
                "Algumas alterações de tema podem exigir reiniciar o aplicativo "
                "para serem totalmente aplicadas.",
            )

        except ValueError as exc:
            messagebox.showerror("ByteForge", f"Configuração inválida: {exc}")
        except OSError as exc:
            messagebox.showerror("ByteForge", f"Não foi possível usar essa pasta: {exc}")
