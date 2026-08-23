"""Testes do OpenAICompatProvider com transporte falso injetado.

Nenhum teste toca rede real: o transporte é um callable gravado nos testes (mesmo espírito do
executável `claude` falso dos testes do ClaudeCliProvider). A camada de rede real (_postar_json)
é exercitada separadamente com urllib monkeypatchado.
"""

import email.message
import io
import json
import urllib.error
from typing import Any

import pytest

from jarvis.providers.base import ErroProvider
from jarvis.providers.openai_compat import (
    OpenAICompatProvider,
    _extrair_conteudo,
    _postar_json,
)


class TransporteFalso:
    def __init__(self, respostas: list[Any]) -> None:
        self._respostas = list(respostas)
        self.chamadas: list[tuple[str, dict[str, Any], dict[str, str], int]] = []

    def __call__(
        self, url: str, corpo: dict[str, Any], headers: dict[str, str], timeout: int
    ) -> dict[str, Any]:
        self.chamadas.append((url, corpo, headers, timeout))
        item = self._respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        assert isinstance(item, dict)
        return item


def _resposta(texto: str) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant", "content": texto}}]}


def test_envia_mensagem_e_recebe_resposta() -> None:
    transporte = TransporteFalso([_resposta("Brasília.")])
    provider = OpenAICompatProvider(
        base_url="http://localhost:11434/v1", modelo="llama3", _postar=transporte
    )

    resposta = provider.enviar("qual é a capital do brasil?")

    assert resposta == "Brasília."
    url, corpo, _, _ = transporte.chamadas[0]
    assert url == "http://localhost:11434/v1/chat/completions"
    assert corpo["model"] == "llama3"


def test_base_url_com_barra_final_nao_duplica_barra() -> None:
    transporte = TransporteFalso([_resposta("ok")])
    provider = OpenAICompatProvider(
        base_url="http://localhost:11434/v1/", modelo="m", _postar=transporte
    )

    provider.enviar("oi")

    assert transporte.chamadas[0][0] == "http://localhost:11434/v1/chat/completions"


def test_prompt_sistema_vai_como_primeira_mensagem() -> None:
    transporte = TransporteFalso([_resposta("ok")])
    provider = OpenAICompatProvider(prompt_sistema="Você é o JARVIS.", _postar=transporte)

    provider.enviar("oi")

    mensagens = transporte.chamadas[0][1]["messages"]
    assert mensagens[0] == {"role": "system", "content": "Você é o JARVIS."}
    assert mensagens[1] == {"role": "user", "content": "oi"}


def test_historico_acumula_entre_chamadas() -> None:
    transporte = TransporteFalso([_resposta("primeira resposta"), _resposta("segunda")])
    provider = OpenAICompatProvider(_postar=transporte)

    provider.enviar("primeira mensagem")
    provider.enviar("segunda mensagem")

    mensagens = transporte.chamadas[1][1]["messages"]
    assert mensagens[1:] == [
        {"role": "user", "content": "primeira mensagem"},
        {"role": "assistant", "content": "primeira resposta"},
        {"role": "user", "content": "segunda mensagem"},
    ]


def test_reiniciar_limpa_o_historico() -> None:
    transporte = TransporteFalso([_resposta("uma"), _resposta("duas")])
    provider = OpenAICompatProvider(_postar=transporte)

    provider.enviar("antes do reiniciar")
    provider.reiniciar()
    provider.enviar("depois do reiniciar")

    mensagens = transporte.chamadas[1][1]["messages"]
    assert mensagens[1:] == [{"role": "user", "content": "depois do reiniciar"}]


def test_api_key_vai_no_header_authorization() -> None:
    transporte = TransporteFalso([_resposta("ok")])
    provider = OpenAICompatProvider(api_key="chave-secreta", _postar=transporte)

    provider.enviar("oi")

    headers = transporte.chamadas[0][2]
    assert headers["Authorization"] == "Bearer chave-secreta"


def test_sem_api_key_nao_tem_header_authorization() -> None:
    transporte = TransporteFalso([_resposta("ok")])
    provider = OpenAICompatProvider(_postar=transporte)

    provider.enviar("oi")

    assert "Authorization" not in transporte.chamadas[0][2]


def test_falha_nao_suja_o_historico() -> None:
    transporte = TransporteFalso(
        [ErroProvider("o servidor respondeu HTTP 500: boom"), _resposta("depois do erro")]
    )
    provider = OpenAICompatProvider(_postar=transporte)

    with pytest.raises(ErroProvider, match="HTTP 500"):
        provider.enviar("mensagem que falha")
    provider.enviar("mensagem que funciona")

    mensagens = transporte.chamadas[1][1]["messages"]
    assert [m["content"] for m in mensagens[1:]] == ["mensagem que funciona"]


