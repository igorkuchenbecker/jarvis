"""Executor de ações do JARVIS: única porta de entrada para qualquer ferramenta rodar de fato.

O modelo (LLM) nunca executa nada diretamente — ele só propõe uma Acao{ferramenta, argumentos}.
Este módulo valida schema e caminhos (jail) em CÓDIGO antes de deixar qualquer coisa rodar, nunca
confiando em instrução de prompt para isso.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jarvis.observability.auditoria import RegistradorAuditoria, RegistroAuditoria
from jarvis.security.jail import ErroForaDoJail, resolver_dentro_do_jail
from jarvis.security.schema import ErroValidacao, validar_schema
from jarvis.tools.registro import RegistroFerramentas


class ErroExecucao(Exception):
    """Levantada quando uma ação é recusada antes mesmo de tentar rodar a ferramenta."""


@dataclass(frozen=True)
class Acao:
    ferramenta: str
    argumentos: dict[str, Any]


@dataclass(frozen=True)
class ResultadoAcao:
    sucesso: bool
    valor: Any = None
    erro: str | None = None
    estado_anterior: Any = None


class Executor:
    def __init__(
        self,
        registro: RegistroFerramentas,
        jail_paths: list[Path],
        auditoria: RegistradorAuditoria | None = None,
    ) -> None:
        self._registro = registro
        self._jail_paths = jail_paths
        self._auditoria = auditoria

    def executar_acao(self, acao: Acao) -> ResultadoAcao:
        inicio = time.monotonic()
        try:
            resultado = self._executar_validado(acao)
        except (ErroExecucao, ErroValidacao, ErroForaDoJail) as erro:
            resultado = ResultadoAcao(sucesso=False, erro=str(erro))
        except Exception as erro:  # a ferramenta existe e passou na validação, mas falhou ao rodar
            resultado = ResultadoAcao(sucesso=False, erro=str(erro))

        self._registrar_auditoria(acao, resultado, time.monotonic() - inicio)
        return resultado

    def _executar_validado(self, acao: Acao) -> ResultadoAcao:
        ferramenta = self._registro.obter(acao.ferramenta)
        if ferramenta is None:
            raise ErroExecucao(f"ferramenta desconhecida: {acao.ferramenta}")

        validar_schema(acao.argumentos, ferramenta.schema_argumentos)

        for campo in ferramenta.campos_caminho:
            resolver_dentro_do_jail(acao.argumentos[campo], self._jail_paths)

        estado_anterior = (
            ferramenta.capturar_estado(acao.argumentos) if ferramenta.capturar_estado else None
        )
        valor = ferramenta.executar(acao.argumentos)
        return ResultadoAcao(sucesso=True, valor=valor, estado_anterior=estado_anterior)

    def reverter(self, acao: Acao, estado_anterior: Any) -> None:
        ferramenta = self._registro.obter(acao.ferramenta)
        if ferramenta is None or ferramenta.reverter is None:
            raise ErroExecucao(f"ferramenta '{acao.ferramenta}' não suporta reversão")
        ferramenta.reverter(acao.argumentos, estado_anterior)

    def _registrar_auditoria(self, acao: Acao, resultado: ResultadoAcao, duracao: float) -> None:
        if self._auditoria is None:
            return
        self._auditoria.registrar(
            RegistroAuditoria(
                acao=acao.ferramenta,
                argumentos_seguros=acao.argumentos,
                resultado="sucesso" if resultado.sucesso else f"erro: {resultado.erro}",
                duracao_segundos=duracao,
            )
        )
