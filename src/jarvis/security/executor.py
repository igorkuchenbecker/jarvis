"""Executor de ações do JARVIS: única porta de entrada para qualquer ferramenta rodar de fato.

O modelo (LLM) nunca executa nada diretamente — ele só propõe uma Acao{ferramenta, argumentos}.
Este módulo valida schema, jail de caminho, allowlist de binário e nível de autonomia em CÓDIGO
antes de deixar qualquer coisa rodar, nunca confiando em instrução de prompt para isso.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jarvis.observability.auditoria import RegistradorAuditoria, RegistroAuditoria
from jarvis.security.allowlist import ErroForaDaAllowlist, validar_binario_permitido
from jarvis.security.jail import ErroForaDoJail, resolver_dentro_do_jail
from jarvis.security.schema import ErroValidacao, validar_schema
from jarvis.tools.base import Ferramenta, NivelRisco
from jarvis.tools.registro import RegistroFerramentas

TETO_RISCO_POR_AUTONOMIA: dict[int, NivelRisco | None] = {
    0: None,
    1: NivelRisco.READ_ONLY,
    2: NivelRisco.LOW,
    3: NivelRisco.MEDIUM,
    4: NivelRisco.MEDIUM,
    5: NivelRisco.MEDIUM,
}


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
        allowlist_binarios: tuple[str, ...] = (),
        nivel_autonomia: int = 2,
        solicitar_aprovacao: Callable[[Acao, Ferramenta], bool] | None = None,
        auditoria: RegistradorAuditoria | None = None,
    ) -> None:
        self._registro = registro
        self._jail_paths = jail_paths
        self._allowlist_binarios = allowlist_binarios
        self._nivel_autonomia = nivel_autonomia
        self._solicitar_aprovacao = solicitar_aprovacao
        self._auditoria = auditoria

    def executar_acao(self, acao: Acao) -> ResultadoAcao:
        inicio = time.monotonic()
        try:
            resultado = self._executar_validado(acao)
        except (ErroExecucao, ErroValidacao, ErroForaDoJail, ErroForaDaAllowlist) as erro:
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

        if ferramenta.campo_binario is not None:
            validar_binario_permitido(
                acao.argumentos[ferramenta.campo_binario], self._allowlist_binarios
            )

        self._verificar_autonomia_e_aprovacao(acao, ferramenta)

        estado_anterior = (
            ferramenta.capturar_estado(acao.argumentos) if ferramenta.capturar_estado else None
        )
        valor = ferramenta.executar(acao.argumentos)
        return ResultadoAcao(sucesso=True, valor=valor, estado_anterior=estado_anterior)

    def _verificar_autonomia_e_aprovacao(self, acao: Acao, ferramenta: Ferramenta) -> None:
        if ferramenta.risco >= NivelRisco.HIGH:
            aprovado = (
                self._solicitar_aprovacao(acao, ferramenta)
                if self._solicitar_aprovacao is not None
                else False
            )
            if not aprovado:
                raise ErroExecucao(
                    f"ação de risco {ferramenta.risco.name} exige aprovação humana e não foi "
                    "aprovada"
                )
            return

        teto = TETO_RISCO_POR_AUTONOMIA.get(self._nivel_autonomia)
        if teto is None or ferramenta.risco > teto:
            raise ErroExecucao(
                f"nível de autonomia atual ({self._nivel_autonomia}) não permite ações de risco "
                f"{ferramenta.risco.name}"
            )

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
