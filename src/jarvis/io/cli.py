"""Ponto de entrada da CLI do JARVIS. Conversação real chega no marco M1."""

from __future__ import annotations

import argparse
from importlib.metadata import version

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from jarvis.core.configuracao import Configuracao, carregar_configuracao
from jarvis.core.loop import (
    MAX_ITERACOES_PADRAO,
    MAX_REPAROS_PADRAO,
    processar_turno,
)
from jarvis.core.objetivos import RepositorioObjetivos
from jarvis.core.planejador import executar_objetivo
from jarvis.io import agendador as agendar
from jarvis.io.audio import (
    AudioIndisponivel,
    aparar_silencio,
    capturar,
    dispositivo_entrada_padrao,
    dispositivo_padrao_do_sistema,
    dispositivo_saida_padrao,
    gerar_beep,
    listar_dispositivos,
    tocar,
)
from jarvis.memory.conhecimento import RepositorioConhecimento
from jarvis.observability.auditoria import RegistradorAuditoria
from jarvis.providers import (
    ErroProvider,
    LLMProvider,
    STTProvider,
    TTSProvider,
    criar_provider_llm,
    criar_provider_stt,
    criar_provider_tts,
)
from jarvis.security.executor import Acao, Executor
from jarvis.security.jail import ErroForaDoJail, resolver_dentro_do_jail
from jarvis.tools import RegistroFerramentas, criar_registro_ferramentas_padrao
from jarvis.tools.base import Ferramenta

console = Console()

COMANDOS_DE_SAIDA = {"sair", "exit", "quit"}


def _seguro(valor: object) -> str:
    """Escapa `[...]` de conteúdo vindo do LLM/ferramentas antes de imprimir com Rich.

    O Rich interpreta `[algo]` em `console.print()` como marcação de estilo por padrão — uma
    citação `[arquivo § seção]` vinda do LLM (M5) era silenciosamente engolida sem isto, porque
    "arquivo § seção" não é um estilo Rich válido. Achado na prática, não é hipotético.
    """
    return escape(str(valor))

PROMPT_SISTEMA_COM_FERRAMENTAS = (
    "Você é o JARVIS, o agente pessoal autônomo do usuário, rodando localmente no Linux dele.\n"
    "Você pode usar ferramentas para agir de verdade no sistema. Para usar uma, responda SOMENTE "
    'com um JSON exatamente neste formato, sem nenhum texto antes ou depois:\n'
    '{{"tipo": "acao", "ferramenta": "<nome>", "argumentos": {{...}}}}\n'
    "Use as chaves EXATAS 'tipo', 'ferramenta' e 'argumentos' — nunca 'tool', 'name', "
    "'args' ou 'parameters'.\n"
    "Ferramentas disponíveis:\n{ferramentas}\n"
    "Para perguntas de conhecimento, responda preferencialmente com base no Second Brain "
    "(conhecimento.buscar/pesquisar); use a web (web.buscar) só para o que o conhecimento "
    "local não cobre.\n"
    "Se não precisar de nenhuma ferramenta, responda normalmente em texto, direto e conciso."
)


def principal() -> None:
    analisador = _construir_analisador()
    argumentos = analisador.parse_args()
    argumentos.funcao(argumentos)


