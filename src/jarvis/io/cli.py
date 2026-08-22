"""Ponto de entrada da CLI do JARVIS. Conversação real chega no marco M1."""

from __future__ import annotations

import argparse

from rich.console import Console

from jarvis.io.audio import (
    AudioIndisponivel,
    dispositivo_entrada_padrao,
    dispositivo_padrao_do_sistema,
    dispositivo_saida_padrao,
    gerar_beep,
    listar_dispositivos,
    tocar,
)

console = Console()


def principal() -> None:
    analisador = _construir_analisador()
    argumentos = analisador.parse_args()
    argumentos.funcao(argumentos)


def _construir_analisador() -> argparse.ArgumentParser:
    analisador = argparse.ArgumentParser(prog="jarvis")
    analisador.set_defaults(funcao=_comando_padrao)
    subcomandos = analisador.add_subparsers()

    comando_voz = subcomandos.add_parser("voz", help="comandos relacionados a voz")
    subcomandos_voz = comando_voz.add_subparsers(required=True)
    comando_voz_check = subcomandos_voz.add_parser(
        "check", help="verifica microfone/saída de áudio e toca um beep de teste"
    )
    comando_voz_check.set_defaults(funcao=_comando_voz_check)

    return analisador


def _comando_padrao(argumentos: argparse.Namespace) -> None:
    console.print(
        "[bold cyan]JARVIS[/bold cyan] — fundação instalada. Marco M1 trará a conversa real."
    )


def _comando_voz_check(argumentos: argparse.Namespace) -> None:
    try:
        dispositivos = listar_dispositivos()
    except AudioIndisponivel as erro:
        console.print(f"[bold red]erro:[/bold red] {erro}")
        return

    entrada = dispositivo_padrao_do_sistema("input") or dispositivo_entrada_padrao(dispositivos)
    saida = dispositivo_padrao_do_sistema("output") or dispositivo_saida_padrao(dispositivos)

    if entrada is None:
        console.print("[bold yellow]aviso:[/bold yellow] nenhum microfone encontrado")
    else:
        console.print(f"microfone: [green]{entrada.nome}[/green] (índice {entrada.indice})")

    if saida is None:
        console.print("[bold yellow]aviso:[/bold yellow] nenhuma saída de áudio encontrada")
        return
    console.print(f"saída: [green]{saida.nome}[/green] (índice {saida.indice})")

    try:
        tocar(gerar_beep())
        console.print("[bold green]beep tocado com sucesso[/bold green]")
    except AudioIndisponivel as erro:
        console.print(f"[bold red]erro ao tocar beep:[/bold red] {erro}")


if __name__ == "__main__":
    principal()
