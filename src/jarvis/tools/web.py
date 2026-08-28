"""Ferramentas de busca externa do JARVIS: Second Brain primeiro, web como complemento.

`pesquisar` é a ferramenta principal de conhecimento: consulta primeiro o conhecimento local
indexado (FTS5) e só cai na web (DuckDuckGo, sem chave) quando não há resultado local — a
fonte principal de resposta é sempre o Second Brain do usuário. `web.buscar` fica exposta
separada para pesquisa web explícita (conteúdo externo que o conhecimento local não cobre).

Ambas são READ_ONLY; o transporte de rede vive em `io/web.py` e é injetável nos testes
(abrir=None usa a rede real). Sem internet (ou DuckDuckGo inacessível) a falha de rede é
convertida em mensagem amigável — o agente segue respondendo com o que o conhecimento local
tiver, em vez de a ferramenta falhar. Nada aqui decide permissão.
"""

from __future__ import annotations

from typing import Any

from jarvis.io.web import ErroBuscaWeb, Transporte, buscar_web
from jarvis.memory.conhecimento import RepositorioConhecimento
from jarvis.tools.base import Ferramenta, NivelRisco

MENSAGEM_SEM_CONEXAO = (
    "web indisponível ({motivo}) — sem conexão não há busca web; use apenas o "
    "conhecimento local (Second Brain)"
)

SCHEMA_BUSCAR = {
    "type": "object",
    "properties": {
        "consulta": {"type": "string"},
        "limite": {"type": "integer"},
    },
    "required": ["consulta"],
    "additionalProperties": False,
}


def _formatar_resultados_web(
    consulta: str, limite: int, timeout: int, abrir: Transporte | None
) -> list[str]:
    try:
        resultados = buscar_web(consulta, limite=limite, timeout=timeout, abrir=abrir)
    except ErroBuscaWeb as erro:
        return [MENSAGEM_SEM_CONEXAO.format(motivo=erro)]
    if not resultados:
        return [f"web sem resultados para: {consulta}"]
    return [
        f"web: {resultado.titulo} — {resultado.url}."
        + (f" {resultado.trecho}" if resultado.trecho else "")
        for resultado in resultados
    ]


def criar_ferramentas_pesquisa(
    repositorio: RepositorioConhecimento,
    abrir: Transporte | None = None,
    timeout_segundos: int = 15,
    limite_padrao: int = 4,
) -> list[Ferramenta]:
    def _pesquisar(argumentos: dict[str, Any]) -> list[str]:
        consulta = argumentos["consulta"]
        limite = argumentos.get("limite", limite_padrao)
        trechos = repositorio.buscar(consulta, limite=limite)
        if trechos:
            return [f"{trecho.citacao()}: {trecho.texto}" for trecho in trechos]
        return _formatar_resultados_web(consulta, limite, timeout_segundos, abrir)

    def _buscar_na_web(argumentos: dict[str, Any]) -> list[str]:
        consulta = argumentos["consulta"]
        limite = argumentos.get("limite", limite_padrao)
        return _formatar_resultados_web(consulta, limite, timeout_segundos, abrir)

    return [
        Ferramenta(
            nome="pesquisar",
            descricao=(
                "Busca de conhecimento: consulta PRIMEIRO o Second Brain local (documentos "
                "indexados em conhecimento.diretorios) e só usa a web (DuckDuckGo, sem chave) "
                "se não houver resultado local. Cite exatamente '[arquivo § seção]' quando a "
                "resposta vier do Second Brain e a URL quando vier da web."
            ),
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_BUSCAR,
            executar=_pesquisar,
        ),
        Ferramenta(
            nome="web.buscar",
            descricao=(
                "Busca na web (DuckDuckGo, sem chave de API) por conteúdo externo não coberto "
                "pelo conhecimento local. Devolve um resultado por linha: título, URL e trecho."
            ),
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_BUSCAR,
            executar=_buscar_na_web,
        ),
    ]