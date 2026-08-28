"""Testes do io de janelas (hyprctl) com subprocess falso, zero dependência de sessão gráfica."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from jarvis.io.janelas import ErroJanelas, focar_janela


@dataclass
class ProcessoFalso:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _subprocess_para(
    chamadas: list[list[str]], resultados: list[ProcessoFalso]
) -> Callable[..., ProcessoFalso]:
    def executar(args: list[str], **_: object) -> ProcessoFalso:
        chamadas.append(args)
        return resultados.pop(0)

    return executar


SAIDA_LUA_OK = (
    "error: [string \"local ws=hl.get_windows(); local s=''; for i=...\"]:1: "
    "0x55f87bae4c50\tkitty\tOC | Acessar memória\t1\n"
    "0x55f87b5a8750\tkitty\t~: linuxmng\t2\n"
    "0x55f87bb31590\tdiscord\t@LKS - Discord\t3\n"
    "0x55f87bb8a060\tapp.zen_browser.zen\tLíder de Projeto Bizu\t4"
)


def test_focar_janela_encontra_por_classe_e_dispara_foco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[list[str]] = []
    monkeypatch.setattr(
        "jarvis.io.janelas.subprocess.run",
        _subprocess_para(
            chamadas,
            [ProcessoFalso(returncode=7, stdout=SAIDA_LUA_OK), ProcessoFalso(returncode=0)],
        ),
    )

    resultado = focar_janela("class:discord")

    assert resultado == "ok"
    assert chamadas[0][:2] == ["hyprctl", "eval"]
    assert "for i=1,#ws do" in chamadas[0][2]
    assert chamadas[1][1] == "dispatch"
    assert chamadas[1][2] == "hl.dsp.focus({window=hl.get_windows()[3]})"


def test_focar_janela_endereco_normaliza_0x_e_casa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[list[str]] = []
    monkeypatch.setattr(
        "jarvis.io.janelas.subprocess.run",
        _subprocess_para(
            chamadas,
            [ProcessoFalso(returncode=7, stdout=SAIDA_LUA_OK), ProcessoFalso(returncode=0)],
        ),
    )

    focar_janela("address:0x55f87bb8a060")

    assert chamadas[1][2] == "hl.dsp.focus({window=hl.get_windows()[4]})"


def test_focar_janela_titulo_casa_por_substring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[list[str]] = []
    monkeypatch.setattr(
        "jarvis.io.janelas.subprocess.run",
        _subprocess_para(
            chamadas,
            [ProcessoFalso(returncode=7, stdout=SAIDA_LUA_OK), ProcessoFalso(returncode=0)],
        ),
    )

    focar_janela("title:LKS")

    assert chamadas[1][2] == "hl.dsp.focus({window=hl.get_windows()[3]})"


def test_focar_janela_nome_livre_casa_em_classe_ou_titulo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[list[str]] = []
    monkeypatch.setattr(
        "jarvis.io.janelas.subprocess.run",
        _subprocess_para(
            chamadas,
            [ProcessoFalso(returncode=7, stdout=SAIDA_LUA_OK), ProcessoFalso(returncode=0)],
        ),
    )

    focar_janela("projeto bizu")

    assert chamadas[1][2] == "hl.dsp.focus({window=hl.get_windows()[4]})"


def test_focar_janela_erra_quando_ninguem_casa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[list[str]] = []
    monkeypatch.setattr(
        "jarvis.io.janelas.subprocess.run",
        _subprocess_para(chamadas, [ProcessoFalso(returncode=7, stdout=SAIDA_LUA_OK)]),
    )

    with pytest.raises(ErroJanelas, match="nenhuma janela casa"):
        focar_janela("class:ghostapp")

    assert len(chamadas) == 1


def test_focar_janela_cai_no_fallback_classico_sem_api_lua(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[list[str]] = []
    err_lua_ausente = ProcessoFalso(
        returncode=7, stdout="error: attempt to index global 'hl' (a nil value)"
    )
    monkeypatch.setattr(
        "jarvis.io.janelas.subprocess.run",
        _subprocess_para(chamadas, [err_lua_ausente, ProcessoFalso(returncode=0)]),
    )

    resultado = focar_janela("class:discord")

    assert resultado == "ok"
    assert chamadas[1] == ["hyprctl", "dispatch", "focuswindow", "class:discord"]


def test_focar_janela_erra_quando_fallback_tambem_falha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[list[str]] = []
    err_lua_ausente = ProcessoFalso(
        returncode=7, stdout="error: attempt to index global 'hl' (a nil value)"
    )
    monkeypatch.setattr(
        "jarvis.io.janelas.subprocess.run",
        _subprocess_para(
            chamadas,
            [err_lua_ausente, ProcessoFalso(returncode=1, stderr="não achei")],
        ),
    )

    with pytest.raises(ErroJanelas, match="não foi possível focar"):
        focar_janela("class:discord")


def test_focar_janela_erra_quando_evidenciando_dispatcher_sem_efeito(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[list[str]] = []
    monkeypatch.setattr(
        "jarvis.io.janelas.subprocess.run",
        _subprocess_para(
            chamadas,
            [
                ProcessoFalso(returncode=7, stdout=SAIDA_LUA_OK),
                ProcessoFalso(
                    returncode=7,
                    stdout="error: hl.dispatch: expected a dispatcher (e.g. hl.dsp.window.close())",
                ),
            ],
        ),
    )

    with pytest.raises(ErroJanelas, match="não foi possível focar"):
        focar_janela("class:discord")


def test_focar_janela_rejeita_seletor_vazio(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[list[str]] = []
    monkeypatch.setattr(
        "jarvis.io.janelas.subprocess.run",
        _subprocess_para(chamadas, [ProcessoFalso(returncode=0)]),
    )

    with pytest.raises(ErroJanelas, match="vazio"):
        focar_janela("   ")

    with pytest.raises(ErroJanelas, match="vazio"):
        focar_janela("address:")

    assert chamadas == []


def test_focar_janela_erra_quando_binario_nao_existe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "jarvis.io.janelas.subprocess.run",
        lambda *_, **__: (_ for _ in ()).throw(FileNotFoundError()),
    )

    with pytest.raises(ErroJanelas, match="não encontrado"):
        focar_janela("class:x")


def test_focar_janela_trata_saida_inesperada_da_enumeracao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[list[str]] = []
    monkeypatch.setattr(
        "jarvis.io.janelas.subprocess.run",
        _subprocess_para(chamadas, [ProcessoFalso(returncode=7, stdout="ok")]),
    )

    with pytest.raises(ErroJanelas, match="saída inesperada"):
        focar_janela("class:discord")


def test_focar_janela_erra_no_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    from subprocess import TimeoutExpired

    def estoura_tempo(*_: object, **__: object) -> None:
        raise TimeoutExpired("hyprctl", 10)

    monkeypatch.setattr("jarvis.io.janelas.subprocess.run", estoura_tempo)

    with pytest.raises(ErroJanelas, match="a tempo"):
        focar_janela("class:x", timeout_segundos=1)
