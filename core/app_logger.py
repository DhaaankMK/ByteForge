"""
core/app_logger.py
---------------------

Módulo responsável pela configuração centralizada do sistema de
logs do ByteForge.

Requisitos atendidos:
    * Toda execução do aplicativo (início e encerramento) é
      registrada no arquivo de log persistente.
    * Qualquer erro/exceção não tratada durante a execução é
      automaticamente registrada no log, incluindo o traceback
      completo, facilitando o diagnóstico de problemas.
    * O log utiliza rotação por tamanho (`RotatingFileHandler`),
      evitando que o arquivo cresça indefinidamente ao longo de
      muitas execuções do programa.
"""

from __future__ import annotations

import sys
import logging
import platform
from logging.handlers import RotatingFileHandler

from core.paths import LOG_FILE, ensure_core_directories

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

# Cada arquivo de log fica limitado a 2 MB; quando atingido, é
# rotacionado automaticamente, mantendo até 5 arquivos antigos
# (byteforge.log.1, .2, ... .5) para histórico recente sem consumir
# espaço em disco indefinidamente.
_MAX_LOG_SIZE_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 5

_configured = False


def configure_logging() -> logging.Logger:
    """
    Configura (uma única vez) o sistema de logging raiz da
    aplicação, registrando mensagens simultaneamente no console e em
    um arquivo persistente com rotação automática. Retorna o logger
    raiz do ByteForge ("ByteForge").
    """
    global _configured

    root_logger = logging.getLogger("ByteForge")

    if _configured:
        return root_logger

    ensure_core_directories()

    root_logger.setLevel(logging.INFO)
    root_logger.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=_MAX_LOG_SIZE_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    _configured = True
    return root_logger


def log_application_start() -> None:
    """
    Registra, de forma destacada no log, o início de uma nova sessão
    de execução do ByteForge, incluindo informações do sistema
    operacional e da versão do Python utilizada — úteis para
    diagnóstico remoto de problemas relatados por usuários.
    """
    logger = logging.getLogger("ByteForge.lifecycle")
    logger.info("=" * 70)
    logger.info("ByteForge iniciado.")
    logger.info(
        "Sistema: %s %s | Python: %s | Arquitetura: %s",
        platform.system(), platform.release(),
        platform.python_version(), platform.machine(),
    )
    logger.info("=" * 70)


def log_application_end(reason: str = "encerramento normal") -> None:
    """
    Registra, de forma destacada no log, o encerramento da sessão
    atual de execução do ByteForge, incluindo o motivo do
    encerramento (ex.: "encerramento normal", "erro fatal", etc.).
    """
    logger = logging.getLogger("ByteForge.lifecycle")
    logger.info("ByteForge encerrado (%s).", reason)
    logger.info("=" * 70)


def install_global_exception_hook() -> None:
    """
    Instala um `sys.excepthook` global que intercepta qualquer
    exceção não tratada em toda a aplicação (incluindo exceções que
    ocorram fora de threads de trabalho gerenciadas manualmente),
    registrando o traceback completo no log antes de permitir o
    comportamento padrão do Python.

    Isso garante que, mesmo em cenários de falha inesperada, o
    arquivo de log sempre contenha evidência suficiente para
    diagnóstico, em vez de a aplicação simplesmente "desaparecer".
    """
    logger = logging.getLogger("ByteForge.lifecycle")

    def _handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Erro fatal não tratado na aplicação ByteForge.",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        log_application_end(reason="erro fatal não tratado")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = _handle_exception
