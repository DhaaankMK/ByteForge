"""
core/settings_manager.py
----------------------------

Módulo responsável por definir, validar, carregar e persistir as
configurações ajustáveis do ByteForge em um arquivo `config.json`
dentro da pasta `data/` do projeto.

Princípios de segurança aplicados neste módulo:

    * A assinatura da marca d'água NUNCA é uma configuração
      editável — ela é importada diretamente da constante fixa
      definida em `core.file_generator.FIXED_WATERMARK_SIGNATURE` e
      exibida apenas como informação somente leitura na interface.
    * O limite mínimo de espaço livre em disco possui um **piso
      absoluto de segurança** (`HARD_FLOOR_MIN_FREE_GB`). Mesmo que
      o usuário tente configurar um valor menor, o valor efetivo
      jamais ficará abaixo desse piso, prevenindo que a função de
      segurança de disco seja completamente desativada por engano.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict

from core.paths import CONFIG_FILE, DEFAULT_OUTPUT_DIR, ensure_core_directories
from core.file_generator import (
    DEFAULT_CHUNK_SIZE_BYTES,
    DEFAULT_WATERMARK_INTERVAL_BYTES,
    FIXED_WATERMARK_SIGNATURE,
)
from core.disk_utils import DEFAULT_MIN_FREE_SPACE_GB

logger = logging.getLogger("ByteForge.settings_manager")

# Piso absoluto de segurança: independentemente do que o usuário
# configurar na interface, o ByteForge nunca aplicará um limite de
# espaço livre obrigatório menor do que este valor. Esta é uma
# segunda camada de proteção, redundante por design, contra a
# desativação acidental ou indevida da verificação de segurança de
# disco.
HARD_FLOOR_MIN_FREE_GB: float = 5.0

VALID_APPEARANCE_MODES = ("Dark", "Light", "System")
VALID_COLOR_THEMES = ("blue", "green", "dark-blue")


@dataclass
class AppSettings:
    """Estrutura que centraliza todas as configurações ajustáveis do app."""

    # --- Segurança / disco -------------------------------------------------
    min_free_space_gb: float = DEFAULT_MIN_FREE_SPACE_GB

    # --- Desempenho de escrita ------------------------------------------------
    chunk_size_mb: float = DEFAULT_CHUNK_SIZE_BYTES / (1024 * 1024)
    watermark_interval_mb: float = DEFAULT_WATERMARK_INTERVAL_BYTES / (1024 * 1024)

    # --- Local de salvamento dos arquivos ---------------------------------------
    output_directory: str = str(DEFAULT_OUTPUT_DIR)

    # --- Aparência / tema ------------------------------------------------------
    appearance_mode: str = "Dark"
    color_theme: str = "blue"

    # --- Comportamento geral -----------------------------------------------------
    confirm_before_overwrite: bool = True
    confirm_before_delete: bool = True
    auto_open_folder_after_generation: bool = False

    # ------------------------------------------------------------------
    # Propriedades derivadas (somente leitura)
    # ------------------------------------------------------------------

    @property
    def chunk_size_bytes(self) -> int:
        return max(1, int(self.chunk_size_mb * 1024 * 1024))

    @property
    def watermark_interval_bytes(self) -> int:
        return max(1, int(self.watermark_interval_mb * 1024 * 1024))

    @property
    def watermark_signature(self) -> str:
        """
        Exposta apenas como informação somente leitura. A assinatura
        real utilizada na geração de arquivos é sempre a constante
        fixa do módulo `file_generator` — este atributo existe para
        que a interface possa exibi-la sem importar diretamente o
        módulo de geração de arquivos.
        """
        return FIXED_WATERMARK_SIGNATURE

    def effective_min_free_space_gb(self) -> float:
        """
        Retorna o limite mínimo de espaço livre que será de fato
        aplicado durante a geração de arquivos, já considerando o
        piso absoluto de segurança (`HARD_FLOOR_MIN_FREE_GB`).
        """
        return max(self.min_free_space_gb, HARD_FLOOR_MIN_FREE_GB)

    def validate_and_clamp(self) -> None:
        """
        Normaliza e corrige valores inválidos ou inseguros, aplicando
        limites mínimos sensatos. Deve ser chamado sempre após
        carregar configurações de uma fonte externa (arquivo JSON)
        ou após edição pelo usuário, antes de salvar.
        """
        if self.min_free_space_gb < HARD_FLOOR_MIN_FREE_GB:
            logger.warning(
                "Valor de 'min_free_space_gb' (%.2f GB) abaixo do piso de segurança "
                "(%.2f GB). Ajustando automaticamente para o piso mínimo.",
                self.min_free_space_gb, HARD_FLOOR_MIN_FREE_GB,
            )
            self.min_free_space_gb = HARD_FLOOR_MIN_FREE_GB

        if self.chunk_size_mb <= 0:
            self.chunk_size_mb = DEFAULT_CHUNK_SIZE_BYTES / (1024 * 1024)

        if self.watermark_interval_mb <= 0:
            self.watermark_interval_mb = DEFAULT_WATERMARK_INTERVAL_BYTES / (1024 * 1024)

        if self.appearance_mode not in VALID_APPEARANCE_MODES:
            self.appearance_mode = "Dark"

        if self.color_theme not in VALID_COLOR_THEMES:
            self.color_theme = "blue"

        if not self.output_directory or not self.output_directory.strip():
            self.output_directory = str(DEFAULT_OUTPUT_DIR)


def _settings_to_dict(settings: AppSettings) -> Dict[str, Any]:
    """
    Converte um `AppSettings` para um dicionário serializável,
    excluindo propriedades derivadas (que não fazem parte dos campos
    do dataclass e, portanto, já são automaticamente ignoradas pelo
    `asdict`).
    """
    return asdict(settings)


def load_settings() -> AppSettings:
    """
    Carrega as configurações persistidas em `data/config.json`. Caso
    o arquivo não exista, esteja corrompido ou contenha campos
    inválidos, retorna uma instância de `AppSettings` com valores
    padrão seguros, registrando o ocorrido no log — a aplicação
    NUNCA falha ao iniciar por causa de um arquivo de configuração
    inválido.
    """
    ensure_core_directories()

    if not CONFIG_FILE.exists():
        logger.info("Nenhum arquivo de configuração encontrado. Utilizando padrões.")
        defaults = AppSettings()
        defaults.validate_and_clamp()
        return defaults

    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        known_fields = set(AppSettings.__dataclass_fields__.keys())
        filtered = {k: v for k, v in raw.items() if k in known_fields}
        settings = AppSettings(**filtered)
        settings.validate_and_clamp()
        logger.info("Configurações carregadas com sucesso de '%s'.", CONFIG_FILE)
        return settings

    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.error(
            "Arquivo de configuração corrompido ou inválido (%s). "
            "Restaurando configurações padrão.", exc
        )
        defaults = AppSettings()
        defaults.validate_and_clamp()
        return defaults


def save_settings(settings: AppSettings) -> None:
    """
    Persiste as configurações atuais em `data/config.json`, em
    formato JSON legível (indentado). A validação/normalização é
    sempre executada antes da escrita, garantindo que nenhum valor
    inseguro ou inválido seja salvo em disco.
    """
    ensure_core_directories()
    settings.validate_and_clamp()

    try:
        CONFIG_FILE.write_text(
            json.dumps(_settings_to_dict(settings), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Configurações salvas com sucesso em '%s'.", CONFIG_FILE)
    except OSError as exc:
        logger.exception("Falha ao salvar configurações em '%s': %s", CONFIG_FILE, exc)
        raise
