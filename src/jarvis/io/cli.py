"""Ponto de entrada da CLI do JARVIS. Conversação real chega no marco M1."""

from __future__ import annotations

import argparse

from rich.console import Console

from jarvis.core.configuracao import Configuracao, carregar_configuracao
from jarvis.core.loop import processar_turno
from jarvis.io.audio import (
    AudioIndisponivel,
    dispositivo_entrada_padrao,
    dispositivo_padrao_do_sistema,
    dispositivo_saida_padrao,
    gerar_beep,
    listar_dispositivos,
    tocar,
)
from jarvis.observability.auditoria import RegistradorAuditoria
from jarvis.providers import ErroProvider, LLMProvider, criar_provider_llm
from jarvis.security.executor import Executor
from jarvis.tools import RegistroFerramentas, criar_registro_ferramentas_padrao

console = Console()

COMANDOS_DE_SAIDA = {"sair", "exit", "quit"}

PROMPT_SISTEMA_COM_FERRAMENTAS = (
    "Você é o JARVIS, o agente pessoal autônomo do usuário, rodando localmente no Linux dele.\n"
    "Você pode usar ferramentas para agir de verdade no sistema. Para usar uma, responda SOMENTE "
    'com um JSON exatamente neste formato, sem nenhum texto antes ou depois:\n'
    '{{"tipo": "acao", "ferramenta": "<nome>", "argumentos": {{...}}}}\n'
    "Ferramentas disponíveis:\n{ferramentas}\n"
    "Se não precisar de nenhuma ferramenta, responda normalmente em texto, direto e conciso."
)


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


def _montar_prompt_sistema(registro: RegistroFerramentas) -> str:
    return PROMPT_SISTEMA_COM_FERRAMENTAS.format(ferramentas=registro.descrever_para_prompt())


def _construir_executor(configuracao: Configuracao) -> tuple[RegistroFerramentas, Executor]:
    registro = criar_registro_ferramentas_padrao(configuracao)
    auditoria = RegistradorAuditoria(configuracao.caminhos.auditoria_jsonl)
    executor = Executor(
        registro,
        jail_paths=list(configuracao.seguranca.jail_paths),
        auditoria=auditoria,
    )
    return registro, executor


def _comando_padrao(argumentos: argparse.Namespace) -> None:
    configuracao = carregar_configuracao()
    registro, executor = _construir_executor(configuracao)
    try:
        provider = criar_provider_llm(configuracao, prompt_sistema=_montar_prompt_sistema(registro))
    except ErroProvider as erro:
        console.print(f"[bold red]erro:[/bold red] {erro}")
        return
    _executar_conversa(provider, executor)


def _executar_conversa(provider: LLMProvider, executor: Executor | None = None) -> None:
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
            if executor is None:
                resposta_final = provider.enviar(texto_usuario)
            else:
                turno = processar_turno(provider, executor, texto_usuario)
                for acao in turno.acoes_executadas:
                    console.print(f"[dim]→ executou {acao.ferramenta}({acao.argumentos})[/dim]")
                resposta_final = turno.resposta_final
        except ErroProvider as erro:
            console.print(f"[bold red]erro:[/bold red] {erro}\n")
            continue

        console.print(f"[bold magenta]jarvis>[/bold magenta] {resposta_final}\n")


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
