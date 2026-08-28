"""Ferramentas de "computer use" (M9): mouse, teclado e leitura de janelas abertas.

Primeiro uso real de NivelRisco.CRITICAL no projeto — clicar e digitar podem fazer qualquer
coisa na sessão gráfica do usuário (enviar uma mensagem, apagar um arquivo via atalho, confirmar
uma compra), sem allowlist possível (não dá pra "permitir" um pixel ou uma tecla com segurança
por si só, ao contrário de `terminal.exec`, que pelo menos restringe o binário). A defesa aqui é
inteiramente a aprovação humana interativa que HIGH/CRITICAL já exigem sempre no Executor — ver
docs/DECISOES.md.

`computador.listar_janelas` é READ_ONLY (só lê estado via hyprctl, sem side effects). Mover o
mouse sem clicar é MEDIUM (raramente causa efeito real por si só, mas já é ação física visível na
sessão do usuário, mais que um LOW comum). Mesma lógica para `computador.focar_janela`: muda o
foco do teclado, ação visível mas de baixa consequência.
"""

from __future__ import annotations

from typing import Any

from jarvis.io.entrada import clicar, digitar, mover_mouse, tecla
from jarvis.io.janelas import focar_janela, listar_janelas
from jarvis.tools.base import Ferramenta, NivelRisco

SCHEMA_VAZIO = {"type": "object", "properties": {}, "additionalProperties": False}

SCHEMA_MOVER_MOUSE = {
    "type": "object",
    "properties": {
        "delta_x": {"type": "integer"},
        "delta_y": {"type": "integer"},
    },
    "required": ["delta_x", "delta_y"],
    "additionalProperties": False,
}

SCHEMA_CLICAR = {
    "type": "object",
    "properties": {
        "botao": {"type": "string", "enum": ["esquerdo", "direito", "meio"]},
    },
    "additionalProperties": False,
}

SCHEMA_DIGITAR = {
    "type": "object",
    "properties": {
        "texto": {"type": "string"},
    },
    "required": ["texto"],
    "additionalProperties": False,
}

SCHEMA_TECLA = {
    "type": "object",
    "properties": {
        "combinacao": {"type": "string"},
    },
    "required": ["combinacao"],
    "additionalProperties": False,
}

SCHEMA_FOCAR_JANELA = {
    "type": "object",
    "properties": {
        "seletor": {"type": "string"},
    },
    "required": ["seletor"],
    "additionalProperties": False,
}


def _computador_listar_janelas(argumentos: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "endereco": janela.endereco,
            "classe": janela.classe,
            "titulo": janela.titulo,
            "workspace": janela.workspace,
            "ativa_no_momento": janela.ativa_no_momento,
        }
        for janela in listar_janelas()
    ]


def _computador_mover_mouse(argumentos: dict[str, Any]) -> str:
    delta_x = int(argumentos["delta_x"])
    delta_y = int(argumentos["delta_y"])
    mover_mouse(delta_x, delta_y)
    return f"mouse movido ({delta_x:+d}, {delta_y:+d})"


def _computador_clicar(argumentos: dict[str, Any]) -> str:
    botao = argumentos.get("botao", "esquerdo")
    clicar(botao)
    return f"clique {botao} executado"


def _computador_digitar(argumentos: dict[str, Any]) -> str:
    texto = argumentos["texto"]
    digitar(texto)
    return f"{len(texto)} caractere(s) digitado(s)"


def _computador_tecla(argumentos: dict[str, Any]) -> str:
    combinacao = argumentos["combinacao"]
    tecla(combinacao)
    return f"tecla '{combinacao}' pressionada"


def _computador_focar_janela(argumentos: dict[str, Any]) -> str:
    seletor = argumentos["seletor"]
    focar_janela(seletor)
    return f"foco movido para '{seletor}'"


def criar_ferramentas_computador() -> list[Ferramenta]:
    return [
        Ferramenta(
            nome="computador.listar_janelas",
            descricao="Lista as janelas abertas (classe, título, workspace, qual está ativa).",
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_VAZIO,
            executar=_computador_listar_janelas,
        ),
        Ferramenta(
            nome="computador.mover_mouse",
            descricao="Move o cursor do mouse relativamente (delta_x, delta_y em pixels).",
            risco=NivelRisco.MEDIUM,
            schema_argumentos=SCHEMA_MOVER_MOUSE,
            executar=_computador_mover_mouse,
        ),
        Ferramenta(
            nome="computador.clicar",
            descricao="Clica um botão do mouse (esquerdo/direito/meio) na posição atual.",
            risco=NivelRisco.CRITICAL,
            schema_argumentos=SCHEMA_CLICAR,
            executar=_computador_clicar,
        ),
        Ferramenta(
            nome="computador.digitar",
            descricao=(
                "Digita texto ASCII simples (sem acentos) onde o foco de teclado estiver."
            ),
            risco=NivelRisco.CRITICAL,
            schema_argumentos=SCHEMA_DIGITAR,
            executar=_computador_digitar,
        ),
        Ferramenta(
            nome="computador.tecla",
            descricao="Pressiona uma tecla ou combinação, ex.: 'enter', 'ctrl+c', 'alt+f4'.",
            risco=NivelRisco.CRITICAL,
            schema_argumentos=SCHEMA_TECLA,
            executar=_computador_tecla,
        ),
        Ferramenta(
            nome="computador.focar_janela",
            descricao=(
                "Move o foco do teclado para a janela que casa com o seletor do "
                "hyprctl (ex.: 'address:0x...','class:(kitty)','class:(^brave$)', "
                "'title:Terminal'). Use computador.listar_janelas antes para descobrir "
                "o seletor."
            ),
            risco=NivelRisco.MEDIUM,
            schema_argumentos=SCHEMA_FOCAR_JANELA,
            executar=_computador_focar_janela,
        ),
    ]
