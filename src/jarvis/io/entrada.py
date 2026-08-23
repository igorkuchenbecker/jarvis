"""Canal de saída de entrada sintética (mouse/teclado) do JARVIS: M9, computer use.

Sintetiza eventos via `evdev.UInput` (dispositivo de entrada virtual no nível do kernel,
`/dev/uinput`), não via nenhum protocolo específico do compositor — funciona igual a um
mouse/teclado físico para qualquer aplicação com foco, independente de Wayland/X11/compositor.
Ver docs/DECISOES.md para o porquê de não usar `ydotool`/protocolos Lua específicos do Hyprland
desta máquina.

Nenhuma função aqui decide nada sobre o agente — é infraestrutura pura de E/S, no mesmo espírito
de `io/audio.py`: sem acesso a `security`, sem lógica de negócio.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from evdev import UInput
from evdev import ecodes as e

ATRASO_ENTRE_EVENTOS_SEGUNDOS = 0.01

_TECLAS_CARACTERE: dict[str, tuple[int, bool]] = {}


def _preencher_letras() -> None:
    for letra in "abcdefghijklmnopqrstuvwxyz":
        codigo = getattr(e, f"KEY_{letra.upper()}")
        _TECLAS_CARACTERE[letra] = (codigo, False)
        _TECLAS_CARACTERE[letra.upper()] = (codigo, True)


def _preencher_digitos() -> None:
    for digito in "0123456789":
        _TECLAS_CARACTERE[digito] = (getattr(e, f"KEY_{digito}"), False)


_preencher_letras()
_preencher_digitos()
_TECLAS_CARACTERE.update(
    {
        " ": (e.KEY_SPACE, False),
        ".": (e.KEY_DOT, False),
        ",": (e.KEY_COMMA, False),
        "-": (e.KEY_MINUS, False),
        "_": (e.KEY_MINUS, True),
        ";": (e.KEY_SEMICOLON, False),
        ":": (e.KEY_SEMICOLON, True),
        "'": (e.KEY_APOSTROPHE, False),
        "/": (e.KEY_SLASH, False),
        "?": (e.KEY_SLASH, True),
        "!": (e.KEY_1, True),
        "@": (e.KEY_2, True),
        "\n": (e.KEY_ENTER, False),
    }
)

_TECLAS_NOMEADAS: dict[str, int] = {
    "enter": e.KEY_ENTER,
    "esc": e.KEY_ESC,
    "escape": e.KEY_ESC,
    "tab": e.KEY_TAB,
    "space": e.KEY_SPACE,
    "backspace": e.KEY_BACKSPACE,
    "delete": e.KEY_DELETE,
    "up": e.KEY_UP,
    "down": e.KEY_DOWN,
    "left": e.KEY_LEFT,
    "right": e.KEY_RIGHT,
    "home": e.KEY_HOME,
    "end": e.KEY_END,
    **{f"f{n}": getattr(e, f"KEY_F{n}") for n in range(1, 13)},
}

_MODIFICADORES_NOMEADOS: dict[str, int] = {
    "ctrl": e.KEY_LEFTCTRL,
    "control": e.KEY_LEFTCTRL,
    "alt": e.KEY_LEFTALT,
    "shift": e.KEY_LEFTSHIFT,
    "super": e.KEY_LEFTMETA,
    "meta": e.KEY_LEFTMETA,
}

_CAPACIDADES: dict[int, Sequence[int]] = {
    e.EV_KEY: sorted(
        {codigo for codigo, _shift in _TECLAS_CARACTERE.values()}
        | set(_TECLAS_NOMEADAS.values())
        | set(_MODIFICADORES_NOMEADOS.values())
        | {e.KEY_LEFTSHIFT, e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE}
    ),
    e.EV_REL: [e.REL_X, e.REL_Y],
}

_BOTOES_MOUSE = {
    "esquerdo": e.BTN_LEFT,
    "direito": e.BTN_RIGHT,
    "meio": e.BTN_MIDDLE,
}


class EntradaIndisponivel(Exception):
    """Levantada quando o dispositivo de entrada virtual não pode ser criado/usado, ou quando
    um caractere/tecla pedido não é suportado."""


def _abrir_dispositivo() -> UInput:
    try:
        return UInput(_CAPACIDADES, name="jarvis-entrada-virtual")
    except Exception as erro:
        raise EntradaIndisponivel(
            f"não foi possível criar o dispositivo de entrada virtual: {erro}"
        ) from erro


def mover_mouse(delta_x: int, delta_y: int) -> None:
    """Move o cursor relativamente (delta_x, delta_y), em pixels/contagens do dispositivo."""
    dispositivo = _abrir_dispositivo()
    try:
        dispositivo.write(e.EV_REL, e.REL_X, delta_x)
        dispositivo.write(e.EV_REL, e.REL_Y, delta_y)
        dispositivo.syn()
    except Exception as erro:
        raise EntradaIndisponivel(f"falha ao mover o mouse: {erro}") from erro
    finally:
        dispositivo.close()


def clicar(botao: str = "esquerdo") -> None:
    """Pressiona e solta um botão do mouse na posição atual do cursor."""
    if botao not in _BOTOES_MOUSE:
        raise EntradaIndisponivel(
            f"botão '{botao}' desconhecido (use: {', '.join(_BOTOES_MOUSE)})"
        )
    codigo = _BOTOES_MOUSE[botao]
    dispositivo = _abrir_dispositivo()
    try:
        dispositivo.write(e.EV_KEY, codigo, 1)
        dispositivo.syn()
        time.sleep(ATRASO_ENTRE_EVENTOS_SEGUNDOS)
        dispositivo.write(e.EV_KEY, codigo, 0)
        dispositivo.syn()
    except Exception as erro:
        raise EntradaIndisponivel(f"falha ao clicar: {erro}") from erro
    finally:
        dispositivo.close()


def digitar(texto: str) -> None:
    """Digita texto ASCII simples (letras, dígitos, espaço, pontuação comum).

    Não suporta acentos/Unicode além do mapeado acima — o caractere real que sai depende do
    layout de teclado XKB ativo no sistema, que este módulo não controla (ver docs/DECISOES.md).
    Levanta EntradaIndisponivel apontando o caractere exato se algo não suportado aparecer, em
    vez de digitar silenciosamente algo errado.
    """
    for indice, caractere in enumerate(texto):
        if caractere not in _TECLAS_CARACTERE:
            raise EntradaIndisponivel(
                f"caractere {caractere!r} (posição {indice}) não é suportado por digitar()"
            )

    dispositivo = _abrir_dispositivo()
    try:
        for caractere in texto:
            codigo, precisa_shift = _TECLAS_CARACTERE[caractere]
            if precisa_shift:
                dispositivo.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
            dispositivo.write(e.EV_KEY, codigo, 1)
            dispositivo.syn()
            time.sleep(ATRASO_ENTRE_EVENTOS_SEGUNDOS)
            dispositivo.write(e.EV_KEY, codigo, 0)
            if precisa_shift:
                dispositivo.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
            dispositivo.syn()
            time.sleep(ATRASO_ENTRE_EVENTOS_SEGUNDOS)
    except Exception as erro:
        raise EntradaIndisponivel(f"falha ao digitar: {erro}") from erro
    finally:
        dispositivo.close()


def tecla(combinacao: str) -> None:
    """Pressiona uma tecla nomeada, com modificadores opcionais separados por '+'.

    Exemplos: "enter", "esc", "ctrl+c", "alt+f4", "ctrl+shift+t".
    """
    partes = [parte.strip().lower() for parte in combinacao.split("+") if parte.strip()]
    if not partes:
        raise EntradaIndisponivel("combinação de tecla vazia")

    *nomes_modificadores, nome_tecla = partes
    codigos_modificadores = []
    for nome in nomes_modificadores:
        if nome not in _MODIFICADORES_NOMEADOS:
            raise EntradaIndisponivel(f"modificador '{nome}' desconhecido")
        codigos_modificadores.append(_MODIFICADORES_NOMEADOS[nome])

    if nome_tecla in _TECLAS_NOMEADAS:
        codigo_tecla = _TECLAS_NOMEADAS[nome_tecla]
    elif nome_tecla in _TECLAS_CARACTERE:
        codigo_tecla, _precisa_shift = _TECLAS_CARACTERE[nome_tecla]
    else:
        raise EntradaIndisponivel(f"tecla '{nome_tecla}' desconhecida")

    dispositivo = _abrir_dispositivo()
    try:
        for codigo_mod in codigos_modificadores:
            dispositivo.write(e.EV_KEY, codigo_mod, 1)
        dispositivo.write(e.EV_KEY, codigo_tecla, 1)
        dispositivo.syn()
        time.sleep(ATRASO_ENTRE_EVENTOS_SEGUNDOS)
        dispositivo.write(e.EV_KEY, codigo_tecla, 0)
        for codigo_mod in reversed(codigos_modificadores):
            dispositivo.write(e.EV_KEY, codigo_mod, 0)
        dispositivo.syn()
    except Exception as erro:
        raise EntradaIndisponivel(f"falha ao pressionar tecla: {erro}") from erro
    finally:
        dispositivo.close()
