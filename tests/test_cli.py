import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from jarvis.core.configuracao import Configuracao, ConfiguracaoCaminhos, ConfiguracaoVoz
from jarvis.io import cli
from jarvis.io.audio import AudioIndisponivel, DispositivoAudio
from jarvis.observability.auditoria import RegistradorAuditoria, RegistroAuditoria
from jarvis.providers.base import ErroProvider
from jarvis.providers.fake import FakeProvider, FakeSTTProvider, FakeTTSProvider
from jarvis.security.executor import Executor
from jarvis.tools import RegistroFerramentas
from jarvis.tools.fs import criar_ferramentas_fs


class _StatusFalso:
    """Substitui Console.status() nos testes — registra a mensagem sem desenhar nada real."""

    def __init__(self, chamadas: list[str], mensagem: str) -> None:
        self._chamadas = chamadas
        self._mensagem = mensagem

    def __enter__(self) -> _StatusFalso:
        self._chamadas.append(self._mensagem)
        return self

    def __exit__(self, *excecao: Any) -> None:
        return None


def _entradas(*textos: str) -> Any:
    fila = iter(textos)

    def _proxima(prompt: str = "") -> str:
        return next(fila)

    return _proxima


def test_comando_padrao_inicia_conversa_com_o_provider_configurado(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "carregar_configuracao", lambda: Configuracao())
    monkeypatch.setattr(
        cli, "_construir_executor", lambda configuracao: (RegistroFerramentas(), None)
    )
    monkeypatch.setattr(
        cli, "criar_provider_llm", lambda configuracao, prompt_sistema=None: FakeProvider(["oi!"])
    )
    monkeypatch.setattr(cli.console, "input", _entradas("olá", "sair"))

    analisador = cli._construir_analisador()
    argumentos = analisador.parse_args([])
    argumentos.funcao(argumentos)

    assert "oi!" in capsys.readouterr().out


