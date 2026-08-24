"""Testes do ClienteGdap com transporte falso injetado.

Nenhum teste toca rede real: o transporte é um callable gravado nos testes (mesmo espírito do
transporte falso de `test_providers_openai_compat.py`). A camada de rede real
(`_requisitar_json`) é exercitada separadamente com urllib monkeypatchado.
"""

from __future__ import annotations

import email.message
import io
import json
import urllib.error
from typing import Any

import pytest

from jarvis.io.gdap import ClienteGdap, ErroGdap, _mensagem_erro_gdap, _requisitar_json


class TransporteFalso:
    def __init__(self, respostas: list[Any]) -> None:
        self._respostas = list(respostas)
        self.chamadas: list[tuple[str, str, dict[str, Any] | None, dict[str, str], int]] = []

    def __call__(
        self,
        url: str,
        metodo: str,
        corpo: dict[str, Any] | None,
        headers: dict[str, str],
        timeout: int,
    ) -> dict[str, Any]:
        self.chamadas.append((url, metodo, corpo, headers, timeout))
        item = self._respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        assert isinstance(item, dict)
        return item


def test_status_chama_health_e_repassa_o_corpo() -> None:
    transporte = TransporteFalso([{"ok": True, "version": "0.1.0", "environment": "development"}])
    cliente = ClienteGdap(_requisitar=transporte)

    resultado = cliente.status()

    assert resultado == {"ok": True, "version": "0.1.0", "environment": "development"}
    url, metodo, corpo, _, _ = transporte.chamadas[0]
    assert url == "http://127.0.0.1:8000/health"
    assert metodo == "GET"
    assert corpo is None


def test_base_url_com_barra_final_nao_duplica_barra() -> None:
    transporte = TransporteFalso([{}])
    cliente = ClienteGdap(base_url="http://127.0.0.1:8000/", _requisitar=transporte)

    cliente.status()

    assert transporte.chamadas[0][0] == "http://127.0.0.1:8000/health"


def test_api_key_vai_no_header_x_api_key() -> None:
    transporte = TransporteFalso([{}])
    cliente = ClienteGdap(api_key="gdap_chave_secreta", _requisitar=transporte)

    cliente.status()

    assert transporte.chamadas[0][3]["X-API-Key"] == "gdap_chave_secreta"


def test_sem_api_key_nao_tem_header_x_api_key() -> None:
    transporte = TransporteFalso([{}])
    cliente = ClienteGdap(_requisitar=transporte)

    cliente.status()

    assert "X-API-Key" not in transporte.chamadas[0][3]


def test_listar_datasets_manda_limite_na_query_e_devolve_items() -> None:
    transporte = TransporteFalso([{"items": [{"name": "vendas"}], "count": 1}])
    cliente = ClienteGdap(_requisitar=transporte)

    resultado = cliente.listar_datasets(limite=10)

    assert resultado == [{"name": "vendas"}]
    assert transporte.chamadas[0][0] == "http://127.0.0.1:8000/api/v1/datasets?limit=10"


def test_listar_datasets_tolera_resposta_sem_items() -> None:
    transporte = TransporteFalso([{}])
    cliente = ClienteGdap(_requisitar=transporte)

    assert cliente.listar_datasets() == []


def test_consultar_manda_sql_e_limite_no_corpo() -> None:
    transporte = TransporteFalso([{"columns": ["n"], "rows": 1, "records": [{"n": 1}]}])
    cliente = ClienteGdap(_requisitar=transporte)

    resultado = cliente.consultar("select 1 as n", limite=5)

    assert resultado["rows"] == 1
    _, metodo, corpo, _, _ = transporte.chamadas[0]
    assert metodo == "POST"
    assert corpo == {"sql": "select 1 as n", "limit": 5}


def test_consultar_sem_limite_nao_manda_a_chave() -> None:
    transporte = TransporteFalso([{}])
    cliente = ClienteGdap(_requisitar=transporte)

    cliente.consultar("select 1")

    assert "limit" not in transporte.chamadas[0][2]  # type: ignore[operator]


def test_perguntar_manda_pergunta_e_dataset_opcional() -> None:
    transporte = TransporteFalso([{"answer": "subiu 10%", "confidence": 0.8, "evidence": []}])
    cliente = ClienteGdap(_requisitar=transporte)

    resultado = cliente.perguntar("por que a receita caiu?", dataset="vendas")

    assert resultado["answer"] == "subiu 10%"
    _, _, corpo, _, _ = transporte.chamadas[0]
    assert corpo == {"question": "por que a receita caiu?", "dataset": "vendas"}


def test_perguntar_sem_dataset_nao_manda_a_chave() -> None:
    transporte = TransporteFalso([{}])
    cliente = ClienteGdap(_requisitar=transporte)

    cliente.perguntar("o que temos de dados?")

    assert "dataset" not in transporte.chamadas[0][2]  # type: ignore[operator]


