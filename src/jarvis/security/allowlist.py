"""Controle de quais binários o `terminal.exec` (e ferramentas futuras) pode rodar.

`sudo`/`su`/`doas`/`pkexec` são recusados SEMPRE, mesmo que alguém coloque um deles na allowlist
de config.yaml por engano — "sem sudo" é invariante do projeto, não uma opção configurável.
"""

from __future__ import annotations

BINARIOS_SEMPRE_PROIBIDOS = frozenset({"sudo", "su", "doas", "pkexec"})


class ErroForaDaAllowlist(Exception):
    """Levantada quando um binário pedido não está autorizado a rodar."""


def validar_binario_permitido(binario: str, allowlist: tuple[str, ...]) -> None:
    if binario in BINARIOS_SEMPRE_PROIBIDOS:
        raise ErroForaDaAllowlist(f"binário '{binario}' é proibido sempre, independente de config")
    if binario not in allowlist:
        raise ErroForaDaAllowlist(
            f"binário '{binario}' não está na allowlist: {', '.join(allowlist) or '(vazia)'}"
        )
