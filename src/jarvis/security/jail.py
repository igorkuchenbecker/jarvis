"""Confinamento de caminhos de arquivo aos diretórios explicitamente autorizados em config.yaml.

Bloqueia travessia (`..`), caminhos absolutos fora do jail e symlinks que escapem dele — tudo via
`Path.resolve()`, que segue symlinks e normaliza `..` antes da comparação.
"""

from __future__ import annotations

from pathlib import Path


class ErroForaDoJail(Exception):
    """Levantada quando um caminho pedido está fora dos diretórios autorizados."""


def resolver_dentro_do_jail(caminho_bruto: str, jail_paths: list[Path]) -> Path:
    caminho_resolvido = Path(caminho_bruto).expanduser().resolve()

    for raiz in jail_paths:
        raiz_resolvida = raiz.expanduser().resolve()
        if caminho_resolvido == raiz_resolvida or raiz_resolvida in caminho_resolvido.parents:
            return caminho_resolvido

    raizes = ", ".join(str(p) for p in jail_paths)
    raise ErroForaDoJail(
        f"caminho '{caminho_bruto}' está fora dos diretórios autorizados: {raizes}"
    )
