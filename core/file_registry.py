"""
core/file_registry.py
-------------------------

Módulo responsável por manter um registro persistente de todos os
arquivos gerados pelo ByteForge, permitindo:

    * Saber exatamente quantos arquivos já foram criados pelo
      software ao longo do tempo (contador histórico, que nunca
      diminui, mesmo que arquivos sejam posteriormente excluídos).
    * Listar, no "Gerenciador de Arquivos" da interface, todos os
      arquivos atualmente registrados, incluindo detecção de
      arquivos que foram removidos manualmente pelo usuário fora do
      ByteForge (status "ausente").
    * Excluir um arquivo do disco e/ou apenas removê-lo do registro.
    * Alterar ("editar") o tamanho de um arquivo já existente,
      regenerando seu conteúdo (com nova marca d'água) no mesmo
      caminho, através do módulo `file_generator`.

Os dados são persistidos em `data/file_registry.json`.
"""

from __future__ import annotations

import os
import json
import uuid
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional

from core.paths import FILE_REGISTRY_FILE, ensure_core_directories

logger = logging.getLogger("ByteForge.file_registry")


@dataclass
class FileEntry:
    """Representa um único arquivo gerado, rastreado pelo ByteForge."""
    id: str
    path: str
    size_bytes: int
    created_at_utc: str
    last_modified_utc: str

    def exists_on_disk(self) -> bool:
        return os.path.isfile(self.path)

    def actual_size_on_disk(self) -> Optional[int]:
        try:
            return os.path.getsize(self.path)
        except OSError:
            return None


@dataclass
class _RegistryData:
    lifetime_total_created: int = 0
    entries: List[FileEntry] = field(default_factory=list)


def _load_raw() -> _RegistryData:
    ensure_core_directories()

    if not FILE_REGISTRY_FILE.exists():
        return _RegistryData()

    try:
        raw = json.loads(FILE_REGISTRY_FILE.read_text(encoding="utf-8"))
        entries = [FileEntry(**entry) for entry in raw.get("entries", [])]
        return _RegistryData(
            lifetime_total_created=int(raw.get("lifetime_total_created", len(entries))),
            entries=entries,
        )
    except (json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        logger.error(
            "Registro de arquivos corrompido ou inválido (%s). "
            "Iniciando um novo registro vazio.", exc
        )
        return _RegistryData()


def _save_raw(data: _RegistryData) -> None:
    ensure_core_directories()
    payload = {
        "lifetime_total_created": data.lifetime_total_created,
        "entries": [asdict(e) for e in data.entries],
    }
    try:
        FILE_REGISTRY_FILE.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        logger.exception("Falha ao salvar o registro de arquivos: %s", exc)
        raise


def list_entries() -> List[FileEntry]:
    """Retorna a lista de todos os arquivos atualmente registrados."""
    return _load_raw().entries


def get_lifetime_total_created() -> int:
    """
    Retorna o número total de arquivos já criados pelo ByteForge
    desde a instalação, incluindo arquivos que já tenham sido
    excluídos ou removidos do registro posteriormente. Este contador
    é estritamente incremental e nunca diminui.
    """
    return _load_raw().lifetime_total_created


def get_active_entries_count() -> int:
    """Retorna a quantidade de arquivos atualmente registrados (ativos)."""
    return len(_load_raw().entries)


def register_new_file(path: str, size_bytes: int) -> FileEntry:
    """
    Registra um novo arquivo gerado pelo ByteForge, incrementando o
    contador histórico (`lifetime_total_created`) e persistindo o
    registro em disco. Deve ser chamado sempre após uma geração de
    arquivo concluída com sucesso.
    """
    data = _load_raw()
    now = datetime.now(timezone.utc).isoformat()

    entry = FileEntry(
        id=uuid.uuid4().hex,
        path=os.path.abspath(path),
        size_bytes=size_bytes,
        created_at_utc=now,
        last_modified_utc=now,
    )

    data.entries.append(entry)
    data.lifetime_total_created += 1
    _save_raw(data)

    logger.info(
        "Arquivo registrado: '%s' (%d bytes). Total histórico: %d.",
        entry.path, entry.size_bytes, data.lifetime_total_created,
    )
    return entry


def update_entry_after_resize(entry_id: str, new_size_bytes: int) -> Optional[FileEntry]:
    """
    Atualiza os metadados de um arquivo já registrado após ele ter
    sido regenerado com um novo tamanho (operação de "editar
    tamanho" no Gerenciador de Arquivos). NÃO realiza a regeneração
    em si — apenas atualiza o registro após a regeneração já ter
    sido concluída com sucesso pelo `file_generator`.
    """
    data = _load_raw()
    for entry in data.entries:
        if entry.id == entry_id:
            entry.size_bytes = new_size_bytes
            entry.last_modified_utc = datetime.now(timezone.utc).isoformat()
            _save_raw(data)
            logger.info("Registro atualizado após edição de tamanho: '%s' -> %d bytes.",
                        entry.path, new_size_bytes)
            return entry

    logger.warning("Tentativa de atualizar entrada inexistente no registro: id=%s", entry_id)
    return None


def remove_entry(entry_id: str, delete_file_from_disk: bool = False) -> bool:
    """
    Remove um arquivo do registro do ByteForge. Caso
    `delete_file_from_disk=True`, o arquivo físico também é excluído
    do disco (operação irreversível). Retorna True se a entrada foi
    encontrada e removida, False caso contrário.
    """
    data = _load_raw()
    target: Optional[FileEntry] = None
    for entry in data.entries:
        if entry.id == entry_id:
            target = entry
            break

    if target is None:
        logger.warning("Tentativa de remover entrada inexistente no registro: id=%s", entry_id)
        return False

    if delete_file_from_disk and target.exists_on_disk():
        try:
            os.remove(target.path)
            logger.info("Arquivo físico excluído do disco: '%s'.", target.path)
        except OSError as exc:
            logger.exception("Falha ao excluir o arquivo físico '%s': %s", target.path, exc)
            raise

    data.entries = [e for e in data.entries if e.id != entry_id]
    _save_raw(data)
    logger.info("Entrada removida do registro do ByteForge: '%s'.", target.path)
    return True


def find_entry(entry_id: str) -> Optional[FileEntry]:
    """Busca uma entrada específica do registro pelo seu identificador."""
    for entry in _load_raw().entries:
        if entry.id == entry_id:
            return entry
    return None


def purge_missing_entries() -> int:
    """
    Remove do registro (sem tocar no disco, já que os arquivos já
    não existem) todas as entradas cujo arquivo físico não seja mais
    encontrado no sistema de arquivos. Retorna a quantidade de
    entradas removidas. Útil como ação de "limpeza" no Gerenciador
    de Arquivos.
    """
    data = _load_raw()
    before = len(data.entries)
    data.entries = [e for e in data.entries if e.exists_on_disk()]
    removed = before - len(data.entries)
    if removed:
        _save_raw(data)
        logger.info("Limpeza do registro: %d entrada(s) ausente(s) removida(s).", removed)
    return removed
