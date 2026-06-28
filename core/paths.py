"""
core/paths.py
----------------

Módulo central de definição de caminhos do ByteForge. Concentra,
em um único lugar, a localização de todos os diretórios e arquivos
internos da aplicação (dados persistentes, logs, saída padrão de
arquivos gerados etc.), evitando caminhos "mágicos" espalhados por
múltiplos módulos.

Estrutura de diretórios criada/utilizada pela aplicação:

    ByteForge/
    ├── data/
    │   ├── config.json            # configurações + aceite dos termos
    │   └── file_registry.json     # histórico de arquivos gerados
    ├── logs/
    │   └── byteforge.log          # log persistente de execução
    ├── output/                    # pasta padrão de saída dos arquivos
    └── plugins/
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _resolve_project_root() -> Path:
    """
    Resolve o diretório raiz "real" da aplicação, considerando dois
    cenários distintos:

    1. Execução normal a partir do código-fonte (`python main.py`):
       a raiz é a pasta que contém `main.py`.
    2. Execução a partir de um executável compilado com PyInstaller
       no modo `--onefile`: `__file__` apontaria para uma pasta
       temporária de extração (`sys._MEIPASS`), que é **apagada**
       quando o programa é encerrado. Usar essa pasta para guardar
       `data/`, `logs/` e `output/` faria com que TODA configuração,
       histórico de arquivos e logs fossem perdidos a cada execução.

    Por isso, quando `sys.frozen` estiver definido (indicando que o
    programa está rodando como executável compilado), utilizamos o
    diretório onde o executável (`sys.executable`) está localizado —
    que é persistente entre execuções — em vez de `__file__`.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


# Raiz do projeto (pasta que contém main.py, core/, gui/, etc., em
# execução via código-fonte; ou a pasta do executável, quando
# compilado com PyInstaller).
PROJECT_ROOT: Path = _resolve_project_root()

DATA_DIR: Path = PROJECT_ROOT / "data"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
DEFAULT_OUTPUT_DIR: Path = PROJECT_ROOT / "output"
PLUGINS_DIR: Path = PROJECT_ROOT / "plugins"

CONFIG_FILE: Path = DATA_DIR / "config.json"
FILE_REGISTRY_FILE: Path = DATA_DIR / "file_registry.json"
LOG_FILE: Path = LOGS_DIR / "byteforge.log"


def ensure_core_directories() -> None:
    """
    Garante que todos os diretórios essenciais da aplicação existam,
    criando-os de forma idempotente. Deve ser chamada o mais cedo
    possível na inicialização do programa (antes de configurar o
    logging ou carregar configurações).
    """
    for directory in (DATA_DIR, LOGS_DIR, DEFAULT_OUTPUT_DIR, PLUGINS_DIR):
        os.makedirs(directory, exist_ok=True)
