"""Registro de auditoria append-only de todas as ações do agente."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RegistroAuditoria:
    """Uma entrada imutável de auditoria: o que foi feito, quando e com qual resultado."""

    acao: str
    argumentos_seguros: dict[str, Any]
    resultado: str
    duracao_segundos: float
    custo_estimado_usd: float = 0.0
    quando: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def para_linha_jsonl(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class RegistradorAuditoria:
    """Anexa registros de auditoria a um arquivo JSONL, nunca sobrescrevendo o anterior."""

    def __init__(self, caminho_jsonl: Path) -> None:
        self._caminho = caminho_jsonl
        self._caminho.parent.mkdir(parents=True, exist_ok=True)

    def registrar(self, registro: RegistroAuditoria) -> None:
        with self._caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write(registro.para_linha_jsonl() + "\n")

    def ler_todos(self) -> list[RegistroAuditoria]:
        if not self._caminho.exists():
            return []
        registros = []
        with self._caminho.open(encoding="utf-8") as arquivo:
            for linha in arquivo:
                linha = linha.strip()
                if not linha:
                    continue
                dados = json.loads(linha)
                registros.append(RegistroAuditoria(**dados))
        return registros
