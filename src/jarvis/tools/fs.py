"""Ferramentas de sistema de arquivos. O jail (confinamento de caminho) é aplicado pelo executor
antes de qualquer executar() aqui rodar — estas funções assumem o caminho já validado.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jarvis.tools.base import Ferramenta, NivelRisco

SCHEMA_CAMINHO = {
    "type": "object",
    "properties": {"caminho": {"type": "string"}},
    "required": ["caminho"],
    "additionalProperties": False,
}

SCHEMA_ESCREVER = {
    "type": "object",
    "properties": {
        "caminho": {"type": "string"},
        "conteudo": {"type": "string"},
    },
    "required": ["caminho", "conteudo"],
    "additionalProperties": False,
}


def _fs_read(argumentos: dict[str, Any]) -> str:
    return Path(argumentos["caminho"]).expanduser().read_text(encoding="utf-8")


def _fs_list(argumentos: dict[str, Any]) -> list[str]:
    caminho = Path(argumentos["caminho"]).expanduser()
    return sorted(item.name for item in caminho.iterdir())


def _fs_write(argumentos: dict[str, Any]) -> str:
    caminho = Path(argumentos["caminho"]).expanduser()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(argumentos["conteudo"], encoding="utf-8")
    return f"escrito em {caminho}"


def _fs_write_capturar_estado(argumentos: dict[str, Any]) -> str | None:
    caminho = Path(argumentos["caminho"]).expanduser()
    if caminho.exists():
        return caminho.read_text(encoding="utf-8")
    return None


def _fs_write_reverter(argumentos: dict[str, Any], estado_anterior: Any) -> None:
    caminho = Path(argumentos["caminho"]).expanduser()
    if estado_anterior is None:
        caminho.unlink(missing_ok=True)
    else:
        caminho.write_text(str(estado_anterior), encoding="utf-8")


def criar_ferramentas_fs() -> list[Ferramenta]:
    return [
        Ferramenta(
            nome="fs.read",
            descricao=(
                "Lê o conteúdo de um arquivo de texto dentro do workspace ou de uma raiz de "
                "leitura autorizada (config seguranca.jail_paths_leitura)."
            ),
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_CAMINHO,
            executar=_fs_read,
            campos_caminho=("caminho",),
        ),
        Ferramenta(
            nome="fs.list",
            descricao=(
                "Lista os nomes de arquivos e pastas dentro de um diretório do workspace ou de "
                "uma raiz de leitura autorizada (config seguranca.jail_paths_leitura)."
            ),
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_CAMINHO,
            executar=_fs_list,
            campos_caminho=("caminho",),
        ),
        Ferramenta(
            nome="fs.write",
            descricao="Escreve (cria ou sobrescreve) um arquivo de texto dentro do workspace.",
            risco=NivelRisco.LOW,
            schema_argumentos=SCHEMA_ESCREVER,
            executar=_fs_write,
            campos_caminho=("caminho",),
            capturar_estado=_fs_write_capturar_estado,
            reverter=_fs_write_reverter,
        ),
    ]
