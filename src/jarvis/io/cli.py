"""Ponto de entrada da CLI do JARVIS. Conversação real chega no marco M1."""

from __future__ import annotations

import argparse

from rich.console import Console

from jarvis.core.configuracao import carregar_configuracao
from jarvis.io.audio import (
    AudioIndisponivel,
    dispositivo_entrada_padrao,
    dispositivo_padrao_do_sistema,
    dispositivo_saida_padrao,
    gerar_beep,
    listar_dispositivos,
    tocar,
)
from jarvis.providers import ErroProvider, LLMProvider, criar_provider_llm

console = Console()

COMANDOS_DE_SAIDA = {"sair", "exit", "quit"}


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
    configuracao = carregar_configuracao()
    try:
        provider = criar_provider_llm(configuracao)
    except ErroProvider as erro:
        console.print(f"[bold red]erro:[/bold red] {erro}")
        return
    _executar_conversa(provider)


def _executar_conversa(provider: LLMProvider) -> None:
    console.print(
        "[bold cyan]JARVIS[/bold cyan] — modo conversa. "
        "Digite 'sair' (ou Ctrl+C/Ctrl+D) para encerrar, 'reiniciar' para começar do zero.\n"
    )

    while True:
        try:
            texto_usuario = console.input("[bold green]você>[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        if not texto_usuario:
            continue
        if texto_usuario in COMANDOS_DE_SAIDA:
            break
        if texto_usuario == "reiniciar":
            provider.reiniciar()
            console.print("[dim]sessão reiniciada.[/dim]\n")
            continue

        try:
            resposta = provider.enviar(texto_usuario)
        except ErroProvider as erro:
            console.print(f"[bold red]erro:[/bold red] {erro}\n")
            continue

        console.print(f"[bold magenta]jarvis>[/bold magenta] {resposta}\n")


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
