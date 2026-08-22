import argparse
from typing import Any

import pytest

from jarvis.core.configuracao import Configuracao
from jarvis.io import cli
from jarvis.io.audio import DispositivoAudio
from jarvis.providers.base import ErroProvider
from jarvis.providers.fake import FakeProvider


def _entradas(*textos: str) -> Any:
    fila = iter(textos)

    def _proxima(prompt: str = "") -> str:
        return next(fila)

    return _proxima


def test_comando_padrao_inicia_conversa_com_o_provider_configurado(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "carregar_configuracao", lambda: Configuracao())
    monkeypatch.setattr(cli, "criar_provider_llm", lambda configuracao: FakeProvider(["oi!"]))
    monkeypatch.setattr(cli.console, "input", _entradas("olá", "sair"))

    analisador = cli._construir_analisador()
    argumentos = analisador.parse_args([])
    argumentos.funcao(argumentos)

    assert "oi!" in capsys.readouterr().out


def test_comando_padrao_mostra_erro_amigavel_quando_provider_nao_disponivel(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _criar_provider_com_erro(configuracao: Configuracao) -> FakeProvider:
        raise ErroProvider("binário não encontrado")

    monkeypatch.setattr(cli, "carregar_configuracao", lambda: Configuracao())
    monkeypatch.setattr(cli, "criar_provider_llm", _criar_provider_com_erro)

    cli._comando_padrao(argparse.Namespace())

    assert "binário não encontrado" in capsys.readouterr().out


def test_executar_conversa_troca_mensagens_ate_o_usuario_sair(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.console, "input", _entradas("oi", "tudo bem?", "sair"))
    provider = FakeProvider(["olá!", "tudo ótimo, e você?"])

    cli._executar_conversa(provider)

    saida = capsys.readouterr().out
    assert "olá!" in saida
    assert "tudo ótimo, e você?" in saida
    assert provider.historico == ["oi", "tudo bem?"]


def test_executar_conversa_encerra_limpo_com_eof(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _input_com_eof(prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr(cli.console, "input", _input_com_eof)

    cli._executar_conversa(FakeProvider([]))  # não deve lançar


def test_executar_conversa_ignora_linhas_vazias(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.console, "input", _entradas("", "  ", "oi", "sair"))
    provider = FakeProvider(["olá!"])

    cli._executar_conversa(provider)

    assert provider.historico == ["oi"]


def test_executar_conversa_reiniciar_limpa_historico_do_provider(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.console, "input", _entradas("oi", "reiniciar", "sair"))
    provider = FakeProvider(["olá!"])

    cli._executar_conversa(provider)

    assert "sessão reiniciada" in capsys.readouterr().out
    assert provider.historico == []


def test_executar_conversa_mostra_erro_do_provider_e_continua(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.console, "input", _entradas("oi", "sair"))

    class ProviderComErro:
        def enviar(self, mensagem: str) -> str:
            raise ErroProvider("falha simulada")

        def reiniciar(self) -> None:
            pass

    cli._executar_conversa(ProviderComErro())

    assert "falha simulada" in capsys.readouterr().out


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
