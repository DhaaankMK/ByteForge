"""
core/plugin_manager.py
------------------------

Módulo responsável por descobrir, carregar e listar plugins
externos (.py) localizados na pasta `/plugins` do projeto. Esta é
uma arquitetura básica de plugins, pensada para ser expandida em
versões futuras do ByteForge sem necessidade de alterar o núcleo da
aplicação.

Convenção de plugin:
---------------------
Cada plugin é um arquivo .py colocado na pasta `plugins/` contendo,
no mínimo, uma variável de módulo `PLUGIN_NAME` (str) e,
opcionalmente, `PLUGIN_DESCRIPTION` (str) e uma função `run()`.
Plugins que não seguirem essa convenção são listados como
"plugins inválidos" e não quebram a aplicação principal.
"""

from __future__ import annotations

import os
import importlib.util
import logging
from dataclasses import dataclass
from types import ModuleType
from typing import List, Optional

logger = logging.getLogger("ByteForge.plugin_manager")

DEFAULT_PLUGINS_DIR: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins"
)


@dataclass
class PluginInfo:
    """Representa um plugin descoberto na pasta de plugins."""
    file_path: str
    name: str
    description: str = ""
    valid: bool = True
    error_message: Optional[str] = None
    module: Optional[ModuleType] = None


def ensure_plugins_directory(plugins_dir: str = DEFAULT_PLUGINS_DIR) -> str:
    """
    Garante que a pasta de plugins exista, criando-a caso necessário.
    Retorna o caminho absoluto da pasta.
    """
    os.makedirs(plugins_dir, exist_ok=True)
    return plugins_dir


def discover_plugins(plugins_dir: str = DEFAULT_PLUGINS_DIR) -> List[PluginInfo]:
    """
    Varre a pasta de plugins em busca de arquivos `.py` e tenta
    carregá-los dinamicamente usando `importlib`. Plugins que falharem
    ao carregar (erro de sintaxe, exceção no nível de módulo, etc.)
    são reportados como inválidos, mas não interrompem a varredura
    dos demais arquivos.

    Retorna uma lista de `PluginInfo`, podendo estar vazia caso a
    pasta não contenha nenhum arquivo `.py` válido — situação em que
    a interface deve exibir a mensagem "Loja de Plugins: Em breve".
    """
    plugins_dir = ensure_plugins_directory(plugins_dir)
    discovered: List[PluginInfo] = []

    try:
        candidate_files = sorted(
            f for f in os.listdir(plugins_dir)
            if f.endswith(".py") and not f.startswith("_")
        )
    except OSError as exc:
        logger.error("Não foi possível listar a pasta de plugins: %s", exc)
        return discovered

    for filename in candidate_files:
        full_path = os.path.join(plugins_dir, filename)
        plugin_info = _load_single_plugin(full_path)
        discovered.append(plugin_info)

    return discovered


def _load_single_plugin(full_path: str) -> PluginInfo:
    """
    Carrega um único arquivo de plugin de forma isolada e segura,
    capturando qualquer exceção que ocorra durante a importação do
    módulo (incluindo erros de sintaxe, ImportError, etc.).
    """
    module_name = f"byteforge_plugin_{os.path.splitext(os.path.basename(full_path))[0]}"

    try:
        spec = importlib.util.spec_from_file_location(module_name, full_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Não foi possível criar especificação de módulo para {full_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        name = getattr(module, "PLUGIN_NAME", os.path.basename(full_path))
        description = getattr(module, "PLUGIN_DESCRIPTION", "Sem descrição fornecida.")

        return PluginInfo(
            file_path=full_path,
            name=str(name),
            description=str(description),
            valid=True,
            module=module,
        )

    except Exception as exc:  # pragma: no cover - segurança contra plugins de terceiros
        logger.exception("Falha ao carregar o plugin '%s'.", full_path)
        return PluginInfo(
            file_path=full_path,
            name=os.path.basename(full_path),
            valid=False,
            error_message=str(exc),
        )


def run_plugin(plugin: PluginInfo) -> Optional[str]:
    """
    Executa a função `run()` de um plugin válido, caso ela exista.
    Retorna o resultado (convertido em string) ou None. Erros durante
    a execução são capturados e retornados como mensagem de erro
    formatada, nunca propagados para a interface gráfica.
    """
    if not plugin.valid or plugin.module is None:
        return "Este plugin não pôde ser carregado e não pode ser executado."

    run_callable = getattr(plugin.module, "run", None)
    if run_callable is None or not callable(run_callable):
        return "Este plugin não implementa uma função run() executável."

    try:
        result = run_callable()
        return str(result) if result is not None else "Plugin executado com sucesso."
    except Exception as exc:  # pragma: no cover
        logger.exception("Erro ao executar o plugin '%s'.", plugin.name)
        return f"Erro durante a execução do plugin: {exc}"
