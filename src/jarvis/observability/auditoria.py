"""Registro de auditoria append-only de todas as ações do agente."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RegistroAuditoria:
    """Uma entrada imutável de auditoria: o que foi feito, quando e com qual resultado.

    `indice` é o número estável da entrada no arquivo append-only — diferente da
    posição numa listagem, ele não muda quando novas entradas chegam, então
    `jarvis why <indice>` continua apontando para a mesma ação entre sessões.
    """

    acao: str
    argumentos_seguros: dict[str, Any]
    resultado: str
    duracao_segundos: float
    custo_estimado_usd: float = 0.0
    quando: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    indice: int | None = None

    def para_linha_jsonl(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class RegistradorAuditoria:
    """Anexa registros de auditoria a um arquivo JSONL, nunca sobrescrevendo o anterior."""

    def __init__(self, caminho_jsonl: Path) -> None:
        self._caminho = caminho_jsonl
        self._caminho.parent.mkdir(parents=True, exist_ok=True)

    def registrar(self, registro: RegistroAuditoria) -> None:
        registro = replace(registro, indice=self._proximo_indice())
        with self._caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write(registro.para_linha_jsonl() + "\n")

    def ler_todos(self) -> list[RegistroAuditoria]:
        if not self._caminho.exists():
            return []
        registros = []
        contador = 0
        with self._caminho.open(encoding="utf-8") as arquivo:
            for linha in arquivo:
                linha = linha.strip()
                if not linha:
                    continue
                contador += 1
                dados = json.loads(linha)
                if dados.get("indice") is None:
                    dados["indice"] = contador
                registros.append(RegistroAuditoria(**dados))
        return registros

    def _proximo_indice(self) -> int:
        if not self._caminho.exists():
            return 1
        proximo = 0
        contador = 0
        with self._caminho.open(encoding="utf-8") as arquivo:
            for linha in arquivo:
                linha = linha.strip()
                if not linha:
                    continue
                contador += 1
                indice = 0
                try:
                    indice = int(json.loads(linha).get("indice") or 0)
                except (json.JSONDecodeError, TypeError, ValueError):
                    indice = 0
                proximo = max(proximo, contador, indice)
        return proximo + 1
