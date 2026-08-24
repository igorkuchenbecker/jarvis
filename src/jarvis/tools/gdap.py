"""Ferramentas de integração com o GDAP (Global Data Automation Platform, projeto irmão em
~/gdap): consultar o catálogo de dados, rodar SQL de leitura, perguntar ao analista de IA do
GDAP e disparar pipelines de dados já cadastrados.

GDAP roda como servidor HTTP separado com seu próprio controle de acesso e sandbox de SQL — o
JARVIS nunca fala com o banco de dados dele diretamente, só com a API HTTP, do mesmo jeito que
qualquer outro cliente (a CLI/web UI do próprio GDAP). Ver `io/gdap.py` para o transporte.

`gdap.status`, `gdap.listar_datasets`, `gdap.consultar` e `gdap.perguntar` são READ_ONLY: o GDAP
já bloqueia INSERT/UPDATE/DELETE/DDL por padrão no seu próprio guard de SQL
(`gdap.security.sql_guard`), então mesmo uma consulta arbitrária vinda daqui não altera dado
nenhum -- na pior hipótese o GDAP recusa a chamada e devolve erro. `gdap.executar_pipeline` é
MEDIUM (roda um pipeline nomeado e pré-cadastrado no GDAP, que pode publicar novas versões de
dataset e gerar relatórios) e só aceita nomes na allowlist `gdap.pipelines_permitidos` do
config.yaml -- mesma filosofia de `terminal.exec`/`allowlist_binarios`, verificada aqui dentro
porque o Executor do JARVIS não tem um mecanismo genérico de allowlist além de binário de
terminal (ver docs/DECISOES.md).
"""

from __future__ import annotations

from typing import Any

from jarvis.io.gdap import ClienteGdap, ErroGdap
from jarvis.tools.base import Ferramenta, NivelRisco

SCHEMA_VAZIO = {"type": "object", "properties": {}, "additionalProperties": False}

SCHEMA_LISTAR_DATASETS = {
    "type": "object",
    "properties": {"limite": {"type": "integer"}},
    "additionalProperties": False,
}

SCHEMA_CONSULTAR = {
    "type": "object",
    "properties": {
        "sql": {"type": "string"},
        "limite": {"type": "integer"},
    },
    "required": ["sql"],
    "additionalProperties": False,
}

SCHEMA_PERGUNTAR = {
    "type": "object",
    "properties": {
        "pergunta": {"type": "string"},
        "dataset": {"type": "string"},
    },
    "required": ["pergunta"],
    "additionalProperties": False,
}

SCHEMA_EXECUTAR_PIPELINE = {
    "type": "object",
    "properties": {
        "nome": {"type": "string"},
        "parametros": {"type": "object"},
    },
    "required": ["nome"],
    "additionalProperties": False,
}


def _status(cliente: ClienteGdap, argumentos: dict[str, Any]) -> dict[str, Any]:
    saude = cliente.status()
    return {
        "ok": saude.get("ok", False),
        "versao": saude.get("version"),
        "ambiente": saude.get("environment"),
    }


def _listar_datasets(cliente: ClienteGdap, argumentos: dict[str, Any]) -> list[dict[str, Any]]:
    limite = int(argumentos.get("limite", 50))
    return [
        {
            "nome": item.get("name"),
            "linhas": item.get("row_count"),
            "qualidade": item.get("quality_score"),
            "classificacao": item.get("classification"),
        }
        for item in cliente.listar_datasets(limite=limite)
    ]


def _consultar(cliente: ClienteGdap, argumentos: dict[str, Any]) -> dict[str, Any]:
    resultado = cliente.consultar(argumentos["sql"], limite=argumentos.get("limite"))
    return {
        "colunas": resultado.get("columns", []),
        "linhas": resultado.get("rows", 0),
        "registros": resultado.get("records", []),
    }


def _perguntar(cliente: ClienteGdap, argumentos: dict[str, Any]) -> dict[str, Any]:
    resposta = cliente.perguntar(argumentos["pergunta"], dataset=argumentos.get("dataset"))
    return {
        "resposta": resposta.get("answer", ""),
        "confianca": resposta.get("confidence"),
        "evidencias": [
            {
                "fonte": item.get("source"),
                "calculo": item.get("calculation") or item.get("query"),
            }
            for item in resposta.get("evidence", [])
        ],
        "limitacoes": resposta.get("limitations", []),
    }


def _executar_pipeline(
    cliente: ClienteGdap, pipelines_permitidos: tuple[str, ...], argumentos: dict[str, Any]
) -> dict[str, Any]:
    nome = argumentos["nome"]
    if nome not in pipelines_permitidos:
        raise ErroGdap(
            f"pipeline '{nome}' não está na allowlist (gdap.pipelines_permitidos no "
            f"config.yaml): {', '.join(pipelines_permitidos) or '(vazia)'}"
        )
    resultado = cliente.executar_pipeline(nome, parametros=argumentos.get("parametros"))
    corpo_resultado = resultado.get("result") or {}
    return {
        "estado": resultado.get("state"),
        "metricas": corpo_resultado.get("metrics", {}),
        "artefatos": corpo_resultado.get("artifacts", []),
    }


def criar_ferramentas_gdap(
    cliente: ClienteGdap, pipelines_permitidos: tuple[str, ...] = ()
) -> list[Ferramenta]:
    return [
        Ferramenta(
            nome="gdap.status",
            descricao="Verifica se o servidor GDAP está no ar e em qual versão/ambiente.",
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_VAZIO,
            executar=lambda argumentos: _status(cliente, argumentos),
        ),
        Ferramenta(
            nome="gdap.listar_datasets",
            descricao=(
                "Lista os datasets no catálogo do GDAP (nome, linhas, score de qualidade, "
                "classificação de sensibilidade)."
            ),
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_LISTAR_DATASETS,
            executar=lambda argumentos: _listar_datasets(cliente, argumentos),
        ),
        Ferramenta(
            nome="gdap.consultar",
            descricao=(
                "Roda uma consulta SQL de leitura contra os datasets do GDAP (SELECT apenas — "
                "o GDAP bloqueia qualquer escrita/DDL no seu próprio guard de SQL, mesmo que "
                "o SQL enviado tente algo diferente)."
            ),
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_CONSULTAR,
            executar=lambda argumentos: _consultar(cliente, argumentos),
        ),
        Ferramenta(
            nome="gdap.perguntar",
            descricao=(
                "Pergunta ao analista de IA do GDAP sobre os dados (tendência, anomalia, "
                "qualidade, comparação de período etc.) — a resposta vem com evidência "
                "(fonte/cálculo) anexada, nunca um número inventado."
            ),
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_PERGUNTAR,
            executar=lambda argumentos: _perguntar(cliente, argumentos),
        ),
        Ferramenta(
            nome="gdap.executar_pipeline",
            descricao=(
                "Roda um pipeline de dados já cadastrado no GDAP até terminar (nome precisa "
                "estar na allowlist gdap.pipelines_permitidos do config.yaml)."
            ),
            risco=NivelRisco.MEDIUM,
            schema_argumentos=SCHEMA_EXECUTAR_PIPELINE,
            executar=lambda argumentos: _executar_pipeline(
                cliente, pipelines_permitidos, argumentos
            ),
        ),
    ]