def _construir_analisador() -> argparse.ArgumentParser:
    analisador = argparse.ArgumentParser(prog="jarvis")
    analisador.set_defaults(funcao=_comando_padrao)
    analisador.add_argument(
        "--version", action="version", version=f"jarvis {version('jarvis')}"
    )
    subcomandos = analisador.add_subparsers()

    comando_voz = subcomandos.add_parser("voz", help="comandos relacionados a voz")
    subcomandos_voz = comando_voz.add_subparsers(required=True)
    comando_voz_check = subcomandos_voz.add_parser(
        "check", help="verifica microfone/saída de áudio e toca um beep de teste"
    )
    comando_voz_check.set_defaults(funcao=_comando_voz_check)

    comando_voz_falar = subcomandos_voz.add_parser(
        "falar", help="conversa por voz push-to-talk (ENTER para gravar, com ferramentas)"
    )
    comando_voz_falar.set_defaults(funcao=_comando_voz_falar)

    comando_audit = subcomandos.add_parser(
        "audit", help="lista as últimas ações registradas em auditoria"
    )
    comando_audit.add_argument("--limite", type=int, default=20)
    comando_audit.set_defaults(funcao=_comando_audit)

    comando_why = subcomandos.add_parser(
        "why", help="explica uma ação da auditoria pelo número (1 = mais recente)"
    )
    comando_why.add_argument("indice", type=int)
    comando_why.set_defaults(funcao=_comando_why)

    comando_run = subcomandos.add_parser(
        "run", help="persegue um objetivo multi-passo, com replanning e checkpoint"
    )
    comando_run.add_argument("objetivo", type=str)
    comando_run.set_defaults(funcao=_comando_run)

    comando_indexar = subcomandos.add_parser(
        "indexar", help="indexa .md/.txt/.pdf de um diretório autorizado em conhecimento.diretorios"
    )
    comando_indexar.add_argument("diretorio", type=str)
    comando_indexar.set_defaults(funcao=_comando_indexar)

    comando_agendar = subcomandos.add_parser(
        "agendar",
        help="tarefas periódicas via systemd user timers (add|listar|remover|testar)",
    )
    subcomandos_agendar = comando_agendar.add_subparsers(required=True)
    comando_agendar_add = subcomandos_agendar.add_parser(
        "add", help="cria uma tarefa que roda `jarvis run <objetivo>` no horário marcado"
    )
    comando_agendar_add.add_argument("--nome", required=True)
    comando_agendar_add.add_argument("--objetivo", required=True)
    grupo_quando = comando_agendar_add.add_mutually_exclusive_group(required=True)
    grupo_quando.add_argument("--diarias", metavar="HH:MM", help="todos os dias no horário")
    grupo_quando.add_argument(
        "--a-cada", metavar="MINUTOS", type=int, help="a cada N minutos"
    )
    grupo_quando.add_argument(
        "--quando", metavar="ONCALENDAR", help="expressão OnCalendar do systemd (avançado)"
    )
    comando_agendar_add.add_argument(
        "--sobrescrever", action="store_true", help="substitui tarefa com o mesmo nome"
    )
    comando_agendar_add.set_defaults(funcao=_comando_agendar_add)

    comando_agendar_listar = subcomandos_agendar.add_parser(
        "listar", help="lista as tarefas agendadas"
    )
    comando_agendar_listar.set_defaults(funcao=_comando_agendar_listar)

    comando_agendar_remover = subcomandos_agendar.add_parser(
        "remover", help="remove uma tarefa pelo nome"
    )
    comando_agendar_remover.add_argument("nome", type=str)
    comando_agendar_remover.set_defaults(funcao=_comando_agendar_remover)

    comando_agendar_testar = subcomandos_agendar.add_parser(
        "testar", help="dispara a tarefa agora (systemctl --user start)"
    )
    comando_agendar_testar.add_argument("nome", type=str)
    comando_agendar_testar.set_defaults(funcao=_comando_agendar_testar)

    return analisador


def _montar_prompt_sistema(registro: RegistroFerramentas) -> str:
    return PROMPT_SISTEMA_COM_FERRAMENTAS.format(ferramentas=registro.descrever_para_prompt())


