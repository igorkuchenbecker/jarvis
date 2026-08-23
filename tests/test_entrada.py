from __future__ import annotations

from typing import Any

import pytest
from evdev import ecodes as e

from jarvis.io.entrada import EntradaIndisponivel, clicar, digitar, mover_mouse, tecla


class _UInputFalso:
    """Substitui evdev.UInput nos testes — nunca abre /dev/uinput de verdade."""

    def __init__(self, capacidades: Any, name: str) -> None:
        self.name = name
        self.eventos: list[tuple[int, int, int]] = []
        self.fechado = False
        self.deve_falhar_ao_escrever = False

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        if self.deve_falhar_ao_escrever:
            raise RuntimeError("falha simulada de escrita no uinput")
        self.eventos.append((tipo, codigo, valor))

    def syn(self) -> None:
        pass

    def close(self) -> None:
        self.fechado = True


@pytest.fixture
def dispositivo_falso(monkeypatch: pytest.MonkeyPatch) -> _UInputFalso:
    instancia = _UInputFalso({}, name="jarvis-entrada-virtual")
    monkeypatch.setattr("jarvis.io.entrada.UInput", lambda capacidades, name: instancia)
    return instancia


def test_mover_mouse_escreve_eventos_relativos_e_fecha_dispositivo(
    dispositivo_falso: _UInputFalso,
) -> None:
    mover_mouse(10, -5)

    assert (e.EV_REL, e.REL_X, 10) in dispositivo_falso.eventos
    assert (e.EV_REL, e.REL_Y, -5) in dispositivo_falso.eventos
    assert dispositivo_falso.fechado is True


def test_clicar_pressiona_e_solta_o_botao(dispositivo_falso: _UInputFalso) -> None:
    clicar("esquerdo")

    assert (e.EV_KEY, e.BTN_LEFT, 1) in dispositivo_falso.eventos
    assert (e.EV_KEY, e.BTN_LEFT, 0) in dispositivo_falso.eventos
    indice_down = dispositivo_falso.eventos.index((e.EV_KEY, e.BTN_LEFT, 1))
    indice_up = dispositivo_falso.eventos.index((e.EV_KEY, e.BTN_LEFT, 0))
    assert indice_down < indice_up


def test_clicar_com_botao_desconhecido_levanta_erro(dispositivo_falso: _UInputFalso) -> None:
    with pytest.raises(EntradaIndisponivel, match="desconhecido"):
        clicar("inexistente")


def test_digitar_texto_simples(dispositivo_falso: _UInputFalso) -> None:
    digitar("ab")

    codigos_pressionados = [
        codigo
        for tipo, codigo, valor in dispositivo_falso.eventos
        if tipo == e.EV_KEY and valor == 1
    ]
    assert codigos_pressionados == [e.KEY_A, e.KEY_B]


def test_digitar_maiuscula_usa_shift(dispositivo_falso: _UInputFalso) -> None:
    digitar("A")

    eventos_down = [
        (tipo, codigo) for tipo, codigo, valor in dispositivo_falso.eventos if valor == 1
    ]
    assert (e.EV_KEY, e.KEY_LEFTSHIFT) in eventos_down
    assert (e.EV_KEY, e.KEY_A) in eventos_down


def test_digitar_caractere_nao_suportado_levanta_erro_antes_de_escrever(
    dispositivo_falso: _UInputFalso,
) -> None:
    with pytest.raises(EntradaIndisponivel, match="ã"):
        digitar("ação")

    assert dispositivo_falso.eventos == []  # não digita parcialmente


def test_tecla_simples(dispositivo_falso: _UInputFalso) -> None:
    tecla("enter")

    assert (e.EV_KEY, e.KEY_ENTER, 1) in dispositivo_falso.eventos
    assert (e.EV_KEY, e.KEY_ENTER, 0) in dispositivo_falso.eventos


def test_tecla_com_modificadores(dispositivo_falso: _UInputFalso) -> None:
    tecla("ctrl+shift+t")

    eventos_down = {
        codigo
        for tipo, codigo, valor in dispositivo_falso.eventos
        if tipo == e.EV_KEY and valor == 1
    }
    assert eventos_down == {e.KEY_LEFTCTRL, e.KEY_LEFTSHIFT, e.KEY_T}


def test_tecla_modificador_desconhecido_levanta_erro(dispositivo_falso: _UInputFalso) -> None:
    with pytest.raises(EntradaIndisponivel, match="modificador"):
        tecla("hyper+a")


def test_tecla_desconhecida_levanta_erro(dispositivo_falso: _UInputFalso) -> None:
    with pytest.raises(EntradaIndisponivel, match="desconhecida"):
        tecla("botao_magico_inexistente_123")


def test_tecla_vazia_levanta_erro(dispositivo_falso: _UInputFalso) -> None:
    with pytest.raises(EntradaIndisponivel, match="vazia"):
        tecla("   ")


def test_falha_ao_criar_dispositivo_levanta_entrada_indisponivel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _uinput_com_falha(capacidades: Any, name: str) -> Any:
        raise RuntimeError("sem permissão em /dev/uinput")

    monkeypatch.setattr("jarvis.io.entrada.UInput", _uinput_com_falha)

    with pytest.raises(EntradaIndisponivel, match="não foi possível criar"):
        mover_mouse(1, 1)


def test_falha_ao_escrever_levanta_entrada_indisponivel_e_fecha_dispositivo(
    dispositivo_falso: _UInputFalso,
) -> None:
    dispositivo_falso.deve_falhar_ao_escrever = True

    with pytest.raises(EntradaIndisponivel, match="falha ao mover"):
        mover_mouse(1, 1)

    assert dispositivo_falso.fechado is True
