"""
plugins/exemplo_info_sistema.py
----------------------------------

Plugin de exemplo, distribuído junto ao ByteForge apenas para
demonstrar a convenção de plugins. Pode ser removido ou usado como
modelo para a criação de novos plugins.

Convenção mínima de um plugin ByteForge:
    PLUGIN_NAME (str)         -> nome exibido na aba 'Plugins'.
    PLUGIN_DESCRIPTION (str)  -> descrição curta exibida na aba.
    def run() -> str          -> ação executada ao clicar em "Executar".
"""

import platform

PLUGIN_NAME = "Informações do Sistema"
PLUGIN_DESCRIPTION = "Exibe informações básicas sobre o sistema operacional atual."


def run() -> str:
    return (
        f"Sistema: {platform.system()} {platform.release()}\n"
        f"Versão do Python: {platform.python_version()}\n"
        f"Arquitetura: {platform.machine()}"
    )