def test_comando_padrao_mostra_erro_amigavel_quando_provider_nao_disponivel(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _criar_provider_com_erro(
        configuracao: Configuracao, prompt_sistema: str | None = None
    ) -> FakeProvider:
        raise ErroProvider("binário não encontrado")

    monkeypatch.setattr(cli, "carregar_configuracao", lambda: Configuracao())
    monkeypatch.setattr(
        cli, "_construir_executor", lambda configuracao: (RegistroFerramentas(), None)
    )
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


def test_executar_conversa_mostra_indicador_de_carregamento_por_mensagem(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Indicador de 'pensando' deve envolver cada chamada ao provider/loop — uma vez por
    mensagem enviada, não uma vez só pra conversa inteira."""
    chamadas: list[str] = []
    monkeypatch.setattr(
        cli.console, "status", lambda mensagem, spinner="dots": _StatusFalso(chamadas, mensagem)
    )
    monkeypatch.setattr(cli.console, "input", _entradas("oi", "tudo bem?", "sair"))
    provider = FakeProvider(["olá!", "tudo ótimo, e você?"])

    cli._executar_conversa(provider)

    assert chamadas == ["[dim]pensando...[/dim]", "[dim]pensando...[/dim]"]


def test_executar_conversa_indicador_desaparece_antes_da_resposta_aparecer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """O 'with' do status precisa fechar (spinner sumir) ANTES do texto final ser impresso —
    não em paralelo. Provamos isso registrando a ordem relativa de entrada/saída do status
    versus a impressão da resposta numa lista compartilhada."""
    eventos: list[str] = []

    class _StatusRegistrado(_StatusFalso):
        def __exit__(self, *excecao: Any) -> None:
            eventos.append("status:fechou")
            return super().__exit__(*excecao)

        def __enter__(self) -> _StatusRegistrado:
            eventos.append("status:abriu")
            return self

    monkeypatch.setattr(
        cli.console, "status", lambda mensagem, spinner="dots": _StatusRegistrado([], mensagem)
    )

    console_print_original = cli.console.print

    def _print_registrando(*args: Any, **kwargs: Any) -> None:
        texto = str(args[0]) if args else ""
        if "jarvis>" in texto:
            eventos.append("resposta:impressa")
        console_print_original(*args, **kwargs)

    monkeypatch.setattr(cli.console, "print", _print_registrando)
    monkeypatch.setattr(cli.console, "input", _entradas("oi", "sair"))

    cli._executar_conversa(FakeProvider(["olá!"]))

    assert eventos == ["status:abriu", "status:fechou", "resposta:impressa"]


def test_executar_conversa_encerra_limpo_com_eof(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _input_com_eof(prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr(cli.console, "input", _input_com_eof)

    cli._executar_conversa(FakeProvider([]))  # não deve lançar


def test_executar_conversa_nao_engole_colchetes_da_resposta_do_llm(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regressão: Console.print() do Rich trata `[algo]` como marcação de estilo por padrão e
    engolia silenciosamente citações como `[arquivo § seção]` vindas do LLM (achado real no M5).
    """
    monkeypatch.setattr(cli.console, "input", _entradas("oi", "sair"))
    provider = FakeProvider(["conforme [notas.md § Instalação], rode X"])

    cli._executar_conversa(provider)

    assert "[notas.md § Instalação]" in capsys.readouterr().out


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


def test_version_imprime_versao_e_sai(capsys: pytest.CaptureFixture[str]) -> None:
    analisador = cli._construir_analisador()

    with pytest.raises(SystemExit) as excinfo:
        analisador.parse_args(["--version"])

    assert excinfo.value.code == 0
    assert "jarvis" in capsys.readouterr().out


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


def test_audit_lista_registros_mais_recentes_primeiro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    caminho_auditoria = tmp_path / "auditoria.jsonl"
    registrador = RegistradorAuditoria(caminho_auditoria)
    registrador.registrar(
        RegistroAuditoria("fs.read", {}, "sucesso", 0.01, quando="2026-01-01T00:00:00")
    )
    registrador.registrar(
        RegistroAuditoria("fs.write", {}, "sucesso", 0.02, quando="2026-01-02T00:00:00")
    )
    monkeypatch.setattr(
        cli,
        "carregar_configuracao",
        lambda: Configuracao(caminhos=ConfiguracaoCaminhos(auditoria_jsonl=caminho_auditoria)),
    )

    cli._comando_audit(argparse.Namespace(limite=20))

    saida = capsys.readouterr().out
    assert saida.index("fs.write") < saida.index("fs.read")


def test_audit_sem_registros_nao_quebra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "carregar_configuracao",
        lambda: Configuracao(
            caminhos=ConfiguracaoCaminhos(auditoria_jsonl=tmp_path / "auditoria.jsonl")
        ),
    )

    cli._comando_audit(argparse.Namespace(limite=20))

    assert "nenhum registro" in capsys.readouterr().out


def test_why_mostra_detalhes_do_registro_pedido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    caminho_auditoria = tmp_path / "auditoria.jsonl"
    registrador = RegistradorAuditoria(caminho_auditoria)
    registrador.registrar(RegistroAuditoria("fs.read", {"caminho": "a.txt"}, "sucesso", 0.01))
    registrador.registrar(RegistroAuditoria("fs.write", {"caminho": "b.txt"}, "sucesso", 0.02))
    monkeypatch.setattr(
        cli,
        "carregar_configuracao",
        lambda: Configuracao(caminhos=ConfiguracaoCaminhos(auditoria_jsonl=caminho_auditoria)),
    )

    cli._comando_why(argparse.Namespace(indice=1))

    saida = capsys.readouterr().out
    assert "fs.write" in saida
    assert "b.txt" in saida


def test_why_indice_invalido_mostra_erro_amigavel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "carregar_configuracao",
        lambda: Configuracao(
            caminhos=ConfiguracaoCaminhos(auditoria_jsonl=tmp_path / "auditoria.jsonl")
        ),
    )

    cli._comando_why(argparse.Namespace(indice=1))

    assert "erro" in capsys.readouterr().out


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


def _executor_com_ferramentas_fs(tmp_path: Path) -> Executor:
    registro = RegistroFerramentas()
    for ferramenta in criar_ferramentas_fs():
        registro.registrar(ferramenta)
    return Executor(registro, jail_paths=[tmp_path])


