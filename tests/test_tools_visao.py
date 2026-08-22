from pathlib import Path
from typing import Any

import pytest

from jarvis.providers.fake import FakeVisionProvider
from jarvis.tools import visao as modulo_visao
from jarvis.tools.visao import criar_ferramentas_visao


def _ferramenta_analisar(provider: FakeVisionProvider) -> Any:
    (ferramenta,) = criar_ferramentas_visao(provider)
    return ferramenta


def test_vision_analyze_usa_pergunta_padrao_quando_nao_informada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caminho_falso = tmp_path / "tela.png"
    caminho_falso.write_bytes(b"fake")
    monkeypatch.setattr(modulo_visao, "capturar_tela", lambda: caminho_falso)
    provider = FakeVisionProvider(["uma janela de terminal aberta"])

    resultado = _ferramenta_analisar(provider).executar({})

    assert resultado == "uma janela de terminal aberta"
    assert provider.historico[0][1] == "Descreva o que está na tela agora."


def test_vision_analyze_apaga_a_captura_apos_uso(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caminho_falso = tmp_path / "tela.png"
    caminho_falso.write_bytes(b"fake")
    monkeypatch.setattr(modulo_visao, "capturar_tela", lambda: caminho_falso)
    provider = FakeVisionProvider(["descrição qualquer"])

    _ferramenta_analisar(provider).executar({})

    assert not caminho_falso.exists()


def test_vision_analyze_nao_aceita_repositorio_de_memoria() -> None:
    """Regressão: a primeira versão gravava um resumo de CADA captura na memória persistente sem
    pedido do usuário — achado na prática (uma conversa real de WhatsApp foi persistida sozinha
    durante um teste manual). Fatos só entram na memória por comando explícito do usuário; a API
    de `criar_ferramentas_visao` nem aceita mais um repositório, para essa regra não poder ser
    reintroduzida por acidente.
    """
    with pytest.raises(TypeError):
        criar_ferramentas_visao(FakeVisionProvider([]), "não deveria aceitar isto")  # type: ignore[call-arg]
