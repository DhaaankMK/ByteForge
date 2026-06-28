"""
core/file_generator.py
-----------------------

Módulo central do ByteForge. Implementa a geração de arquivos
"dummy" (de preenchimento) de tamanho arbitrário, escritos em blocos
(chunks) através de uma thread dedicada, de forma a manter a
interface gráfica (Tkinter/CustomTkinter) sempre responsiva.

Principais responsabilidades deste módulo:

1.  Gerar dados pseudoaleatórios de alta entropia para o corpo do
    arquivo (evitando arquivos compostos apenas por zeros, o que
    poderia ser otimizado de forma indesejada por sistemas de
    arquivos "sparse" ou ferramentas de compressão).
2.  Inserir marcas d'água (watermarks) internas em intervalos
    regulares, contendo uma assinatura textual fixa e um bloco de
    metadados em JSON (data de geração, autor do software, versão,
    índice do bloco, etc.), permitindo identificar a origem do
    arquivo mesmo após renomeado.
3.  Reportar progresso, velocidade de escrita (MB/s) e tempo
    estimado restante (ETA) através de callbacks thread-safe.
4.  Suportar cancelamento e pausa cooperativos, utilizando
    `threading.Event`.
5.  Tratamento de erros robusto: espaço em disco, permissões,
    interrupções do sistema operacional e limpeza de arquivos
    parciais em caso de cancelamento.
"""

from __future__ import annotations

import os
import io
import json
import time
import logging
import secrets
import threading
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from core.disk_utils import check_free_space, format_bytes

logger = logging.getLogger("ByteForge.file_generator")

# ----------------------------------------------------------------------
# Constantes de configuração padrão
# ----------------------------------------------------------------------

# Tamanho padrão de cada bloco de escrita (8 MB). Blocos muito
# pequenos aumentam o overhead de chamadas de sistema; blocos muito
# grandes aumentam o consumo de memória RAM e reduzem a frequência
# de atualização da interface. 8 MB é um equilíbrio adequado para a
# maioria dos discos SSD/HDD modernos.
DEFAULT_CHUNK_SIZE_BYTES: int = 8 * 1024 * 1024

# Intervalo (em bytes) entre cada inserção de marca d'água dentro do
# arquivo. Por padrão, a cada 64 MB de dados gerados, um bloco de
# watermark é inserido.
DEFAULT_WATERMARK_INTERVAL_BYTES: int = 64 * 1024 * 1024

# Assinatura textual da marca d'água embutida em cada arquivo gerado.
#
# IMPORTANTE — IMUTABILIDADE PROPOSITAL: por decisão de projeto, esta
# assinatura é uma constante FIXA e PERMANENTE, e não deve ser exposta
# como configuração editável em nenhuma tela da interface. Isso garante
# que todo arquivo gerado pelo ByteForge possa ser identificado e
# atribuído à sua origem de forma confiável e inalterável, mesmo que o
# usuário renomeie o arquivo ou altere outras configurações do
# aplicativo. Qualquer tentativa de sobrescrever este valor através de
# configuração externa é silenciosamente ignorada (ver `GenerationConfig`).
FIXED_WATERMARK_SIGNATURE: str = "ByteForge - DhaaankMK"

# Mantido por compatibilidade com versões anteriores do módulo. Aponta
# para a mesma constante fixa e não deve ser usado para permitir edição.
DEFAULT_WATERMARK_SIGNATURE: str = FIXED_WATERMARK_SIGNATURE

# Nome do produto, usado nos metadados internos do arquivo.
PRODUCT_NAME: str = "ByteForge"

# Autor/criador do software. Conforme solicitado explicitamente pelo
# proprietário deste projeto, a identidade pública exibida em
# qualquer metadado, log, marca d'água ou tela de créditos é o
# pseudônimo "DhaaankMK". O nome civil do autor é informação privada e
# NUNCA deve ser exposto pelo software em nenhuma circunstância.
PRODUCT_AUTHOR: str = "DhaaankMK"


class GenerationCancelledError(Exception):
    """Exceção interna levantada quando o usuário cancela a geração."""


