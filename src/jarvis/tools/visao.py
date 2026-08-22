"""Ferramenta de visão: captura a tela e pede ao VisionProvider para descrevê-la/analisá-la.

A captura de tela nunca é mantida em disco além do necessário para a chamada ao provider — é
apagada logo depois, sucesso ou erro. Não persiste nada na memória automaticamente: a tela pode
conter conteúdo sensível (achado na prática — ver docs/DECISOES.md), e a regra do projeto é que
fatos só são gravados com comando explícito do usuário ("lembre que..."), nunca como efeito
colateral automático de uma ferramenta de leitura. Se o usuário quiser guardar algo visto na tela,
o LLM usa `memory.store` normalmente, por decisão explícita, não por trás dos panos.
"""

from __future__ import annotations

from typing import Any

from jarvis.io.tela import ErroCaptura, capturar_tela
from jarvis.providers.base import VisionProvider
from jarvis.tools.base import Ferramenta, NivelRisco

SCHEMA_ANALISAR = {
    "type": "object",
    "properties": {"pergunta": {"type": "string"}},
    "additionalProperties": False,
}

PERGUNTA_PADRAO = "Descreva o que está na tela agora."


def criar_ferramentas_visao(provider: VisionProvider) -> list[Ferramenta]:
    def _analisar(argumentos: dict[str, Any]) -> str:
        pergunta = argumentos.get("pergunta") or PERGUNTA_PADRAO
        try:
            caminho_tela = capturar_tela()
        except ErroCaptura as erro:
            raise ValueError(str(erro)) from erro

        try:
            return provider.analisar(caminho_tela, pergunta)
        finally:
            caminho_tela.unlink(missing_ok=True)

    return [
        Ferramenta(
            nome="vision.analyze",
            descricao="Captura a tela atual e responde uma pergunta sobre o que está nela.",
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_ANALISAR,
            executar=_analisar,
        ),
    ]
