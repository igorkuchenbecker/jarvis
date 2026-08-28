"""Loop de objetivos (goals) do M4: decompõe em subtarefas, executa cada uma com
`core.loop.processar_turno`, detecta falha pelo próprio texto de resposta, replaneja o restante
quando falha, e persiste checkpoint a cada subtarefa concluída — retomável após um crash do
processo (`RepositorioObjetivos.obter_em_andamento`).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from jarvis.core.loop import MAX_ITERACOES_PADRAO, MAX_REPAROS_PADRAO, processar_turno
from jarvis.core.objetivos import RepositorioObjetivos, Subtarefa
from jarvis.providers.base import ErroProvider, LLMProvider
from jarvis.security.executor import Executor

MAX_REPLANEJAMENTOS_PADRAO = 3

PROMPT_PLANEJAR = (
    "Decomponha o objetivo a seguir em uma lista curta de subtarefas sequenciais e concretas. "
    "Responda SOMENTE com um JSON exatamente neste formato, sem texto antes ou depois:\n"
    '{{"tipo": "plano", "subtarefas": [{{"descricao": "...", "criterio_sucesso": "..."}}]}}\n'
    "Objetivo: {objetivo}"
)

PROMPT_SUBTAREFA = (
    "Subtarefa atual: {descricao}\n"
    "Critério de sucesso: {criterio_sucesso}\n"
    "Cumpra essa subtarefa (usando ferramentas se precisar) e termine sua resposta final com "
    "'SUCESSO: <resumo>' se o critério foi atendido, ou 'FALHA: <motivo>' se não conseguiu."
)

PROMPT_REPLANEJAR = (
    "A subtarefa '{descricao_falha}' falhou: {motivo_falha}\n"
    "Objetivo original: {objetivo}\n"
    "Gere uma nova lista de subtarefas para tentar cumprir o objetivo a partir daqui — pode "
    "incluir uma abordagem diferente para o que falhou. Responda SOMENTE com um JSON no mesmo "
    'formato: {{"tipo": "plano", "subtarefas": '
    '[{{"descricao": "...", "criterio_sucesso": "..."}}]}}'
)


@dataclass(frozen=True)
class ObjetivoConcluido:
    id: str
    estado: str  # concluido | falhou
    subtarefas: list[Subtarefa] = field(default_factory=list)


def _extrair_plano(resposta: str) -> list[Subtarefa] | None:
    texto = resposta.strip()
    if texto.startswith("```"):
        texto = texto.strip("`").strip()
        if texto.startswith("json"):
            texto = texto[len("json") :].strip()

    try:
        dado: Any = json.loads(texto)
    except json.JSONDecodeError:
        return None

    if not isinstance(dado, dict) or dado.get("tipo") != "plano":
        return None
    subtarefas_brutas = dado.get("subtarefas")
    if not isinstance(subtarefas_brutas, list):
        return None

    return [
        Subtarefa(
            descricao=str(item.get("descricao", "")),
            criterio_sucesso=str(item.get("criterio_sucesso", "")),
        )
        for item in subtarefas_brutas
        if isinstance(item, dict)
    ]


def _solicitar_plano(provider: LLMProvider, prompt: str) -> list[Subtarefa]:
    resposta = provider.enviar(prompt)
    plano = _extrair_plano(resposta)
    if not plano:
        raise ErroProvider(
            "não consegui decompor o objetivo em subtarefas: resposta inesperada: "
            f"{resposta[:200]!r}"
        )
    return plano


def planejar(provider: LLMProvider, objetivo: str) -> list[Subtarefa]:
    return _solicitar_plano(provider, PROMPT_PLANEJAR.format(objetivo=objetivo))


def _avaliar_resultado_subtarefa(resposta_final: str) -> tuple[bool, str]:
    texto = resposta_final.strip()
    if "FALHA" in texto.upper():
        return False, texto
    return True, texto


def executar_objetivo(
    provider: LLMProvider,
    executor: Executor,
    repositorio: RepositorioObjetivos,
    descricao_objetivo: str,
    max_replanejamentos: int = MAX_REPLANEJAMENTOS_PADRAO,
    max_iteracoes: int = MAX_ITERACOES_PADRAO,
    max_reparos: int = MAX_REPAROS_PADRAO,
    ao_progredir: Callable[[str], None] | None = None,
) -> ObjetivoConcluido:
    aviso = ao_progredir or (lambda mensagem: None)

    objetivo = repositorio.obter_em_andamento()
    if objetivo is None:
        subtarefas = planejar(provider, descricao_objetivo)
        id_objetivo = repositorio.criar(descricao_objetivo, subtarefas)
        objetivo_recem_criado = repositorio.obter(id_objetivo)
        assert objetivo_recem_criado is not None
        objetivo = objetivo_recem_criado
    else:
        aviso(f"retomando objetivo em andamento na subtarefa {objetivo.indice_atual + 1}")

    while objetivo.indice_atual < len(objetivo.subtarefas):
        subtarefa = objetivo.subtarefas[objetivo.indice_atual]
        aviso(
            f"subtarefa {objetivo.indice_atual + 1}/{len(objetivo.subtarefas)}: "
            f"{subtarefa.descricao}"
        )

        turno = processar_turno(
            provider,
            executor,
            PROMPT_SUBTAREFA.format(
                descricao=subtarefa.descricao, criterio_sucesso=subtarefa.criterio_sucesso
            ),
            max_iteracoes=max_iteracoes,
            max_reparos=max_reparos,
        )
        sucesso, detalhe = _avaliar_resultado_subtarefa(turno.resposta_final)

        if sucesso:
            subtarefa.estado = "concluida"
            objetivo.indice_atual += 1
            repositorio.salvar_checkpoint(objetivo)
            continue

        subtarefa.estado = "falhou"
        objetivo.replanejamentos += 1
        if objetivo.replanejamentos > max_replanejamentos:
            objetivo.estado = "falhou"
            repositorio.salvar_checkpoint(objetivo)
            return ObjetivoConcluido(
                id=objetivo.id, estado="falhou", subtarefas=objetivo.subtarefas
            )

        aviso(f"subtarefa falhou ({detalhe}); replanejando...")
        novo_plano = _solicitar_plano(
            provider,
            PROMPT_REPLANEJAR.format(
                descricao_falha=subtarefa.descricao,
                motivo_falha=detalhe,
                objetivo=descricao_objetivo,
            ),
        )
        objetivo.subtarefas = objetivo.subtarefas[: objetivo.indice_atual] + novo_plano
        repositorio.salvar_checkpoint(objetivo)

    objetivo.estado = "concluido"
    repositorio.salvar_checkpoint(objetivo)
    return ObjetivoConcluido(id=objetivo.id, estado="concluido", subtarefas=objetivo.subtarefas)
