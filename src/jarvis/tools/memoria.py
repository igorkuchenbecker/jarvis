"""Ferramentas de memória: guardar um texto e buscá-lo depois por relevância (FTS5)."""

from __future__ import annotations

from typing import Any

from jarvis.memory.armazenamento import RepositorioMemoria
from jarvis.tools.base import Ferramenta, NivelRisco

SCHEMA_MEMORY_STORE = {
    "type": "object",
    "properties": {"texto": {"type": "string"}},
    "required": ["texto"],
    "additionalProperties": False,
}

SCHEMA_MEMORY_SEARCH = {
    "type": "object",
    "properties": {
        "consulta": {"type": "string"},
        "limite": {"type": "integer"},
    },
    "required": ["consulta"],
    "additionalProperties": False,
}


def criar_ferramentas_memoria(repositorio: RepositorioMemoria) -> list[Ferramenta]:
    def _armazenar(argumentos: dict[str, Any]) -> str:
        repositorio.armazenar(argumentos["texto"])
        return "memorizado"

    def _buscar(argumentos: dict[str, Any]) -> list[str]:
        limite = argumentos.get("limite", 5)
        return repositorio.buscar(argumentos["consulta"], limite=limite)

    return [
        Ferramenta(
            nome="memory.store",
            descricao="Guarda um texto na memória persistente do JARVIS.",
            risco=NivelRisco.LOW,
            schema_argumentos=SCHEMA_MEMORY_STORE,
            executar=_armazenar,
        ),
        Ferramenta(
            nome="memory.search",
            descricao="Busca textos guardados na memória persistente por relevância.",
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_MEMORY_SEARCH,
            executar=_buscar,
        ),
    ]