def _solicitar_aprovacao_interativa(acao: Acao, ferramenta: Ferramenta) -> bool:
    console.print(
        f"[bold yellow]aprovação necessária[/bold yellow] — {acao.ferramenta} "
        f"(risco {ferramenta.risco.name}) com argumentos {_seguro(acao.argumentos)}"
    )
    try:
        resposta = console.input("[bold yellow]permitir? (s/N)[/bold yellow] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return resposta in {"s", "sim", "y", "yes"}


def _construir_executor(configuracao: Configuracao) -> tuple[RegistroFerramentas, Executor]:
    registro = criar_registro_ferramentas_padrao(configuracao)
    auditoria = RegistradorAuditoria(configuracao.caminhos.auditoria_jsonl)
    executor = Executor(
        registro,
        jail_paths=list(configuracao.seguranca.jail_paths),
        jail_paths_leitura=configuracao.seguranca.jail_paths_leitura,
        allowlist_binarios=configuracao.seguranca.allowlist_binarios,
        nivel_autonomia=configuracao.autonomia.nivel,
        solicitar_aprovacao=_solicitar_aprovacao_interativa,
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
    _executar_conversa(
        provider,
        executor,
        max_iteracoes=configuracao.limites.max_iteracoes_por_turno,
        max_reparos=configuracao.limites.max_reparos_por_turno,
    )


def _executar_conversa(
    provider: LLMProvider,
    executor: Executor | None = None,
    max_iteracoes: int = MAX_ITERACOES_PADRAO,
    max_reparos: int = MAX_REPAROS_PADRAO,
) -> None:
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
            with console.status("[dim]pensando...[/dim]", spinner="dots"):
                if executor is None:
                    resposta_final = provider.enviar(texto_usuario)
                else:
                    turno = processar_turno(
                        provider,
                        executor,
                        texto_usuario,
                        max_iteracoes=max_iteracoes,
                        max_reparos=max_reparos,
                    )
                    resposta_final = turno.resposta_final
        except ErroProvider as erro:
            console.print(f"[bold red]erro:[/bold red] {erro}\n")
            continue

        if executor is not None:
            for acao in turno.acoes_executadas:
                console.print(
                    f"[dim]→ executou {acao.ferramenta}({_seguro(acao.argumentos)})[/dim]"
                )

        console.print(f"[bold magenta]jarvis>[/bold magenta] {_seguro(resposta_final)}\n")


def _executar_conversa_voz(
    provider: LLMProvider,
    executor: Executor,
    stt: STTProvider,
    tts: TTSProvider,
    duracao_captura_segundos: float,
    taxa_amostragem: int,
    max_iteracoes: int = MAX_ITERACOES_PADRAO,
    max_reparos: int = MAX_REPAROS_PADRAO,
) -> None:
    """Loop de conversa por voz push-to-talk (M8/V3): mesmo `processar_turno` com ferramentas
    usado pela conversa em texto (M2) — não é mais o LLM direto sem tool-calling cogitado
    quando M1/M2 ainda não existiam (ver docs/DECISOES.md, decisão revisitada nesta fatia).
    """
    console.print(
        "[bold cyan]JARVIS[/bold cyan] — modo voz (push-to-talk). "
        "Pressione ENTER para falar, ou digite 'sair'+ENTER para encerrar.\n"
    )

    while True:
        try:
            entrada = console.input("[bold green]ENTER para falar>[/bold green] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        if entrada in COMANDOS_DE_SAIDA:
            break

        console.print("[dim]🎙  gravando...[/dim]")
        try:
            sinal_capturado = capturar(duracao_captura_segundos, taxa_amostragem)
        except AudioIndisponivel as erro:
            console.print(f"[bold red]erro ao gravar:[/bold red] {erro}\n")
            continue

        sinal_aparado = aparar_silencio(sinal_capturado, taxa_amostragem)
        if sinal_aparado.size == 0:
            console.print("[yellow]não ouvi nada, tente de novo.[/yellow]\n")
            continue

        try:
            texto_usuario = stt.transcrever(sinal_aparado, taxa_amostragem)
        except ErroProvider as erro:
            console.print(f"[bold red]erro ao transcrever:[/bold red] {erro}\n")
            continue

        console.print(f"[bold green]você (voz)>[/bold green] {_seguro(texto_usuario)}")

        try:
            with console.status("[dim]pensando...[/dim]", spinner="dots"):
                turno = processar_turno(
                    provider,
                    executor,
                    texto_usuario,
                    max_iteracoes=max_iteracoes,
                    max_reparos=max_reparos,
                )
        except ErroProvider as erro:
            console.print(f"[bold red]erro:[/bold red] {erro}\n")
            continue

        for acao in turno.acoes_executadas:
            console.print(f"[dim]→ executou {acao.ferramenta}({_seguro(acao.argumentos)})[/dim]")

        console.print(f"[bold magenta]jarvis>[/bold magenta] {_seguro(turno.resposta_final)}")

        try:
            sinal_resposta, taxa_resposta = tts.sintetizar(turno.resposta_final)
            tocar(sinal_resposta, taxa_resposta)
        except (ErroProvider, AudioIndisponivel) as erro:
            console.print(f"[bold red]erro ao falar a resposta:[/bold red] {erro}")

        console.print()


def _comando_voz_falar(argumentos: argparse.Namespace) -> None:
    configuracao = carregar_configuracao()
    if not configuracao.voz.habilitada:
        console.print(
            "[bold red]erro:[/bold red] voz desabilitada — ligue 'voz.habilitada: true' "
            "em config.yaml"
        )
        return

    registro, executor = _construir_executor(configuracao)
    try:
        provider = criar_provider_llm(configuracao, prompt_sistema=_montar_prompt_sistema(registro))
        stt = criar_provider_stt(configuracao)
        tts = criar_provider_tts(configuracao)
    except ErroProvider as erro:
        console.print(f"[bold red]erro:[/bold red] {erro}")
        return

    _executar_conversa_voz(
        provider,
        executor,
        stt,
        tts,
        configuracao.voz.duracao_captura_segundos,
        configuracao.voz.taxa_amostragem,
        max_iteracoes=configuracao.limites.max_iteracoes_por_turno,
        max_reparos=configuracao.limites.max_reparos_por_turno,
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


def _comando_run(argumentos: argparse.Namespace) -> None:
    configuracao = carregar_configuracao()
    registro, executor = _construir_executor(configuracao)
    try:
        provider = criar_provider_llm(configuracao, prompt_sistema=_montar_prompt_sistema(registro))
    except ErroProvider as erro:
        console.print(f"[bold red]erro:[/bold red] {erro}")
        return

    repositorio = RepositorioObjetivos(configuracao.caminhos.banco_dados)

    def _mostrar_progresso(mensagem: str) -> None:
        console.print(f"[dim]→ {_seguro(mensagem)}[/dim]")

    try:
        resultado = executar_objetivo(
            provider,
            executor,
            repositorio,
            argumentos.objetivo,
            max_replanejamentos=configuracao.limites.max_replanejamentos,
            max_iteracoes=configuracao.limites.max_iteracoes_por_turno,
            max_reparos=configuracao.limites.max_reparos_por_turno,
            ao_progredir=_mostrar_progresso,
        )
    except ErroProvider as erro:
        console.print(f"[bold red]erro:[/bold red] {erro}")
        return

    if resultado.estado == "concluido":
        console.print(
            f"[bold green]objetivo concluído[/bold green] "
            f"({len(resultado.subtarefas)} subtarefa(s))"
        )
    else:
        console.print(
            "[bold red]objetivo não concluído[/bold red] — replanejamentos esgotados"
        )


def _comando_indexar(argumentos: argparse.Namespace) -> None:
    configuracao = carregar_configuracao()

    if not configuracao.conhecimento.diretorios:
        console.print(
            "[bold red]erro:[/bold red] nenhum diretório autorizado em "
            "'conhecimento.diretorios' no config.yaml"
        )
        return

    try:
        caminho = resolver_dentro_do_jail(
            argumentos.diretorio, list(configuracao.conhecimento.diretorios)
        )
    except ErroForaDoJail as erro:
        console.print(f"[bold red]erro:[/bold red] {erro}")
        return

    repositorio = RepositorioConhecimento(configuracao.caminhos.banco_dados)
    quantidade = repositorio.ingerir_diretorio(caminho)
    console.print(
        f"[bold green]{quantidade} trecho(s) indexado(s)[/bold green] a partir de {caminho}"
    )


def _comando_audit(argumentos: argparse.Namespace) -> None:
    configuracao = carregar_configuracao()
    registrador = RegistradorAuditoria(configuracao.caminhos.auditoria_jsonl)
    registros = list(reversed(registrador.ler_todos()))[: argumentos.limite]

    if not registros:
        console.print("[dim]nenhum registro de auditoria ainda.[/dim]")
        return

    tabela = Table()
    tabela.add_column("#")
    tabela.add_column("quando")
    tabela.add_column("ação")
    tabela.add_column("resultado")
    tabela.add_column("duração (s)")
    for indice, registro in enumerate(registros, start=1):
        tabela.add_row(
            str(registro.indice or indice),
            registro.quando,
            registro.acao,
            registro.resultado,
            f"{registro.duracao_segundos:.3f}",
        )
    console.print(tabela)


def _comando_why(argumentos: argparse.Namespace) -> None:
    configuracao = carregar_configuracao()
    registrador = RegistradorAuditoria(configuracao.caminhos.auditoria_jsonl)
    registro = next(
        (r for r in registrador.ler_todos() if r.indice == argumentos.indice), None
    )

    if registro is None:
        console.print(f"[bold red]erro:[/bold red] não há registro #{argumentos.indice}")
        return

    console.print(f"[bold]#{registro.indice}[/bold] {registro.acao} em {registro.quando}")
    console.print(f"argumentos: {_seguro(registro.argumentos_seguros)}")
    console.print(f"resultado: {_seguro(registro.resultado)}")
    console.print(f"duração: {registro.duracao_segundos:.3f}s")
    console.print(f"custo estimado: US${registro.custo_estimado_usd:.4f}")


def _comando_agendar_add(argumentos: argparse.Namespace) -> None:
    try:
        timer = agendar.criar_tarefa(
            argumentos.nome,
            argumentos.objetivo,
            diarias=argumentos.diarias,
            a_cada=argumentos.a_cada,
            quando=argumentos.quando,
            sobrescrever=argumentos.sobrescrever,
        )
    except agendar.ErroAgendador as erro:
        console.print(f"[bold red]erro:[/bold red] {erro}")
        return
    console.print(
        f"[bold green]tarefa agendada.[/bold green] timer: {timer.name} — "
        f"`jarvis agendar testar {argumentos.nome}` roda agora"
    )


def _comando_agendar_listar(argumentos: argparse.Namespace) -> None:
    nomes = agendar.listar_tarefas()
    if not nomes:
        console.print("[dim]nenhuma tarefa agendada.[/dim]")
        return
    console.print("[bold]Tarefas agendadas:[/bold]")
    for nome in nomes:
        console.print(f"  - {nome}")


def _comando_agendar_remover(argumentos: argparse.Namespace) -> None:
    try:
        agendar.remover_tarefa(argumentos.nome)
    except agendar.ErroAgendador as erro:
        console.print(f"[bold red]erro:[/bold red] {erro}")
        return
    console.print(f"[bold green]tarefa removida:[/bold green] {argumentos.nome}")


def _comando_agendar_testar(argumentos: argparse.Namespace) -> None:
    try:
        agendar.testar_tarefa(argumentos.nome)
    except agendar.ErroAgendador as erro:
        console.print(f"[bold red]erro:[/bold red] {erro}")
        return
    console.print(f"[bold green]tarefa disparada:[/bold green] {argumentos.nome}")


if __name__ == "__main__":
    principal()
