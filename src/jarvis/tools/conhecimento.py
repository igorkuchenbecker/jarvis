"""Ferramenta de busca no conhecimento local indexado (RAG leve, M5)."""

from __future__ import annotations

from typing import Any

from jarvis.memory.conhecimento import RepositorioConhecimento
from jarvis.tools.base import Ferramenta, NivelRisco

SCHEMA_BUSCAR = {
    "type": "object",
    "properties": {
        "consulta": {"type": "string"},
        "limite": {"type": "integer"},
    },
    "required": ["consulta"],
    "additionalProperties": False,
}


def criar_ferramentas_conhecimento(repositorio: RepositorioConhecimento) -> list[Ferramenta]:
    def _buscar(argumentos: dict[str, Any]) -> list[str]:
        limite = argumentos.get("limite", 5)
        trechos = repositorio.buscar(argumentos["consulta"], limite=limite)
        return [f"{trecho.citacao()}: {trecho.texto}" for trecho in trechos]

    return [
        Ferramenta(
            nome="conhecimento.buscar",
            descricao=(
                "Busca trechos relevantes nos documentos locais indexados (.md/.txt/.pdf). "
                "Cada resultado já vem no formato [caminho § seção]: texto — o caminho entre "
                "colchetes é real e pode ser lido com fs.read para contexto adicional; cite "
                "exatamente assim ao responder."
            ),
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_BUSCAR,
            executar=_buscar,
        ),
    ]