def test_executar_pipeline_manda_params_wait_true_e_url_codificada() -> None:
    transporte = TransporteFalso([{"state": "SUCCESS", "result": {}}])
    cliente = ClienteGdap(_requisitar=transporte)

    resultado = cliente.executar_pipeline("vendas diarias", parametros={"dias": 7})

    assert resultado["state"] == "SUCCESS"
    url, metodo, corpo, _, _ = transporte.chamadas[0]
    assert url == "http://127.0.0.1:8000/api/v1/pipelines/vendas%20diarias/run"
    assert metodo == "POST"
    assert corpo == {"params": {"dias": 7}, "wait": True}


def test_mensagem_erro_gdap_extrai_o_envelope_uniforme() -> None:
    corpo = json.dumps({"error": {"code": "GDAP-3003", "message": "DROP is blocked"}})
    assert _mensagem_erro_gdap(corpo) == "DROP is blocked (GDAP-3003)"


def test_mensagem_erro_gdap_retorna_none_para_corpo_nao_reconhecido() -> None:
    assert _mensagem_erro_gdap("não é json") is None
    assert _mensagem_erro_gdap(json.dumps({"detail": "algo"})) is None


def _urlopen_falso(bruto: bytes | Exception) -> Any:
    class RespostaFalsa(io.BytesIO):
        def __enter__(self) -> RespostaFalsa:
            return self

        def __exit__(self, *args: object) -> None:
            pass

    def abrir(requisicao: Any, timeout: float) -> RespostaFalsa:
        if isinstance(bruto, Exception):
            raise bruto
        return RespostaFalsa(bruto)

    return abrir


ALVO_URLOPEN = "jarvis.io.gdap.urllib.request.urlopen"


def test_requisitar_json_converte_http_error_com_envelope_gdap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpo_erro = json.dumps({"error": {"code": "GDAP-3003", "message": "DROP is blocked"}})
    erro_http = urllib.error.HTTPError(
        "http://servidor",
        403,
        "Forbidden",
        email.message.Message(),
        io.BytesIO(corpo_erro.encode()),
    )
    monkeypatch.setattr(ALVO_URLOPEN, _urlopen_falso(erro_http))

    with pytest.raises(ErroGdap, match=r"HTTP 403.*DROP is blocked.*GDAP-3003"):
        _requisitar_json("http://servidor", "GET", None, {}, 10)


def test_requisitar_json_converte_conexao_recusada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ALVO_URLOPEN, _urlopen_falso(urllib.error.URLError("Connection refused")))

    with pytest.raises(ErroGdap, match="não consegui conectar"):
        _requisitar_json("http://servidor", "GET", None, {}, 10)


def test_requisitar_json_converte_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ALVO_URLOPEN, _urlopen_falso(TimeoutError("estourou")))

    with pytest.raises(ErroGdap, match="não respondeu em 10s"):
        _requisitar_json("http://servidor", "GET", None, {}, 10)


def test_requisitar_json_converte_nao_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ALVO_URLOPEN, _urlopen_falso(b"isso nao e json"))

    with pytest.raises(ErroGdap, match="não é JSON válido"):
        _requisitar_json("http://servidor", "GET", None, {}, 10)


def test_requisitar_json_corpo_vazio_vira_dicionario_vazio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ALVO_URLOPEN, _urlopen_falso(b""))

    assert _requisitar_json("http://servidor", "DELETE", None, {}, 10) == {}


def test_requisitar_json_envia_user_agent_proprio(monkeypatch: pytest.MonkeyPatch) -> None:
    capturado: dict[str, Any] = {}

    def abrir(requisicao: Any, timeout: float) -> Any:
        capturado["headers"] = dict(requisicao.header_items())
        return _urlopen_falso(b"{}")(requisicao, timeout)

    monkeypatch.setattr(ALVO_URLOPEN, abrir)
    _requisitar_json("http://servidor", "GET", None, {}, 10)

    assert capturado["headers"]["User-agent"].startswith("jarvis/")


def test_fabrica_recusa_quando_variavel_de_api_key_nao_existe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from jarvis.core.configuracao import Configuracao, ConfiguracaoGdap
    from jarvis.providers.base import ErroProvider
    from jarvis.tools import criar_registro_ferramentas_padrao

    monkeypatch.delenv("JARVIS_TESTE_GDAP_CHAVE_INEXISTENTE", raising=False)
    configuracao = Configuracao(
        caminhos=Configuracao().caminhos.__class__(banco_dados=tmp_path / "jarvis.db"),
        gdap=ConfiguracaoGdap(habilitada=True, api_key_env="JARVIS_TESTE_GDAP_CHAVE_INEXISTENTE"),
    )

    with pytest.raises(ErroProvider, match="JARVIS_TESTE_GDAP_CHAVE_INEXISTENTE"):
        criar_registro_ferramentas_padrao(configuracao)
