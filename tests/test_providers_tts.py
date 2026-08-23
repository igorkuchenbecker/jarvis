from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from jarvis.providers.base import ErroProvider
from jarvis.providers.tts import PiperTTSProvider


@dataclass
class _PedacoFalso:
    audio_float_array: np.ndarray
    sample_rate: int = 22050


class _VozFalsa:
    def __init__(self) -> None:
        self.textos_sintetizados: list[str] = []
        self.pedacos_a_retornar = [_PedacoFalso(np.ones(100, dtype=np.float32))]
        self.deve_falhar = False

    def synthesize(self, texto: str, *_a: Any, **_kw: Any) -> list[_PedacoFalso]:
        if self.deve_falhar:
            raise RuntimeError("falha simulada do piper")
        self.textos_sintetizados.append(texto)
        return self.pedacos_a_retornar


def _preparar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, voz_falsa: _VozFalsa | None = None
) -> tuple[PiperTTSProvider, _VozFalsa]:
    fake = voz_falsa or _VozFalsa()
    # arquivos "já baixados" para o construtor não tentar baixar nada de verdade.
    (tmp_path / "pt_BR-faber-medium.onnx").write_bytes(b"")
    (tmp_path / "pt_BR-faber-medium.onnx.json").write_text("{}")

    monkeypatch.setattr("jarvis.providers.tts.download_voice", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        "jarvis.providers.tts.PiperVoice.load", staticmethod(lambda *_a, **_kw: fake)
    )

    provider = PiperTTSProvider(voz="pt_BR-faber-medium", diretorio_modelos=tmp_path)
    return provider, fake


def test_sintetizar_devolve_sinal_concatenado_e_taxa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _VozFalsa()
    fake.pedacos_a_retornar = [
        _PedacoFalso(np.ones(10, dtype=np.float32), sample_rate=22050),
        _PedacoFalso(np.zeros(5, dtype=np.float32), sample_rate=22050),
    ]
    provider, fake = _preparar(tmp_path, monkeypatch, fake)

    sinal, taxa = provider.sintetizar("olá, tudo bem?")

    assert taxa == 22050
    assert sinal.shape == (15,)
    assert fake.textos_sintetizados == ["olá, tudo bem?"]


def test_construtor_baixa_voz_quando_arquivos_nao_existem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[tuple[str, Path]] = []

    def _download_falso(voz: str, diretorio: Path, **_kw: Any) -> None:
        chamadas.append((voz, diretorio))
        (diretorio / f"{voz}.onnx").write_bytes(b"")
        (diretorio / f"{voz}.onnx.json").write_text("{}")

    monkeypatch.setattr("jarvis.providers.tts.download_voice", _download_falso)
    monkeypatch.setattr(
        "jarvis.providers.tts.PiperVoice.load", staticmethod(lambda *_a, **_kw: _VozFalsa())
    )

    PiperTTSProvider(voz="pt_BR-faber-medium", diretorio_modelos=tmp_path)

    assert chamadas == [("pt_BR-faber-medium", tmp_path)]


def test_construtor_nao_baixa_de_novo_quando_arquivos_ja_existem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[str] = []
    monkeypatch.setattr(
        "jarvis.providers.tts.download_voice", lambda *_a, **_kw: chamadas.append("baixou")
    )
    provider, _fake = _preparar(tmp_path, monkeypatch)

    assert chamadas == []


def test_sintetizar_levanta_erro_com_texto_vazio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider, _fake = _preparar(tmp_path, monkeypatch)

    with pytest.raises(ErroProvider, match="vazio"):
        provider.sintetizar("   ")


def test_sintetizar_propaga_falha_da_voz_como_erro_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _VozFalsa()
    fake.deve_falhar = True
    provider, _fake = _preparar(tmp_path, monkeypatch, fake)

    with pytest.raises(ErroProvider, match="falha ao sintetizar"):
        provider.sintetizar("um texto qualquer")


def test_construtor_propaga_falha_no_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _download_com_falha(*_a: Any, **_kw: Any) -> None:
        raise RuntimeError("sem rede")

    monkeypatch.setattr("jarvis.providers.tts.download_voice", _download_com_falha)

    with pytest.raises(ErroProvider, match="não foi possível baixar"):
        PiperTTSProvider(voz="voz-inexistente", diretorio_modelos=tmp_path)
