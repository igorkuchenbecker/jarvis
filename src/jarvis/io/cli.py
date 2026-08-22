"""Ponto de entrada da CLI do JARVIS. Conversação real chega no marco M1."""

from __future__ import annotations

from rich.console import Console

console = Console()


def principal() -> None:
    console.print(
        "[bold cyan]JARVIS[/bold cyan] — fundação instalada. Marco M1 trará a conversa real."
    )


if __name__ == "__main__":
    principal()