def test_voz_falar_roteia_para_o_comando_certo() -> None:
    analisador = cli._construir_analisador()
    argumentos = analisador.parse_args(["voz", "falar"])

    assert argumentos.funcao is cli._comando_voz_falar


def test_executar_conversa_voz_transcreve_processa_e_fala_a_resposta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.console, "input", _entradas("", "sair"))
    monkeypatch.setattr(cli, "capturar", lambda duracao, taxa: np.ones(1000, dtype=np.float32))
    monkeypatch.setattr(cli, "aparar_silencio", lambda sinal, taxa: sinal)

    chamadas_tocar: list[tuple[Any, int]] = []
    monkeypatch.setattr(
        cli, "tocar", lambda sinal, taxa: chamadas_tocar.append((sinal, taxa))
    )

    provider = FakeProvider(["Brasília é a capital do Brasil."])
    executor = _executor_com_ferramentas_fs(tmp_path)
    stt = FakeSTTProvider(["qual é a capital do brasil?"])
    tts = FakeTTSProvider(taxa_amostragem=22050)

    cli._executar_conversa_voz(provider, executor, stt, tts, 6.0, 16000)

    saida = capsys.readouterr().out
    assert "qual é a capital do brasil?" in saida
    assert "Brasília é a capital do Brasil." in saida
    assert stt.historico[0][1] == 16000
    assert tts.historico == ["Brasília é a capital do Brasil."]
    assert len(chamadas_tocar) == 1
    assert chamadas_tocar[0][1] == 22050


def test_executar_conversa_voz_mostra_indicador_de_carregamento(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.console, "input", _entradas("", "sair"))
    monkeypatch.setattr(cli, "capturar", lambda duracao, taxa: np.ones(1000, dtype=np.float32))
    monkeypatch.setattr(cli, "aparar_silencio", lambda sinal, taxa: sinal)
    monkeypatch.setattr(cli, "tocar", lambda sinal, taxa: None)

    chamadas: list[str] = []
    monkeypatch.setattr(
        cli.console, "status", lambda mensagem, spinner="dots": _StatusFalso(chamadas, mensagem)
    )

    cli._executar_conversa_voz(
        FakeProvider(["olá!"]),
        _executor_com_ferramentas_fs(tmp_path),
        FakeSTTProvider(["oi"]),
        FakeTTSProvider(),
        6.0,
        16000,
    )

    assert chamadas == ["[dim]pensando...[/dim]"]


def test_executar_conversa_voz_executa_ferramenta_de_verdade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """M8/V4: fecha a divida tecnica de V3 — prova que ferramentas de verdade (não só texto)
    funcionam pelo caminho de voz, exatamente como já funcionavam pelo caminho de texto (M2).
    """
    (tmp_path / "a.txt").write_text("conteudo")
    monkeypatch.setattr(cli.console, "input", _entradas("", "sair"))
    monkeypatch.setattr(cli, "capturar", lambda duracao, taxa: np.ones(1000, dtype=np.float32))
    monkeypatch.setattr(cli, "aparar_silencio", lambda sinal, taxa: sinal)
    monkeypatch.setattr(cli, "tocar", lambda sinal, taxa: None)

    provider = FakeProvider(
        [
            json.dumps(
                {"tipo": "acao", "ferramenta": "fs.list", "argumentos": {"caminho": str(tmp_path)}}
            ),
            "O único arquivo é a.txt.",
        ]
    )
    executor = _executor_com_ferramentas_fs(tmp_path)
    stt = FakeSTTProvider(["liste os arquivos do meu workspace"])
    tts = FakeTTSProvider()

    cli._executar_conversa_voz(provider, executor, stt, tts, 6.0, 16000)

    saida = capsys.readouterr().out
    assert "executou fs.list" in saida
    assert "O único arquivo é a.txt." in saida
    assert tts.historico == ["O único arquivo é a.txt."]