@dataclass
class GenerationProgress:
    """
    Snapshot imutável do progresso da geração de arquivo, enviado
    periodicamente para a interface através de um callback.
    """
    bytes_written: int
    total_bytes: int
    speed_mb_s: float
    elapsed_seconds: float
    eta_seconds: Optional[float]
    finished: bool = False
    cancelled: bool = False
    error: Optional[str] = None

    @property
    def percentage(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(100.0, (self.bytes_written / self.total_bytes) * 100.0)


@dataclass
class GenerationConfig:
    """
    Agrupa todos os parâmetros configuráveis de uma operação de
    geração de arquivo, evitando assinaturas de função com dezenas
    de argumentos posicionais.

    NOTA DE SEGURANÇA: este objeto propositalmente NÃO possui um
    campo editável para a assinatura da marca d'água. A assinatura
    utilizada em toda e qualquer geração de arquivo é sempre a
    constante fixa `FIXED_WATERMARK_SIGNATURE` ("ByteForge -
    DhaaankMK"), garantindo rastreabilidade permanente dos arquivos
    gerados pelo software.
    """
    output_path: str
    total_size_bytes: int
    chunk_size_bytes: int = DEFAULT_CHUNK_SIZE_BYTES
    watermark_interval_bytes: int = DEFAULT_WATERMARK_INTERVAL_BYTES
    min_free_space_gb: float = 15.0
    extra_metadata: dict = field(default_factory=dict)


ProgressCallback = Callable[[GenerationProgress], None]


def _build_watermark_block(
    signature: str,
    block_index: int,
    file_total_size: int,
    extra_metadata: Optional[dict] = None,
) -> bytes:
    """
    Constrói um bloco de marca d'água em bytes, composto por:

        [SIGNATURE_ASCII] + [JSON_METADATA_UTF8] + [SEPARADOR]

    O JSON de metadados inclui informações como o nome do produto,
    o autor (pseudônimo público), a data/hora de geração em UTC,
    o índice do bloco de watermark e o tamanho total do arquivo.
    Esses metadados permitem rastrear e identificar arquivos gerados
    pelo ByteForge mesmo que tenham sido renomeados posteriormente.
    """
    metadata = {
        "product": PRODUCT_NAME,
        "author": PRODUCT_AUTHOR,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "watermark_index": block_index,
        "total_file_size_bytes": file_total_size,
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    payload = (
        f"<<{signature}>>"
        f"{json.dumps(metadata, ensure_ascii=False)}"
        f"<<END_{signature}>>"
    ).encode("utf-8")

    return payload


def _generate_pseudorandom_chunk(size: int) -> bytes:
    """
    Gera `size` bytes de dados pseudoaleatórios de alta entropia.

    Utiliza o módulo `secrets`, que internamente recorre ao gerador
    de números aleatórios criptograficamente seguro do sistema
    operacional (os.urandom). Isso garante que o arquivo gerado não
    seja apenas uma sequência de zeros (o que poderia ser comprimido
    trivialmente ou tratado como "sparse file" por alguns sistemas
    de arquivos), atendendo ao requisito de dados verdadeiramente
    pseudoaleatórios.
    """
    if size <= 0:
        return b""
    return secrets.token_bytes(size)


class FileGeneratorWorker(threading.Thread):
    """
    Thread dedicada à geração do arquivo dummy.

    Esta classe herda de `threading.Thread` para que a escrita em
    disco (operação potencialmente lenta e bloqueante) ocorra em uma
    thread separada da thread principal da interface gráfica,
    mantendo a UI do CustomTkinter sempre responsiva, conforme
    requisito de performance do projeto.

    O cancelamento é implementado de forma cooperativa através de um
    `threading.Event` (`self._cancel_event`), checado a cada bloco
    escrito. A pausa é implementada através de outro evento
    (`self._pause_event`).
    """

    def __init__(
        self,
        config: GenerationConfig,
        on_progress: Optional[ProgressCallback] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(daemon=True, name="ByteForge-FileGeneratorWorker")
        self.config = config
        self._on_progress = on_progress
        self._on_log = on_log

        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()  # set() == pausado

        self._bytes_written: int = 0
        self._start_time: Optional[float] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # API pública de controle (chamada pela thread da UI)
    # ------------------------------------------------------------------

    def request_cancel(self) -> None:
        """Solicita o cancelamento cooperativo da geração."""
        self._log("Cancelamento solicitado pelo usuário. Finalizando bloco atual...")
        self._cancel_event.set()

    def toggle_pause(self) -> bool:
        """
        Alterna entre pausado/em execução. Retorna o novo estado
        (True = pausado).
        """
        if self._pause_event.is_set():
            self._pause_event.clear()
            self._log("Geração retomada.")
            return False
        else:
            self._pause_event.set()
            self._log("Geração pausada.")
            return True

    @property
    def bytes_written(self) -> int:
        with self._lock:
            return self._bytes_written

    # ------------------------------------------------------------------
    # Núcleo de execução da thread
    # ------------------------------------------------------------------

    def run(self) -> None:  # noqa: C901 - complexidade justificada por robustez
        """
        Ponto de entrada da thread. Implementa o ciclo de vida
        completo da geração: validação de segurança, escrita em
        blocos, inserção de watermarks, relatório de progresso e
        tratamento de erros/limpeza.
        """
        cfg = self.config
        temp_path = cfg.output_path + ".byteforge.tmp"

        try:
            self._validate_before_start(cfg)

            self._start_time = time.monotonic()
            last_report_time = self._start_time
            last_report_bytes = 0
            watermark_index = 0
            bytes_since_last_watermark = 0

            self._log(f"Iniciando geração de '{os.path.basename(cfg.output_path)}' "
                       f"({format_bytes(cfg.total_size_bytes)})...")

            # Escrevemos primeiro em um arquivo temporário e, ao final,
            # renomeamos para o nome definitivo. Essa estratégia evita
            # que um arquivo "incompleto" seja confundido com um
            # arquivo válido caso o processo seja interrompido
            # abruptamente (ex.: queda de energia).
            with open(temp_path, "wb", buffering=0) as f:
                remaining = cfg.total_size_bytes

                while remaining > 0:
                    self._wait_while_paused()

                    if self._cancel_event.is_set():
                        raise GenerationCancelledError()

                    # Decide se este bloco deve conter uma watermark.
                    write_size = min(cfg.chunk_size_bytes, remaining)

                    if bytes_since_last_watermark >= cfg.watermark_interval_bytes:
                        watermark_index += 1
                        watermark_block = _build_watermark_block(
                            FIXED_WATERMARK_SIGNATURE,
                            watermark_index,
                            cfg.total_size_bytes,
                            cfg.extra_metadata,
                        )
                        watermark_block = watermark_block[:write_size]
                        remaining_in_chunk = write_size - len(watermark_block)
                        chunk = watermark_block + _generate_pseudorandom_chunk(remaining_in_chunk)
                        bytes_since_last_watermark = 0
                    else:
                        chunk = _generate_pseudorandom_chunk(write_size)

                    f.write(chunk)

                    with self._lock:
                        self._bytes_written += len(chunk)
                    bytes_since_last_watermark += len(chunk)
                    remaining -= len(chunk)

                    now = time.monotonic()
                    # Reporta progresso no máximo ~10 vezes por segundo,
                    # evitando sobrecarregar a fila de eventos da UI.
                    if now - last_report_time >= 0.1 or remaining <= 0:
                        self._report_progress(now, last_report_time, last_report_bytes)
                        last_report_time = now
                        last_report_bytes = self._bytes_written

                f.flush()
                os.fsync(f.fileno())

            # Renomeia o arquivo temporário para o nome final somente
            # após a escrita completa ter sido concluída com sucesso.
            os.replace(temp_path, cfg.output_path)

            total_elapsed = time.monotonic() - self._start_time
            self._log(
                f"Arquivo gerado com sucesso em {total_elapsed:.2f}s: "
                f"{cfg.output_path}"
            )
            self._emit_final_progress(finished=True)

        except GenerationCancelledError:
            self._log("Geração cancelada pelo usuário. Removendo arquivo parcial...")
            self._safe_remove(temp_path)
            self._emit_final_progress(cancelled=True)

        except PermissionError as exc:
            self._log(f"Erro de permissão: {exc}")
            self._safe_remove(temp_path)
            self._emit_final_progress(error=f"Permissão negada: {exc}")

        except OSError as exc:
            # Cobre erros de "disco cheio" (ENOSPC), caminho inválido,
            # dispositivo removido durante a escrita, etc.
            self._log(f"Erro de sistema operacional durante a escrita: {exc}")
            self._safe_remove(temp_path)
            self._emit_final_progress(error=f"Erro de E/S: {exc}")

        except Exception as exc:  # pragma: no cover - rede de segurança final
            logger.exception("Erro inesperado durante a geração do arquivo.")
            self._log(f"Erro inesperado: {exc}")
            self._safe_remove(temp_path)
            self._emit_final_progress(error=f"Erro inesperado: {exc}")

    # ------------------------------------------------------------------
    # Métodos auxiliares privados
    # ------------------------------------------------------------------

    def _validate_before_start(self, cfg: GenerationConfig) -> None:
        """
        Executa todas as validações de segurança e sanidade antes de
        iniciar a escrita de qualquer byte em disco.
        """
        if cfg.total_size_bytes <= 0:
            raise ValueError("O tamanho do arquivo deve ser maior que zero.")

        if cfg.chunk_size_bytes <= 0:
            raise ValueError("O tamanho do bloco (chunk) deve ser maior que zero.")

        output_dir = os.path.dirname(os.path.abspath(cfg.output_path)) or "."
        os.makedirs(output_dir, exist_ok=True)

        if not os.access(output_dir, os.W_OK):
            raise PermissionError(
                f"Sem permissão de escrita no diretório de destino: {output_dir}"
            )

        # Requisito obrigatório de segurança de disco: bloqueia a
        # operação se o espaço livre remanescente, após a escrita,
        # ficar abaixo do limite mínimo configurado (15 GB padrão).
        disk_check = check_free_space(
            output_dir, cfg.total_size_bytes, cfg.min_free_space_gb
        )
        if not disk_check.allowed:
            raise OSError(disk_check.message)

        self._log(disk_check.message)

    def _wait_while_paused(self) -> None:
        """
        Bloqueia a thread de geração enquanto o evento de pausa
        estiver ativo, verificando periodicamente também o
        cancelamento (para que seja possível cancelar mesmo enquanto
        pausado).
        """
        while self._pause_event.is_set():
            if self._cancel_event.is_set():
                return
            time.sleep(0.1)

    def _report_progress(
        self, now: float, last_time: float, last_bytes: int
    ) -> None:
        if self._on_progress is None or self._start_time is None:
            return

        interval = max(now - last_time, 1e-6)
        bytes_delta = self._bytes_written - last_bytes
        speed_mb_s = (bytes_delta / interval) / (1024 * 1024)

        elapsed = now - self._start_time
        remaining_bytes = self.config.total_size_bytes - self._bytes_written
        eta_seconds: Optional[float]
        if speed_mb_s > 0.01:
            eta_seconds = remaining_bytes / (speed_mb_s * 1024 * 1024)
        else:
            eta_seconds = None

        progress = GenerationProgress(
            bytes_written=self._bytes_written,
            total_bytes=self.config.total_size_bytes,
            speed_mb_s=speed_mb_s,
            elapsed_seconds=elapsed,
            eta_seconds=eta_seconds,
        )
        self._safe_callback(self._on_progress, progress)

    def _emit_final_progress(
        self,
        finished: bool = False,
        cancelled: bool = False,
        error: Optional[str] = None,
    ) -> None:
        if self._on_progress is None or self._start_time is None:
            return
        elapsed = time.monotonic() - self._start_time
        progress = GenerationProgress(
            bytes_written=self._bytes_written,
            total_bytes=self.config.total_size_bytes,
            speed_mb_s=0.0,
            elapsed_seconds=elapsed,
            eta_seconds=0.0 if finished else None,
            finished=finished,
            cancelled=cancelled,
            error=error,
        )
        self._safe_callback(self._on_progress, progress)

    def _safe_callback(self, callback: Callable, *args) -> None:
        """
        Executa um callback (geralmente destinado a atualizar a UI)
        protegido por try/except, para que uma falha na camada de
        apresentação nunca derrube a thread de geração de arquivos.
        """
        try:
            callback(*args)
        except Exception:  # pragma: no cover
            logger.exception("Falha ao executar callback de progresso/log.")

    def _log(self, message: str) -> None:
        logger.info(message)
        if self._on_log is not None:
            self._safe_callback(self._on_log, message)

    @staticmethod
    def _safe_remove(path: str) -> None:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:  # pragma: no cover
            logger.exception("Não foi possível remover o arquivo temporário: %s", path)


def parse_size_to_bytes(value: float, unit: str) -> int:
    """
    Converte um valor numérico e uma unidade textual ("KB", "MB",
    "GB", "TB") para um total de bytes (inteiro).

    Levanta ValueError caso a unidade seja desconhecida ou o valor
    seja inválido (negativo ou não numérico).
    """
    if value < 0:
        raise ValueError("O tamanho informado não pode ser negativo.")

    multipliers = {
        "B": 1,
        "KB": 1024,
        "MB": 1024 ** 2,
        "GB": 1024 ** 3,
        "TB": 1024 ** 4,
    }
    unit_normalized = unit.strip().upper()
    if unit_normalized not in multipliers:
        raise ValueError(f"Unidade de tamanho desconhecida: {unit}")

    return int(value * multipliers[unit_normalized])


def generate_default_filename(extension: str = ".bin") -> str:
    """
    Gera um nome de arquivo padrão e sugestivo, sempre carregando a
    marca registrada do ByteForge em seu próprio nome (ex.:
    "ByteForge-DhaaankMK_20260628_153012.bin"), reforçando a
    identificação e rastreabilidade do arquivo mesmo antes de ser
    aberto ou inspecionado.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_signature = FIXED_WATERMARK_SIGNATURE.replace(" - ", "-").replace(" ", "")
    if not extension.startswith("."):
        extension = f".{extension}"
    return f"{safe_signature}_{timestamp}{extension}"
