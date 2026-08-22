from pathlib import Path
from typing import Any

import numpy as np
import pytest

from jarvis.io.audio import (
    AudioIndisponivel,
    DispositivoAudio,
    aparar_silencio,
    capturar,
    carregar_wav,
    dispositivo_entrada_padrao,
    dispositivo_saida_padrao,
    gerar_beep,
    listar_dispositivos,
    salvar_wav,
    tocar,
)


def test_gerar_beep_produz_sinal_com_duracao_esperada() -> None:
    sinal = gerar_beep(duracao_segundos=0.5, taxa_amostragem=16000)

    assert sinal.shape == (8000,)
    assert sinal.dtype == np.float32
    assert np.max(np.abs(sinal)) <= 0.3


def test_aparar_silencio_remove_silencio_das_pontas() -> None:
    taxa = 16000
    silencio = np.zeros(taxa, dtype=np.float32)
    voz = np.full(taxa, 0.5, dtype=np.float32)
    sinal = np.concatenate([silencio, voz, silencio])

    aparado = aparar_silencio(sinal, taxa_amostragem=taxa, limiar_rms=0.01)

    assert aparado.size < sinal.size
    assert np.mean(np.abs(aparado)) > 0.1


def test_aparar_silencio_sinal_totalmente_silencioso_fica_vazio() -> None:
    sinal = np.zeros(16000, dtype=np.float32)

    aparado = aparar_silencio(sinal, taxa_amostragem=16000, limiar_rms=0.01)

    assert aparado.size == 0


def test_aparar_silencio_sinal_vazio_nao_quebra() -> None:
    assert aparar_silencio(np.array([], dtype=np.float32)).size == 0


def test_dispositivo_entrada_e_saida_padrao_escolhem_o_primeiro_compativel() -> None:
    dispositivos = [
        DispositivoAudio(indice=0, nome="monitor", canais_entrada=0, canais_saida=2),
        DispositivoAudio(indice=1, nome="microfone usb", canais_entrada=1, canais_saida=0),
        DispositivoAudio(indice=2, nome="hdmi", canais_entrada=0, canais_saida=2),
    ]

    assert dispositivo_entrada_padrao(dispositivos) == dispositivos[1]
    assert dispositivo_saida_padrao(dispositivos) == dispositivos[0]


def test_dispositivo_padrao_retorna_none_sem_candidatos() -> None:
    assert dispositivo_entrada_padrao([]) is None
    assert dispositivo_saida_padrao([]) is None


def test_salvar_e_carregar_wav_faz_ida_e_volta(tmp_path: Path) -> None:
    caminho = tmp_path / "teste.wav"
    sinal_original = gerar_beep(duracao_segundos=0.1, taxa_amostragem=16000)

    salvar_wav(caminho, sinal_original, taxa_amostragem=16000)
    sinal_recuperado, taxa_recuperada = carregar_wav(caminho)

    assert taxa_recuperada == 16000
    assert sinal_recuperado.shape == sinal_original.shape
    assert np.allclose(sinal_recuperado, sinal_original, atol=1e-3)


def test_listar_dispositivos_traduz_erro_do_portaudio(monkeypatch: pytest.MonkeyPatch) -> None:
    def _query_devices_com_erro() -> Any:
        raise RuntimeError("PortAudio indisponível")

    monkeypatch.setattr("jarvis.io.audio.sd.query_devices", _query_devices_com_erro)

    with pytest.raises(AudioIndisponivel):
        listar_dispositivos()


def test_capturar_traduz_erro_do_portaudio(monkeypatch: pytest.MonkeyPatch) -> None:
    def _rec_com_erro(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("dispositivo ocupado")

    monkeypatch.setattr("jarvis.io.audio.sd.rec", _rec_com_erro)

    with pytest.raises(AudioIndisponivel):
        capturar(duracao_segundos=0.1)


def test_tocar_traduz_erro_do_portaudio(monkeypatch: pytest.MonkeyPatch) -> None:
    def _play_com_erro(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("sem saída de áudio")

    monkeypatch.setattr("jarvis.io.audio.sd.play", _play_com_erro)

    with pytest.raises(AudioIndisponivel):
        tocar(gerar_beep())
