import pytest

from jarvis.providers.base import ErroProvider
from jarvis.providers.fake import FakeProvider


def test_fake_provider_devolve_respostas_na_ordem() -> None:
    provider = FakeProvider(["primeira", "segunda"])

    assert provider.enviar("oi") == "primeira"
    assert provider.enviar("tudo bem?") == "segunda"
    assert provider.historico == ["oi", "tudo bem?"]


def test_fake_provider_levanta_erro_quando_esgota_roteiro() -> None:
    provider = FakeProvider(["única resposta"])
    provider.enviar("oi")

    with pytest.raises(ErroProvider):
        provider.enviar("de novo?")


def test_fake_provider_reiniciar_limpa_historico() -> None:
    provider = FakeProvider(["resposta"])
    provider.enviar("oi")

    provider.reiniciar()

    assert provider.historico == []