def test_executar_conversa_voz_avisa_quando_nao_ouve_nada(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.console, "input", _entradas("", "sair"))
    monkeypatch.setattr(cli, "capturar", lambda duracao, taxa: np.ones(1000, dtype=np.float32))
    monkeypatch.setattr(cli, "aparar_silencio", lambda sinal, taxa: sinal[:0])

    stt = FakeSTTProvider([])
    tts = FakeTTSProvider()

    cli._executar_conversa_voz(
        FakeProvider([]), Executor(RegistroFerramentas(), jail_paths=[]), stt, tts, 6.0, 16000
    )

    assert "não ouvi nada" in capsys.readouterr().out
    assert stt.historico == []


def test_executar_conversa_voz_mostra_erro_quando_microfone_falha(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.console, "input", _entradas("", "sair"))

    def _capturar_com_falha(duracao: float, taxa: int) -> Any:
        raise AudioIndisponivel("sem microfone")

    monkeypatch.setattr(cli, "capturar", _capturar_com_falha)

    cli._executar_conversa_voz(
        FakeProvider([]),
        Executor(RegistroFerramentas(), jail_paths=[]),
        FakeSTTProvider([]),
        FakeTTSProvider(),
        6.0,
        16000,
    )

    assert "sem microfone" in capsys.readouterr().out


def test_executar_conversa_voz_mostra_erro_de_transcricao_e_continua(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.console, "input", _entradas("", "sair"))
    monkeypatch.setattr(cli, "capturar", lambda duracao, taxa: np.ones(1000, dtype=np.float32))
    monkeypatch.setattr(cli, "aparar_silencio", lambda sinal, taxa: sinal)

    class SttComErro:
        def transcrever(self, sinal: Any, taxa_amostragem: int) -> str:
            raise ErroProvider("modelo indisponível")

    cli._executar_conversa_voz(
        FakeProvider([]),
        Executor(RegistroFerramentas(), jail_paths=[]),
        SttComErro(),
        FakeTTSProvider(),
        6.0,
        16000,
    )

    assert "modelo indisponível" in capsys.readouterr().out


def test_executar_conversa_voz_mostra_erro_de_reproducao_mas_nao_trava(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """M8/V4: uma saída de áudio indisponível não deve impedir o próximo turno de voz."""
    monkeypatch.setattr(cli.console, "input", _entradas("", "sair"))
    monkeypatch.setattr(cli, "capturar", lambda duracao, taxa: np.ones(1000, dtype=np.float32))
    monkeypatch.setattr(cli, "aparar_silencio", lambda sinal, taxa: sinal)

    def _tocar_com_falha(sinal: Any, taxa: int) -> None:
        raise AudioIndisponivel("sem saída de áudio")

    monkeypatch.setattr(cli, "tocar", _tocar_com_falha)

    provider = FakeProvider(["olá!"])
    stt = FakeSTTProvider(["oi"])

    cli._executar_conversa_voz(
        provider, Executor(RegistroFerramentas(), jail_paths=[]), stt, FakeTTSProvider(), 6.0, 16000
    )

    saida = capsys.readouterr().out
    assert "olá!" in saida  # a resposta em texto sempre aparece, mesmo sem áudio
    assert "sem saída de áudio" in saida


def test_comando_voz_falar_recusa_quando_voz_desabilitada(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli, "carregar_configuracao", lambda: Configuracao(voz=ConfiguracaoVoz(habilitada=False))
    )

    cli._comando_voz_falar(argparse.Namespace())

    assert "desabilitada" in capsys.readouterr().out


def test_comando_voz_falar_monta_providers_e_inicia_loop_quando_habilitada(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli, "carregar_configuracao", lambda: Configuracao(voz=ConfiguracaoVoz(habilitada=True))
    )
    monkeypatch.setattr(
        cli, "_construir_executor", lambda configuracao: (RegistroFerramentas(), None)
    )
    monkeypatch.setattr(
        cli, "criar_provider_llm", lambda configuracao, prompt_sistema=None: FakeProvider([])
    )
    monkeypatch.setattr(cli, "criar_provider_stt", lambda configuracao: FakeSTTProvider([]))
    monkeypatch.setattr(cli, "criar_provider_tts", lambda configuracao: FakeTTSProvider())

    chamadas: list[Any] = []
    monkeypatch.setattr(
        cli, "_executar_conversa_voz", lambda *args: chamadas.append(args)
    )

    cli._comando_voz_falar(argparse.Namespace())

    assert len(chamadas) == 1
