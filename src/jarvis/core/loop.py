"""Loop mínimo de tool-calling para o M2.

Isto NÃO é o loop completo de goals do M4 (sem decomposição em subtarefas, replanning ou
checkpoints em SQLite) — é só o suficiente para o LLM pedir para uma ferramenta rodar, ver o
resultado, e decidir se chama outra ou responde ao usuário em texto, com um teto de iterações
por segurança (mesmo espírito do limite de M4, adotado cedo porque sem ele um loop de ação
já é perigoso).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from jarvis.providers.base import LLMProvider
from jarvis.security.executor import Acao, Executor

MAX_ITERACOES_PADRAO = 12


@dataclass(frozen=True)
class TurnoConcluido:
    resposta_final: str
    acoes_executadas: list[Acao] = field(default_factory=list)


def _extrair_acao(resposta: str) -> dict[str, object] | None:
    texto = resposta.strip()
    if texto.startswith("```"):
        texto = texto.strip("`").strip()
        if texto.startswith("json"):
            texto = texto[len("json") :].strip()

    try:
        dado = json.loads(texto)
    except json.JSONDecodeError:
        return None

    if isinstance(dado, dict) and dado.get("tipo") == "acao":
        return dado
    return None


def processar_turno(
    provider: LLMProvider,
    executor: Executor,
    mensagem_usuario: str,
    max_iteracoes: int = MAX_ITERACOES_PADRAO,
) -> TurnoConcluido:
    acoes_executadas: list[Acao] = []
    resposta = provider.enviar(mensagem_usuario)

    for _ in range(max_iteracoes):
        dado_acao = _extrair_acao(resposta)
        if dado_acao is None:
            return TurnoConcluido(resposta_final=resposta, acoes_executadas=acoes_executadas)

        argumentos_brutos = dado_acao.get("argumentos") or {}
        if not isinstance(argumentos_brutos, dict):
            argumentos_brutos = {}
        acao = Acao(
            ferramenta=str(dado_acao.get("ferramenta")),
            argumentos=dict(argumentos_brutos),
        )
        resultado = executor.executar_acao(acao)
        acoes_executadas.append(acao)

        if resultado.sucesso:
            mensagem_resultado = (
                f"Resultado de {acao.ferramenta}: {resultado.valor!r}. "
                "Se precisar de outra ferramenta, responda com outro JSON de ação; "
                "senão, responda ao usuário em texto normal."
            )
        else:
            mensagem_resultado = (
                f"A ferramenta {acao.ferramenta} falhou: {resultado.erro}. "
                "Ajuste e tente de novo, ou explique o problema ao usuário em texto normal."
            )

        resposta = provider.enviar(mensagem_resultado)

    return TurnoConcluido(resposta_final=resposta, acoes_executadas=acoes_executadas)
