from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from jarvis.providers.base import ErroProvider
from jarvis.providers.stt import WhisperSTTProvider


@dataclass
class _SegmentoFalso:
    text: str


class _WhisperModelFalso:
    """Substitui faster_whisper.WhisperModel nos testes — nunca baixa nem carrega modelo real."""

    def __init__(
        self, modelo: str, device: str, compute_type: str, download_root: str | None
    ) -> None:
        self.modelo = modelo
        self.device = device
        self.compute_type = compute_type
        self.chamadas_transcribe: list[tuple[Any, str | None]] = []
        self.segmentos_a_retornar: list[_SegmentoFalso] = [_SegmentoFalso("olá mundo")]
        self.deve_falhar = False

    def transcribe(
        self, sinal: Any, language: str | None = None
    ) -> tuple[list[_SegmentoFalso], Any]:
        if self.deve_falhar:
            raise RuntimeError("falha simulada do whisper")
        self.chamadas_transcribe.append((sinal, language))
        return self.segmentos_a_retornar, None


def test_transcrever_devolve_texto_dos_segmentos(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _WhisperModelFalso("small", "cpu", "int8", None)
    monkeypatch.setattr("jarvis.providers.stt.WhisperModel", lambda *_a, **_kw: fake)

    provider = WhisperSTTProvider(modelo="small", idioma="pt")
    sinal = np.ones(16000, dtype=np.float32)

    texto = provider.transcrever(sinal, 16000)

    assert texto == "olá mundo"
    assert len(fake.chamadas_transcribe) == 1
    assert fake.chamadas_transcribe[0][1] == "pt"


def test_transcrever_junta_multiplos_segmentos(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _WhisperModelFalso("small", "cpu", "int8", None)
    fake.segmentos_a_retornar = [
        _SegmentoFalso("primeira parte."),
        _SegmentoFalso("segunda parte."),
    ]
    monkeypatch.setattr("jarvis.providers.stt.WhisperModel", lambda *_a, **_kw: fake)

    provider = WhisperSTTProvider()
    texto = provider.transcrever(np.ones(1000, dtype=np.float32), 16000)

    assert texto == "primeira parte. segunda parte."


def test_transcrever_levanta_erro_com_audio_vazio(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _WhisperModelFalso("small", "cpu", "int8", None)
    monkeypatch.setattr("jarvis.providers.stt.WhisperModel", lambda *_a, **_kw: fake)
    provider = WhisperSTTProvider()

    with pytest.raises(ErroProvider, match="vazio"):
        provider.transcrever(np.zeros(0, dtype=np.float32), 16000)


def test_transcrever_levanta_erro_com_taxa_amostragem_errada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _WhisperModelFalso("small", "cpu", "int8", None)
    monkeypatch.setattr("jarvis.providers.stt.WhisperModel", lambda *_a, **_kw: fake)
    provider = WhisperSTTProvider()

    with pytest.raises(ErroProvider, match="16000"):
        provider.transcrever(np.ones(8000, dtype=np.float32), 8000)


def test_transcrever_levanta_erro_quando_nenhuma_fala_detectada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _WhisperModelFalso("small", "cpu", "int8", None)
    fake.segmentos_a_retornar = []
    monkeypatch.setattr("jarvis.providers.stt.WhisperModel", lambda *_a, **_kw: fake)
    provider = WhisperSTTProvider()

    with pytest.raises(ErroProvider, match="nenhuma fala"):
        provider.transcrever(np.ones(1000, dtype=np.float32), 16000)


def test_transcrever_propaga_falha_do_modelo_como_erro_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _WhisperModelFalso("small", "cpu", "int8", None)
    fake.deve_falhar = True
    monkeypatch.setattr("jarvis.providers.stt.WhisperModel", lambda *_a, **_kw: fake)
    provider = WhisperSTTProvider()

    with pytest.raises(ErroProvider, match="falha ao transcrever"):
        provider.transcrever(np.ones(1000, dtype=np.float32), 16000)


def test_construtor_propaga_falha_ao_carregar_modelo(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fabrica_com_falha(*_a: Any, **_kw: Any) -> _WhisperModelFalso:
        raise RuntimeError("modelo não encontrado")

    monkeypatch.setattr("jarvis.providers.stt.WhisperModel", _fabrica_com_falha)

    with pytest.raises(ErroProvider, match="não foi possível carregar"):
        WhisperSTTProvider(modelo="inexistente")
