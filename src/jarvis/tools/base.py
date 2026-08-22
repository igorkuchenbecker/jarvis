"""Contrato comum de toda ferramenta que o executor do JARVIS pode rodar.

O modelo (LLM) nunca executa nada diretamente — ele só propõe uma Acao{ferramenta, argumentos}.
Cada Ferramenta aqui é só dados + funções puras; quem decide se pode rodar é o executor
(jarvis.security.executor), nunca a própria ferramenta nem o prompt.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class NivelRisco(IntEnum):
    READ_ONLY = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class Ferramenta:
    nome: str
    descricao: str
    risco: NivelRisco
    schema_argumentos: dict[str, Any]
    executar: Callable[[dict[str, Any]], Any]
    campos_caminho: tuple[str, ...] = ()
    capturar_estado: Callable[[dict[str, Any]], Any] | None = None
    reverter: Callable[[dict[str, Any], Any], None] | None = None
