import argparse
from typing import Any

import pytest

from jarvis.io import cli
from jarvis.io.audio import DispositivoAudio


def test_comando_padrao_sem_argumentos_nao_lanca(capsys: pytest.CaptureFixture[str]) -> None:
    analisador = cli._construir_analisador()
    argumentos = analisador.parse_args([])

    argumentos.funcao(argumentos)

    assert "JARVIS" in capsys.readouterr().out


def test_voz_check_roteia_para_o_comando_certo() -> None:
    analisador = cli._construir_analisador()
    argumentos = analisador.parse_args(["voz", "check"])

    assert argumentos.funcao is cli._comando_voz_check


def test_voz_check_toca_beep_quando_ha_dispositivos(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    dispositivos = [
        DispositivoAudio(indice=0, nome="mic falso", canais_entrada=1, canais_saida=0),
        DispositivoAudio(indice=1, nome="speaker falso", canais_entrada=0, canais_saida=2),
    ]
    chamadas_tocar: list[Any] = []

    def _tocar_falso(sinal: Any, dispositivo: int | None = None) -> None:
        chamadas_tocar.append(dispositivo)

    monkeypatch.setattr(cli, "listar_dispositivos", lambda: dispositivos)
    monkeypatch.setattr(cli, "dispositivo_padrao_do_sistema", lambda tipo: None)
    monkeypatch.setattr(cli, "tocar", _tocar_falso)

    cli._comando_voz_check(argparse.Namespace())

    saida = capsys.readouterr().out
    assert "mic falso" in saida
    assert "speaker falso" in saida
    assert "beep tocado com sucesso" in saida
    assert chamadas_tocar == [None]


def test_voz_check_avisa_sem_quebrar_quando_nao_ha_microfone(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    dispositivos = [
        DispositivoAudio(indice=0, nome="speaker falso", canais_entrada=0, canais_saida=2)
    ]

    monkeypatch.setattr(cli, "listar_dispositivos", lambda: dispositivos)
    monkeypatch.setattr(cli, "dispositivo_padrao_do_sistema", lambda tipo: None)
    monkeypatch.setattr(cli, "tocar", lambda sinal, dispositivo=None: None)

    cli._comando_voz_check(argparse.Namespace())

    assert "nenhum microfone encontrado" in capsys.readouterr().out
