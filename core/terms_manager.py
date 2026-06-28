"""
core/terms_manager.py
-------------------------

Módulo responsável por controlar a exibição e o registro de aceite
do Termo de Responsabilidade do ByteForge.

Regra de negócio:
    * Na primeira execução, o usuário deve ler e marcar a caixa de
      concordância do termo antes de poder utilizar qualquer
      funcionalidade do aplicativo.
    * Uma vez aceito, o aceite é persistido em disco (arquivo
      `data/terms_acceptance.json`) junto com a data/hora e a versão
      do termo aceito, e o termo não é exibido novamente nas
      execuções seguintes — a menos que o texto do termo seja
      atualizado para uma nova versão (`TERMS_VERSION`), cenário em
      que um novo aceite passa a ser exigido.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from core.paths import DATA_DIR, ensure_core_directories

logger = logging.getLogger("ByteForge.terms_manager")

TERMS_ACCEPTANCE_FILE = DATA_DIR / "terms_acceptance.json"

# Versão atual do termo de responsabilidade. Caso o texto do termo
# seja alterado de forma relevante em uma atualização futura, este
# número deve ser incrementado, o que automaticamente invalida
# aceites anteriores e exige um novo aceite explícito do usuário.
TERMS_VERSION: str = "1.0"

TERMS_TEXT: str = """\
TERMO DE RESPONSABILIDADE E ISENÇÃO DE GARANTIAS — BYTEFORGE

Ao utilizar o ByteForge, você declara estar de acordo com os termos
abaixo:

1. FINALIDADE DO SOFTWARE
   O ByteForge é uma ferramenta destinada à geração de arquivos de
   preenchimento ("dummy files") de tamanho definido pelo usuário,
   para fins de teste, simulação de carga de armazenamento, backup
   e demais usos legítimos.

2. ISENÇÃO DE RESPONSABILIDADE
   O ByteForge é fornecido "como está" ("as is"), sem qualquer
   garantia expressa ou implícita. O desenvolvedor (DhaaankMK) NÃO
   se responsabiliza por qualquer dano, perda de dados, perda de
   desempenho, indisponibilidade de espaço em disco, instabilidade
   do sistema operacional ou qualquer outro prejuízo direto ou
   indireto decorrente do uso, mau uso, ou impossibilidade de uso
   deste software — mesmo que o ByteForge não apresente, em si,
   qualquer ameaça, falha de segurança ou código malicioso conhecido.

3. RESPONSABILIDADE DO USUÁRIO
   É de responsabilidade exclusiva do usuário verificar se possui
   espaço em disco adequado, realizar backups de seus dados antes de
   operações em massa, e utilizar o software de forma consciente.
   O ByteForge inclui mecanismos de segurança (como a verificação de
   espaço mínimo livre em disco), mas estes não substituem o bom
   senso e a prudência do usuário.

4. ACEITE
   Ao marcar a caixa de confirmação abaixo e clicar em "Li e
   Concordo", você confirma que leu, compreendeu e concorda
   integralmente com este Termo de Responsabilidade, podendo então
   utilizar o ByteForge livremente.
"""


@dataclass
class TermsAcceptanceRecord:
    accepted: bool
    accepted_version: Optional[str] = None
    accepted_at_utc: Optional[str] = None


def has_accepted_current_terms() -> bool:
    """
    Verifica se o usuário já aceitou a versão atual do termo de
    responsabilidade. Retorna False também em caso de arquivo
    inexistente, corrompido, ou se o aceite registrado se refere a
    uma versão antiga do termo.
    """
    record = _load_acceptance_record()
    return bool(record.accepted and record.accepted_version == TERMS_VERSION)


def register_acceptance() -> None:
    """
    Registra, de forma persistente, que o usuário leu e concordou
    com a versão atual do Termo de Responsabilidade, incluindo a
    data/hora exata (UTC) do aceite.
    """
    ensure_core_directories()
    record = TermsAcceptanceRecord(
        accepted=True,
        accepted_version=TERMS_VERSION,
        accepted_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    try:
        TERMS_ACCEPTANCE_FILE.write_text(
            json.dumps(record.__dict__, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(
            "Termo de Responsabilidade (versão %s) aceito pelo usuário em %s.",
            record.accepted_version, record.accepted_at_utc,
        )
    except OSError as exc:
        logger.exception("Falha ao registrar aceite do Termo de Responsabilidade: %s", exc)
        raise


def _load_acceptance_record() -> TermsAcceptanceRecord:
    ensure_core_directories()
    if not TERMS_ACCEPTANCE_FILE.exists():
        return TermsAcceptanceRecord(accepted=False)

    try:
        raw = json.loads(TERMS_ACCEPTANCE_FILE.read_text(encoding="utf-8"))
        return TermsAcceptanceRecord(
            accepted=bool(raw.get("accepted", False)),
            accepted_version=raw.get("accepted_version"),
            accepted_at_utc=raw.get("accepted_at_utc"),
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning(
            "Arquivo de aceite de termos corrompido (%s). Será solicitado novo aceite.", exc
        )
        return TermsAcceptanceRecord(accepted=False)
