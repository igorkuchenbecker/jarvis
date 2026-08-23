from __future__ import annotations

from typing import Any

import pytest

from jarvis.io.janelas import Janela
from jarvis.tools.base import NivelRisco
from jarvis.tools.computador import criar_ferramentas_computador


def _ferramentas() -> dict[str, Any]:
    return {f.nome: f for f in criar_ferramentas_computador()}


def test_todos_os_niveis_de_risco_estao_corretos() -> None:
    ferramentas = _ferramentas()

    assert ferramentas["computador.listar_janelas"].risco == NivelRisco.READ_ONLY
    assert ferramentas["computador.mover_mouse"].risco == NivelRisco.MEDIUM
    assert ferramentas["computador.clicar"].risco == NivelRisco.CRITICAL
    assert ferramentas["computador.digitar"].risco == NivelRisco.CRITICAL
    assert ferramentas["computador.tecla"].risco == NivelRisco.CRITICAL


def test_listar_janelas_delega_para_io_janelas(monkeypatch: pytest.MonkeyPatch) -> None:
    janelas_falsas = [
        Janela(endereco="0x1", classe="kitty", titulo="term", workspace="1", ativa_no_momento=True)
    ]
    monkeypatch.setattr("jarvis.tools.computador.listar_janelas", lambda: janelas_falsas)

    resultado = _ferramentas()["computador.listar_janelas"].executar({})

    assert resultado == [
        {
            "endereco": "0x1",
            "classe": "kitty",
            "titulo": "term",
            "workspace": "1",
            "ativa_no_momento": True,
        }
    ]


def test_mover_mouse_delega_para_io_entrada(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[tuple[int, int]] = []
    monkeypatch.setattr(
        "jarvis.tools.computador.mover_mouse", lambda dx, dy: chamadas.append((dx, dy))
    )

    resultado = _ferramentas()["computador.mover_mouse"].executar({"delta_x": 5, "delta_y": -3})

    assert chamadas == [(5, -3)]
    assert "5" in resultado and "-3" in resultado


def test_clicar_delega_e_usa_botao_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[str] = []
    monkeypatch.setattr("jarvis.tools.computador.clicar", lambda botao: chamadas.append(botao))

    _ferramentas()["computador.clicar"].executar({})

    assert chamadas == ["esquerdo"]


def test_digitar_delega_para_io_entrada(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[str] = []
    monkeypatch.setattr("jarvis.tools.computador.digitar", lambda texto: chamadas.append(texto))

    resultado = _ferramentas()["computador.digitar"].executar({"texto": "oi"})

    assert chamadas == ["oi"]
    assert "2" in resultado


def test_tecla_delega_para_io_entrada(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[str] = []
    monkeypatch.setattr(
        "jarvis.tools.computador.tecla", lambda combinacao: chamadas.append(combinacao)
    )

    _ferramentas()["computador.tecla"].executar({"combinacao": "ctrl+c"})

    assert chamadas == ["ctrl+c"]
