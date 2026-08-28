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
from typing import Any

from jarvis.providers.base import LLMProvider
from jarvis.security.executor import Acao, Executor

MAX_ITERACOES_PADRAO = 12
MAX_REPAROS_PADRAO = 2

MENSAGEM_REPARO = (
    "Sua última resposta não seguiu o protocolo de ação do JARVIS. Se quiser usar uma "
    'ferramenta, responda SOMENTE com um JSON exatamente neste formato, sem texto antes ou '
    'depois e sem crases: {{"tipo": "acao", "ferramenta": "<nome>", "argumentos": {{...}}}}. '
    'Use as chaves exatas "tipo", "ferramenta" e "argumentos" — não use "tool", "name", '
    '"args" ou "parameters".'
)


def _formatar_valor_para_llm(valor: Any) -> str:
    """Formata o retorno de uma ferramenta de forma legível para o LLM reutilizar literalmente.

    Uma lista de strings vira uma lista com marcadores em vez do `repr()` de uma lista Python —
    isso importa de verdade para ferramentas como `conhecimento.buscar`, cujo resultado já vem
    pronto para ser citado (`[arquivo § seção]: texto`); dentro do repr de uma lista, as aspas e
    escapes do Python atrapalhavam o modelo a extrair a citação exata (visto na prática, M5).
    """
    if isinstance(valor, list):
        if not valor:
            return "(nenhum resultado)"
        return "\n".join(f"- {item}" for item in valor)
    return repr(valor)


@dataclass(frozen=True)
class TurnoConcluido:
    resposta_final: str
    acoes_executadas: list[Acao] = field(default_factory=list)


def _argumentos_de(bloco: dict[Any, Any]) -> dict[str, object]:
    for chave in ("argumentos", "args", "arguments", "parametros", "parameters"):
        if chave in bloco and bloco[chave] is not None:
            brutos = bloco[chave]
            break
    else:
        return {}
    if isinstance(brutos, dict):
        return dict(brutos)
    if isinstance(brutos, str):
        try:
            decodificados = json.loads(brutos)
        except json.JSONDecodeError:
            return {}
        return dict(decodificados) if isinstance(decodificados, dict) else {}
    return {}


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

    if not isinstance(dado, dict):
        return None

    bloco: dict[Any, Any] = dado
    if dado.get("type") == "function" and isinstance(dado.get("function"), dict):
        bloco = dado["function"]
    elif isinstance(dado.get("function_call"), dict):
        bloco = dado["function_call"]

    nome = bloco.get("ferramenta") or bloco.get("tool") or bloco.get("name")
    if not isinstance(nome, str) or not nome:
        return None

    return {"tipo": "acao", "ferramenta": nome, "argumentos": _argumentos_de(bloco)}


def _parece_tentativa_de_acao(resposta: str) -> bool:
    """Detecta resposta que parece chamada de ferramenta malformada (p/ dar chance de corrigir)."""
    texto = resposta.strip()
    if texto.startswith("```"):
        texto = texto.strip("`").strip()
    if not (texto.startswith("{") or texto.startswith("[")):
        return False
    tem_marcas = any(
        marca in texto
        for marca in (
            '"ferramenta"',
            '"argu"',
            '"tool"',
            '"tipo"',
            '"function"',
            '"name"',
            '"parameters"',
        )
    )
    if tem_marcas:
        return True
    try:
        json.loads(texto)
    except json.JSONDecodeError:
        return True
    return False


def processar_turno(
    provider: LLMProvider,
    executor: Executor,
    mensagem_usuario: str,
    max_iteracoes: int = MAX_ITERACOES_PADRAO,
    max_reparos: int = MAX_REPAROS_PADRAO,
) -> TurnoConcluido:
    acoes_executadas: list[Acao] = []
    reparos_restantes = max_reparos
    resposta = provider.enviar(mensagem_usuario)

    for _ in range(max_iteracoes):
        dado_acao = _extrair_acao(resposta)
        if dado_acao is None:
            if reparos_restantes > 0 and _parece_tentativa_de_acao(resposta):
                reparos_restantes -= 1
                resposta = provider.enviar(MENSAGEM_REPARO)
                continue
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
                f"Resultado de {acao.ferramenta}:\n{_formatar_valor_para_llm(resultado.valor)}\n"
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
