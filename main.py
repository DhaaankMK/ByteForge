#!/usr/bin/env python3
"""
main.py
---------

Ponto de entrada da aplicação ByteForge.

Responsabilidades deste módulo:
    * Garantir a existência de toda a estrutura de diretórios
      internos da aplicação (`data/`, `logs/`, `output/`, `plugins/`).
    * Configurar o sistema de logging persistente, registrando toda
      execução (início e encerramento) e qualquer erro/exceção não
      tratada que ocorra em qualquer parte do programa.
    * Instanciar e executar a janela principal (ByteForgeApp).

Uso:
    python main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que o diretório raiz do projeto esteja no sys.path,
# permitindo importações absolutas como `from core import ...`
# independentemente do diretório de onde o script é executado.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from core.paths import ensure_core_directories
    from core.app_logger import (
        configure_logging,
        install_global_exception_hook,
        log_application_start,
        log_application_end,
    )

    ensure_core_directories()
    logger = configure_logging()
    install_global_exception_hook()
    log_application_start()

    try:
        from core.plugin_manager import ensure_plugins_directory
        from gui.app import ByteForgeApp
        from gui.splash import show_splash

        ensure_plugins_directory()

        logger.info("Exibindo tela de splash...")
        show_splash(duration_ms=1600)

        logger.info("Inicializando a interface gráfica do ByteForge...")
        app = ByteForgeApp()
        app.mainloop()
        log_application_end(reason="encerramento normal")
        return 0

    except ImportError as exc:
        logger.critical("Erro de dependência ausente: %s", exc)
        print(
            "\n[ByteForge] Erro de dependência ausente: "
            f"{exc}\n\n"
            "Certifique-se de instalar todas as dependências listadas em "
            "'requirements.txt' antes de executar a aplicação:\n\n"
            "    pip install -r requirements.txt\n",
            file=sys.stderr,
        )
        log_application_end(reason="erro de dependência ausente")
        return 1

    except Exception:  # pragma: no cover - rede de segurança final
        logger.exception("Erro fatal não tratado na aplicação ByteForge.")
        log_application_end(reason="erro fatal não tratado")
        return 1


if __name__ == "__main__":
    sys.exit(main())