def test_resposta_sem_choices_levanta_erro() -> None:
    transporte = TransporteFalso([{"erro": {"message": "modelo não existe"}}])
    provider = OpenAICompatProvider(_postar=transporte)

    with pytest.raises(ErroProvider, match="sem 'choices'"):
        provider.enviar("oi")


def test_resposta_sem_conteudo_textual_levanta_erro() -> None:
    transporte = TransporteFalso([{"choices": [{"message": {"role": "assistant"}}]}])
    provider = OpenAICompatProvider(_postar=transporte)

    with pytest.raises(ErroProvider, match="sem conteúdo"):
        provider.enviar("oi")


def test_extrair_conteudo_rejeita_payloads_maliciosos() -> None:
    with pytest.raises(ErroProvider):
        _extrair_conteudo({})
    with pytest.raises(ErroProvider):
        _extrair_conteudo({"choices": []})
    with pytest.raises(ErroProvider):
        _extrair_conteudo({"choices": [{"message": {"content": 42}}]})


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


ALVO_URLOPEN = "jarvis.providers.openai_compat.urllib.request.urlopen"


def test_postar_json_converte_http_error_em_erro_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    erro_http = urllib.error.HTTPError(
        "http://servidor",
        401,
        "Unauthorized",
        email.message.Message(),
        io.BytesIO(b'{"erro":"chave invalida"}'),
    )
    monkeypatch.setattr(ALVO_URLOPEN, _urlopen_falso(erro_http))

    with pytest.raises(ErroProvider, match=r"HTTP 401.*chave invalida"):
        _postar_json("http://servidor", {}, {}, 10)


def test_postar_json_converte_conexao_recusada_em_erro_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    erro_conexao = urllib.error.URLError("Connection refused")
    monkeypatch.setattr(ALVO_URLOPEN, _urlopen_falso(erro_conexao))

    with pytest.raises(ErroProvider, match="não consegui conectar"):
        _postar_json("http://servidor", {}, {}, 10)


def test_postar_json_converte_timeout_em_erro_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ALVO_URLOPEN, _urlopen_falso(TimeoutError("estourou")))

    with pytest.raises(ErroProvider, match="não respondeu em 10s"):
        _postar_json("http://servidor", {}, {}, 10)


def test_postar_json_converte_nao_json_em_erro_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ALVO_URLOPEN, _urlopen_falso(b"isso nao e json"))

    with pytest.raises(ErroProvider, match="não é JSON válido"):
        _postar_json("http://servidor", {}, {}, 10)


def test_postar_json_retorna_dicionario_parseado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ALVO_URLOPEN, _urlopen_falso(json.dumps({"ok": True}).encode()))

    assert _postar_json("http://servidor", {}, {}, 10) == {"ok": True}


def _config_openai_compat(api_key_env: str = "") -> Any:
    from jarvis.core.configuracao import Configuracao, ConfiguracaoOpenAiCompat

    return Configuracao(
        llm_padrao="openai_compat",
        openai_compat=ConfiguracaoOpenAiCompat(
            base_url="https://api.groq.com/openai/v1",
            modelo="llama-3.3-70b-versatile",
            api_key_env=api_key_env,
        ),
    )


def test_fabrica_cria_provider_com_ajustes_do_config() -> None:
    from jarvis.providers import criar_provider_llm

    provider = criar_provider_llm(_config_openai_compat())

    assert isinstance(provider, OpenAICompatProvider)
    assert provider._base_url == "https://api.groq.com/openai/v1"
    assert provider._modelo == "llama-3.3-70b-versatile"


def test_fabrica_recusa_quando_variavel_de_api_key_nao_existe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jarvis.providers import criar_provider_llm

    monkeypatch.delenv("JARVIS_TESTE_CHAVE_INEXISTENTE", raising=False)

    with pytest.raises(ErroProvider, match="JARVIS_TESTE_CHAVE_INEXISTENTE"):
        criar_provider_llm(_config_openai_compat("JARVIS_TESTE_CHAVE_INEXISTENTE"))


def test_fabrica_le_a_chave_da_variavel_de_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    from jarvis.providers import criar_provider_llm

    monkeypatch.setenv("JARVIS_TESTE_CHAVE", "sk-teste")
    provider = criar_provider_llm(_config_openai_compat("JARVIS_TESTE_CHAVE"))

    assert isinstance(provider, OpenAICompatProvider)
    assert provider._api_key == "sk-teste"


def test_postar_json_envia_user_agent_proprio(monkeypatch: pytest.MonkeyPatch) -> None:
    capturado: dict[str, Any] = {}

    def abrir(requisicao: Any, timeout: float) -> Any:
        capturado["headers"] = dict(requisicao.header_items())
        return _urlopen_falso(b"{}")(requisicao, timeout)

    monkeypatch.setattr(ALVO_URLOPEN, abrir)
    _postar_json("http://servidor", {}, {}, 10)

    assert capturado["headers"]["User-agent"].startswith("jarvis/")
