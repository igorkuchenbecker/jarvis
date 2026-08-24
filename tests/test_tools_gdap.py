"""Testes das ferramentas gdap.* com ClienteGdap falso (sem rede, sem servidor GDAP real)."""

from __future__ import annotations

from typing import Any

import pytest

from jarvis.io.gdap import ClienteGdap, ErroGdap
from jarvis.tools.base import NivelRisco
from jarvis.tools.gdap import criar_ferramentas_gdap


class ClienteGdapFalso:
    """Dublê do ClienteGdap: grava chamadas, devolve respostas roteirizadas."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.resposta_status: dict[str, Any] = {
            "ok": True,
            "version": "0.1.0",
            "environment": "dev",
        }
        self.resposta_datasets: list[dict[str, Any]] = []
        self.resposta_consulta: dict[str, Any] = {"columns": [], "rows": 0, "records": []}
        self.resposta_pergunta: dict[str, Any] = {"answer": "", "confidence": 0.0, "evidence": []}
        self.resposta_pipeline: dict[str, Any] = {"state": "SUCCESS", "result": {}}

    def status(self) -> dict[str, Any]:
        self.chamadas.append(("status", (), {}))
        return self.resposta_status

    def listar_datasets(self, limite: int = 50) -> list[dict[str, Any]]:
        self.chamadas.append(("listar_datasets", (), {"limite": limite}))
        return self.resposta_datasets

    def consultar(self, sql: str, limite: int | None = None) -> dict[str, Any]:
        self.chamadas.append(("consultar", (sql,), {"limite": limite}))
        return self.resposta_consulta

    def perguntar(self, pergunta: str, dataset: str | None = None) -> dict[str, Any]:
        self.chamadas.append(("perguntar", (pergunta,), {"dataset": dataset}))
        return self.resposta_pergunta

    def executar_pipeline(
        self, nome: str, parametros: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.chamadas.append(("executar_pipeline", (nome,), {"parametros": parametros}))
        return self.resposta_pipeline


def _por_nome(cliente: ClienteGdap, pipelines_permitidos: tuple[str, ...] = ()) -> dict[str, Any]:
    return {f.nome: f for f in criar_ferramentas_gdap(cliente, pipelines_permitidos)}


def test_cria_as_cinco_ferramentas_com_nomes_e_riscos_esperados() -> None:
    ferramentas = _por_nome(ClienteGdapFalso())  # type: ignore[arg-type]

    assert set(ferramentas) == {
        "gdap.status",
        "gdap.listar_datasets",
        "gdap.consultar",
        "gdap.perguntar",
        "gdap.executar_pipeline",
    }
    for nome in ("gdap.status", "gdap.listar_datasets", "gdap.consultar", "gdap.perguntar"):
        assert ferramentas[nome].risco == NivelRisco.READ_ONLY
    assert ferramentas["gdap.executar_pipeline"].risco == NivelRisco.MEDIUM


def test_status_traduz_campos_para_portugues() -> None:
    cliente = ClienteGdapFalso()
    cliente.resposta_status = {"ok": True, "version": "1.2.3", "environment": "production"}
    ferramentas = _por_nome(cliente)  # type: ignore[arg-type]

    resultado = ferramentas["gdap.status"].executar({})

    assert resultado == {"ok": True, "versao": "1.2.3", "ambiente": "production"}


def test_listar_datasets_usa_limite_padrao_e_traduz_campos() -> None:
    cliente = ClienteGdapFalso()
    cliente.resposta_datasets = [
        {
            "name": "vendas",
            "row_count": 100,
            "quality_score": 91.4,
            "classification": "CONFIDENTIAL",
        }
    ]
    ferramentas = _por_nome(cliente)  # type: ignore[arg-type]

    resultado = ferramentas["gdap.listar_datasets"].executar({})

    assert cliente.chamadas[0] == ("listar_datasets", (), {"limite": 50})
    assert resultado == [
        {"nome": "vendas", "linhas": 100, "qualidade": 91.4, "classificacao": "CONFIDENTIAL"}
    ]


def test_listar_datasets_repassa_limite_informado() -> None:
    cliente = ClienteGdapFalso()
    ferramentas = _por_nome(cliente)  # type: ignore[arg-type]

    ferramentas["gdap.listar_datasets"].executar({"limite": 5})

    assert cliente.chamadas[0] == ("listar_datasets", (), {"limite": 5})


def test_consultar_repassa_sql_e_limite() -> None:
    cliente = ClienteGdapFalso()
    cliente.resposta_consulta = {"columns": ["n"], "rows": 1, "records": [{"n": 1}]}
    ferramentas = _por_nome(cliente)  # type: ignore[arg-type]

    resultado = ferramentas["gdap.consultar"].executar({"sql": "select 1 as n", "limite": 10})

    assert cliente.chamadas[0] == ("consultar", ("select 1 as n",), {"limite": 10})
    assert resultado == {"colunas": ["n"], "linhas": 1, "registros": [{"n": 1}]}


def test_perguntar_traduz_evidencias() -> None:
    cliente = ClienteGdapFalso()
    cliente.resposta_pergunta = {
        "answer": "receita caiu 10%",
        "confidence": 0.8,
        "evidence": [{"source": "dataset:vendas", "calculation": "sum(revenue)"}],
        "limitations": ["dado parcial do último mês"],
    }
    ferramentas = _por_nome(cliente)  # type: ignore[arg-type]

    resultado = ferramentas["gdap.perguntar"].executar(
        {"pergunta": "por que a receita caiu?", "dataset": "vendas"}
    )

    assert cliente.chamadas[0] == ("perguntar", ("por que a receita caiu?",), {"dataset": "vendas"})
    assert resultado["resposta"] == "receita caiu 10%"
    assert resultado["evidencias"] == [{"fonte": "dataset:vendas", "calculo": "sum(revenue)"}]
    assert resultado["limitacoes"] == ["dado parcial do último mês"]


def test_executar_pipeline_permitido_roda_e_traduz_resultado() -> None:
    cliente = ClienteGdapFalso()
    cliente.resposta_pipeline = {
        "state": "SUCCESS",
        "result": {"metrics": {"rows": 100}, "artifacts": ["file:///r.html"]},
    }
    ferramentas = _por_nome(cliente, pipelines_permitidos=("vendas_diarias",))  # type: ignore[arg-type]

    resultado = ferramentas["gdap.executar_pipeline"].executar(
        {"nome": "vendas_diarias", "parametros": {"dias": 7}}
    )

    assert cliente.chamadas[0] == (
        "executar_pipeline",
        ("vendas_diarias",),
        {"parametros": {"dias": 7}},
    )
    assert resultado == {
        "estado": "SUCCESS",
        "metricas": {"rows": 100},
        "artefatos": ["file:///r.html"],
    }


def test_executar_pipeline_fora_da_allowlist_e_recusado_sem_chamar_o_gdap() -> None:
    """Teste 'malicioso' da convenção do projeto: um pipeline fora da allowlist configurada
    nunca deve chegar a bater na API do GDAP, mesmo que o LLM peça — mesmo espírito do teste de
    travessia de jail e do binário fora da allowlist em terminal.exec.
    """
    cliente = ClienteGdapFalso()
    ferramentas = _por_nome(cliente, pipelines_permitidos=("vendas_diarias",))  # type: ignore[arg-type]

    with pytest.raises(ErroGdap, match="não está na allowlist"):
        ferramentas["gdap.executar_pipeline"].executar({"nome": "apagar_tudo"})

    assert cliente.chamadas == []


def test_executar_pipeline_com_allowlist_vazia_recusa_qualquer_nome() -> None:
    cliente = ClienteGdapFalso()
    ferramentas = _por_nome(cliente)  # type: ignore[arg-type]

    with pytest.raises(ErroGdap, match=r"\(vazia\)"):
        ferramentas["gdap.executar_pipeline"].executar({"nome": "qualquer"})


def test_erro_do_cliente_propaga_para_quem_chamou_a_ferramenta() -> None:
    class ClienteQueFalha:
        def status(self) -> dict[str, Any]:
            raise ErroGdap("não consegui conectar ao GDAP em http://127.0.0.1:8000")

    ferramentas = _por_nome(ClienteQueFalha())  # type: ignore[arg-type]

    with pytest.raises(ErroGdap, match="não consegui conectar"):
        ferramentas["gdap.status"].executar({})
