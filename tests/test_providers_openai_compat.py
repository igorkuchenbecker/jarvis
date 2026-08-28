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


def _resposta_sem_conteudo() -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant"}}]}


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


def test_modelo_de_raciocinio_aplica_piso_de_max_tokens() -> None:
    transporte = TransporteFalso([_resposta("ok")])
    provider = OpenAICompatProvider(
        modelo="qwen3:4b", max_tokens=2048, piso_max_tokens_raciocinio=16384, _postar=transporte
    )

    provider.enviar("oi")

    assert transporte.chamadas[0][1]["max_tokens"] == 16384


def test_modelo_de_raciocinio_respeita_max_tokens_maior_que_o_piso() -> None:
    transporte = TransporteFalso([_resposta("ok")])
    provider = OpenAICompatProvider(
        modelo="qwen3:4b", max_tokens=32768, piso_max_tokens_raciocinio=16384, _postar=transporte
    )

    provider.enviar("oi")

    assert transporte.chamadas[0][1]["max_tokens"] == 32768


def test_piso_desligado_mantem_max_tokens_em_modelo_de_raciocinio() -> None:
    transporte = TransporteFalso([_resposta("ok")])
    provider = OpenAICompatProvider(
        modelo="qwen3:4b", max_tokens=2048, piso_max_tokens_raciocinio=0, _postar=transporte
    )

    provider.enviar("oi")

    assert transporte.chamadas[0][1]["max_tokens"] == 2048


def test_modelo_sem_raciocinio_preserva_max_tokens() -> None:
    transporte = TransporteFalso([_resposta("ok")])
    provider = OpenAICompatProvider(
        modelo="llama3.3:latest",
        max_tokens=2048,
        piso_max_tokens_raciocinio=16384,
        _postar=transporte,
    )

    provider.enviar("oi")

    assert transporte.chamadas[0][1]["max_tokens"] == 2048


def test_historico_comprime_quando_estoura_teto() -> None:
    transporte = TransporteFalso(
        [
            _resposta("R1"),
            _resposta("R2"),
            _resposta("resumo do papo até aqui"),
            _resposta("final"),
        ]
    )
    provider = OpenAICompatProvider(modelo="qwen3:4b", historico_teto_tokens=6, _postar=transporte)

    assert provider.enviar("mensagem um") == "R1"
    assert provider.enviar("mensagem dois") == "R2"
    assert provider.enviar("mensagem tres") == "final"

    assert provider._mensagens[0]["role"] == "system"
    assert "resumo do papo até aqui" in provider._mensagens[0]["content"]
    assert provider._mensagens[1:] == [
        {"role": "assistant", "content": "R2"},
        {"role": "user", "content": "mensagem tres"},
        {"role": "assistant", "content": "final"},
    ]
    post_resumo = transporte.chamadas[2][1]
    assert "comprime conversas" in post_resumo["messages"][0]["content"]
    assert "usuário: mensagem um" in post_resumo["messages"][1]["content"]


def test_compressao_abandona_quando_resumo_vem_vazio() -> None:
    transporte = TransporteFalso(
        [
            _resposta("R1"),
            _resposta("R2"),
            _resposta_sem_conteudo(),
            _resposta("final"),
        ]
    )
    provider = OpenAICompatProvider(modelo="qwen3:4b", historico_teto_tokens=6, _postar=transporte)

    provider.enviar("mensagem um")
    provider.enviar("mensagem dois")
    assert provider.enviar("mensagem tres") == "final"

    assert len(provider._mensagens) == 6
    assert provider._mensagens[0] == {"role": "user", "content": "mensagem um"}


def test_compressao_desligada_com_teto_zero() -> None:
    transporte = TransporteFalso([_resposta("ok"), _resposta("ok"), _resposta("ok")])
    provider = OpenAICompatProvider(modelo="qwen3:4b", historico_teto_tokens=0, _postar=transporte)

    provider.enviar("mensagem um")
    provider.enviar("mensagem dois")
    provider.enviar("mensagem tres")

    assert len(transporte.chamadas) == 3


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


def test_resposta_sem_conteudo_textual_levanta_erro_informativo() -> None:
    transporte = TransporteFalso(
        [_resposta_sem_conteudo(), _resposta_sem_conteudo(), _resposta("funcionou")]
    )
    provider = OpenAICompatProvider(
        base_url="http://localhost:11434/v1", modelo="m", _postar=transporte
    )

    with pytest.raises(ErroProvider, match="sem conteúdo textual"):
        provider.enviar("oi")

    url, corpo, _, _ = transporte.chamadas[0]
    assert url == "http://localhost:11434/v1/chat/completions"
    assert corpo["model"] == "m"


def test_resposta_sem_conteudo_retenta_e_recupera() -> None:
    transporte = TransporteFalso([_resposta_sem_conteudo(), _resposta("recuperou")])
    provider = OpenAICompatProvider(_postar=transporte)

    resposta = provider.enviar("oi")

    assert resposta == "recuperou"
    assert len(transporte.chamadas) == 2


def test_resposta_sem_conteudo_persistente_nao_suja_o_historico() -> None:
    transporte = TransporteFalso(
        [_resposta_sem_conteudo(), _resposta_sem_conteudo(), _resposta("depois do erro")]
    )
    provider = OpenAICompatProvider(_postar=transporte)

    with pytest.raises(ErroProvider, match="max_tokens"):
        provider.enviar("mensagem que falha")
    provider.enviar("mensagem que funciona")

    mensagens = transporte.chamadas[2][1]["messages"]
    assert [m["content"] for m in mensagens[1:]] == ["mensagem que funciona"]


def test_envia_max_tokens_no_corpo() -> None:
    transporte = TransporteFalso([_resposta("ok")])
    provider = OpenAICompatProvider(max_tokens=4096, _postar=transporte)

    provider.enviar("oi")

    assert transporte.chamadas[0][1]["max_tokens"] == 4096


def test_max_tokens_zero_nao_envia_campo() -> None:
    transporte = TransporteFalso([_resposta("ok")])
    provider = OpenAICompatProvider(max_tokens=0, _postar=transporte)

    provider.enviar("oi")

    assert "max_tokens" not in transporte.chamadas[0][1]


def test_desabilita_ferramentas_nativas_por_padrao() -> None:
    transporte = TransporteFalso([_resposta("ok")])
    provider = OpenAICompatProvider(_postar=transporte)

    provider.enviar("oi")

    corpo = transporte.chamadas[0][1]
    assert corpo["tools"] == []
    assert corpo["tool_choice"] == "none"


def test_desabilita_ferramentas_nativas_pode_ser_ligada_de_novo() -> None:
    transporte = TransporteFalso([_resposta("ok")])
    provider = OpenAICompatProvider(desabilitar_ferramentas_nativas=False, _postar=transporte)

    provider.enviar("oi")

    corpo = transporte.chamadas[0][1]
    assert "tools" not in corpo
    assert "tool_choice" not in corpo


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
