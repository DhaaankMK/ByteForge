"""
core/disk_utils.py
-------------------

Módulo responsável por toda a lógica de segurança relacionada ao
espaço em disco. O ByteForge NUNCA deve permitir a criação de um
arquivo que deixe o volume de destino com menos de um limite mínimo
de espaço livre (por padrão, 15 GB), evitando que o sistema
operacional do usuário fique sem espaço para arquivos de sistema,
memória virtual (swap/pagefile) ou outras operações críticas.

Este módulo utiliza a biblioteca padrão `shutil` (via shutil.disk_usage)
como mecanismo primário, com fallback opcional para `psutil`, que
oferece informações mais detalhadas em alguns sistemas operacionais.
"""

from __future__ import annotations

import os
import shutil
import logging
from dataclasses import dataclass
from typing import Optional

try:
    import psutil  # type: ignore
    _PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover - psutil é opcional, mas recomendado
    _PSUTIL_AVAILABLE = False

logger = logging.getLogger("ByteForge.disk_utils")

# Limite mínimo de segurança, em bytes (15 GB).
# Este valor é definido como constante para evitar "magic numbers"
# espalhados pelo código e para facilitar auditoria de segurança.
DEFAULT_MIN_FREE_SPACE_GB: float = 15.0
BYTES_PER_GB: int = 1024 ** 3


@dataclass(frozen=True)
class DiskCheckResult:
    """
    Estrutura imutável que representa o resultado de uma verificação
    de espaço em disco. Usar um dataclass aqui (em vez de uma tupla
    solta) torna o retorno da função autoexplicativo e seguro contra
    erros de ordenação de campos.
    """
    allowed: bool
    total_bytes: int
    used_bytes: int
    free_bytes_before: int
    free_bytes_after: int
    min_required_bytes: int
    message: str

    @property
    def free_gb_before(self) -> float:
        return self.free_bytes_before / BYTES_PER_GB

    @property
    def free_gb_after(self) -> float:
        return self.free_bytes_after / BYTES_PER_GB


def _resolve_existing_directory(path: str) -> str:
    """
    Dado um caminho de arquivo ou diretório, retorna o diretório
    "ancestral" mais próximo que de fato existe no sistema de
    arquivos. Isso é necessário porque `shutil.disk_usage` e
    `psutil.disk_usage` exigem um caminho existente, mas o usuário
    pode informar um caminho de arquivo que ainda não foi criado.

    Levanta FileNotFoundError caso nenhum ancestral exista (situação
    extremamente improvável em sistemas Unix/Windows normais, pois a
    raiz do sistema de arquivos sempre existe).
    """
    candidate = os.path.abspath(path)

    # Se o caminho aponta para um arquivo (ainda não criado) ou para
    # um diretório, normalizamos para o diretório correspondente.
    if os.path.splitext(candidate)[1] and not os.path.isdir(candidate):
        candidate = os.path.dirname(candidate) or os.getcwd()

    visited = set()
    while not os.path.isdir(candidate):
        if candidate in visited:
            raise FileNotFoundError(
                f"Não foi possível resolver um diretório existente a partir de: {path}"
            )
        visited.add(candidate)
        parent = os.path.dirname(candidate)
        if parent == candidate:
            raise FileNotFoundError(
                f"Não foi possível resolver um diretório existente a partir de: {path}"
            )
        candidate = parent

    return candidate


def get_disk_usage(path: str) -> "shutil._ntuple_diskusage":
    """
    Retorna o uso de disco (total, used, free) para o volume que
    contém `path`. Tenta usar `psutil` primeiro (quando disponível),
    pois oferece compatibilidade mais ampla em alguns sistemas com
    múltiplos pontos de montagem, e recorre a `shutil.disk_usage`
    como alternativa robusta e sempre disponível na stdlib.
    """
    directory = _resolve_existing_directory(path)

    if _PSUTIL_AVAILABLE:
        try:
            usage = psutil.disk_usage(directory)
            # psutil retorna um objeto com atributos total/used/free/percent,
            # compatível com a interface usada neste módulo.
            return usage
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Falha ao obter uso de disco via psutil (%s). "
                "Utilizando shutil como alternativa.", exc
            )

    return shutil.disk_usage(directory)


def check_free_space(
    target_directory: str,
    planned_file_size_bytes: int,
    min_free_space_gb: float = DEFAULT_MIN_FREE_SPACE_GB,
) -> DiskCheckResult:
    """
    Verifica se é seguro gravar um arquivo de tamanho
    `planned_file_size_bytes` no diretório `target_directory`.

    A regra de segurança implementada é:

        espaço_livre_atual - tamanho_do_arquivo >= limite_mínimo

    Ou seja, o ByteForge bloqueia a geração do arquivo se, **após**
    a escrita, o espaço livre restante no volume for inferior ao
    limite mínimo configurado (15 GB por padrão).

    Parâmetros
    ----------
    target_directory : str
        Diretório de destino onde o arquivo será criado.
    planned_file_size_bytes : int
        Tamanho total planejado do arquivo, em bytes.
    min_free_space_gb : float
        Limite mínimo de espaço livre remanescente, em gigabytes.

    Retorna
    -------
    DiskCheckResult
        Objeto contendo o veredito (allowed) e métricas detalhadas
        para serem exibidas na interface ou registradas em log.
    """
    if planned_file_size_bytes < 0:
        raise ValueError("O tamanho do arquivo planejado não pode ser negativo.")

    min_required_bytes = int(min_free_space_gb * BYTES_PER_GB)

    usage = get_disk_usage(target_directory)
    total_bytes = int(usage.total)
    used_bytes = int(usage.used)
    free_bytes_before = int(usage.free)

    free_bytes_after = free_bytes_before - planned_file_size_bytes

    allowed = free_bytes_after >= min_required_bytes

    if free_bytes_before < planned_file_size_bytes:
        allowed = False
        message = (
            f"Espaço insuficiente: o disco possui apenas "
            f"{free_bytes_before / BYTES_PER_GB:.2f} GB livres, mas o arquivo "
            f"solicitado requer {planned_file_size_bytes / BYTES_PER_GB:.2f} GB."
        )
    elif not allowed:
        message = (
            f"Operação bloqueada por segurança: após gravar este arquivo, restariam "
            f"apenas {free_bytes_after / BYTES_PER_GB:.2f} GB livres, abaixo do "
            f"limite mínimo configurado de {min_free_space_gb:.2f} GB."
        )
    else:
        message = (
            f"Espaço suficiente. Após a gravação, restarão aproximadamente "
            f"{free_bytes_after / BYTES_PER_GB:.2f} GB livres "
            f"(limite mínimo: {min_free_space_gb:.2f} GB)."
        )

    result = DiskCheckResult(
        allowed=allowed,
        total_bytes=total_bytes,
        used_bytes=used_bytes,
        free_bytes_before=free_bytes_before,
        free_bytes_after=max(free_bytes_after, 0),
        min_required_bytes=min_required_bytes,
        message=message,
    )

    logger.info(
        "Verificação de disco em '%s': allowed=%s | livre_antes=%.2fGB | "
        "livre_depois=%.2fGB | minimo=%.2fGB",
        target_directory, result.allowed, result.free_gb_before,
        result.free_gb_after, min_free_space_gb,
    )

    return result


def format_bytes(num_bytes: int) -> str:
    """
    Converte um valor em bytes para uma string legível por humanos
    (ex.: "3.42 GB"), usada em diversos pontos da interface.
    """
    step_unit = 1024.0
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if value < step_unit:
            return f"{value:.2f} {unit}"
        value /= step_unit
    return f"{value:.2f} EB"
