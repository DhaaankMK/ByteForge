"""
core/network_utils.py
-----------------------

Módulo responsável por estruturar a camada de rede do ByteForge,
preparando o terreno para futuras integrações reais com uma "Loja de
Plugins" remota. Atualmente, a URL de destino é meramente
representativa (não corresponde a um serviço em produção), portanto
este módulo é projetado para falhar de forma graciosa, sem nunca
travar a interface ou lançar exceções não tratadas para a camada de
GUI.

Toda a verificação é executada com timeout curto e tratamento
explícito de exceções de rede (timeout, falha de DNS, conexão
recusada, etc.), retornando sempre um objeto estruturado
`ConnectivityResult` em vez de propagar exceções.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

try:
    import requests  # type: ignore
    _REQUESTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _REQUESTS_AVAILABLE = False

logger = logging.getLogger("ByteForge.network_utils")

# URL base do (futuro) servidor de plugins do ByteForge. Este
# endereço é meramente ilustrativo/placeholder e não corresponde a
# uma infraestrutura real em produção. Ele existe apenas para que a
# arquitetura de rede já esteja pronta para receber uma API real no
# futuro, sem necessidade de refatoração estrutural.
PLUGIN_STORE_BASE_URL: str = "https://plugins.byteforge.dev/api/v1/status"

DEFAULT_TIMEOUT_SECONDS: float = 3.0


@dataclass(frozen=True)
class ConnectivityResult:
    """Resultado estruturado de uma tentativa de verificação de rede."""
    success: bool
    status_code: Optional[int]
    latency_ms: Optional[float]
    message: str


def check_plugin_store_connection(
    url: str = PLUGIN_STORE_BASE_URL,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> ConnectivityResult:
    """
    Tenta estabelecer uma conexão HTTP simples com o servidor de
    plugins do ByteForge. Como o serviço ainda não existe em
    produção, espera-se que esta chamada falhe (timeout ou erro de
    resolução de DNS) em ambientes normais — e isso é tratado como um
    resultado esperado e não como uma falha crítica da aplicação.

    Esta função NUNCA lança exceções: todos os erros de rede são
    capturados e convertidos em um `ConnectivityResult` com
    `success=False` e uma mensagem amigável para o usuário.
    """
    if not _REQUESTS_AVAILABLE:
        return ConnectivityResult(
            success=False,
            status_code=None,
            latency_ms=None,
            message=(
                "Biblioteca 'requests' não está instalada. "
                "A verificação de conectividade com a Loja de Plugins "
                "foi ignorada."
            ),
        )

    start = time.monotonic()
    try:
        response = requests.get(url, timeout=timeout_seconds)
        latency_ms = (time.monotonic() - start) * 1000.0
        return ConnectivityResult(
            success=response.ok,
            status_code=response.status_code,
            latency_ms=latency_ms,
            message="Conexão com a Loja de Plugins estabelecida com sucesso.",
        )

    except requests.exceptions.Timeout:
        return ConnectivityResult(
            success=False,
            status_code=None,
            latency_ms=None,
            message=(
                "Tempo de conexão esgotado ao tentar contatar a Loja de "
                "Plugins. O serviço remoto ainda não está disponível."
            ),
        )

    except requests.exceptions.ConnectionError:
        return ConnectivityResult(
            success=False,
            status_code=None,
            latency_ms=None,
            message=(
                "Não foi possível resolver/conectar ao servidor da Loja "
                "de Plugins. Funcionalidade reservada para uma atualização futura."
            ),
        )

    except Exception as exc:  # pragma: no cover - rede de segurança final
        logger.exception("Erro inesperado ao verificar conectividade de rede.")
        return ConnectivityResult(
            success=False,
            status_code=None,
            latency_ms=None,
            message=f"Erro inesperado na verificação de rede: {exc}",
        )
