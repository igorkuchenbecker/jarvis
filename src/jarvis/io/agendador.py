"""Tarefas periódicas do JARVIS via systemd user timers.

`jarvis agendar add` grava um par .service/.timer em ~/.config/systemd/user e habilita o timer
com `systemctl --user`. O ExecStart roda `python -m jarvis.io.cli run "<objetivo>"`, então a
tarefa usa o mesmo loop/ferramentas da conversa; ações HIGH continuam exigindo aprovação humana
(fail-closed) — um timer nunca executa mutação sem usuário. `jarvis agendar listar/remover/testar`
consultam/removem/disparam os timers.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

SistemaSystemctl = Callable[[list[str]], str]

PREFIJO_UNIDADE = "jarvis_tarefa_"


class ErroAgendador(Exception):
    pass


def slugificar(nome: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
    if not slug:
        raise ErroAgendador("nome da tarefa não pode virar slug vazio")
    return slug


def _valor_unit(valor: str) -> str:
    """Escape para valor de linha `Chave=...` no formato systemd (quotes + %)."""
    return '"' + valor.replace("%", "%%").replace('"', '\\"') + '"'


def _escrever_unit(diretorio: Path, nome_arquivo: str, conteudo: str) -> Path:
    caminho = diretorio / nome_arquivo
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


def _oncalendar_diarias(hhmm: str) -> str:
    if not re.match(r"^\d{1,2}:\d{2}$", hhmm):
        raise ErroAgendador("--diarias precisa do formato HH:MM")
    hora, minuto = [int(parte) for parte in hhmm.split(":")]
    if hora > 23 or minuto > 59:
        raise ErroAgendador("--diarias fora de alcance: hora 0-23, minuto 0-59")
    return f"*-*-* {hora:02d}:{minuto:02d}:00"


def _oncalendar_a_cada(minutos: int) -> str:
    if minutos <= 0:
        raise ErroAgendador("--a-cada precisa ser um número positivo de minutos")
    return f"*:0/{minutos}"


def _montar_quando(diarias: str | None, a_cada: int | None, quando: str | None) -> str:
    if diarias is not None:
        return _oncalendar_diarias(diarias)
    if a_cada is not None:
        return _oncalendar_a_cada(a_cada)
    if quando is not None:
        if not quando.strip() or "\n" in quando:
            raise ErroAgendador("--quando precisa de uma expressão OnCalendar válida")
        return quando.strip()
    raise ErroAgendador("informe --diarias, --a-cada ou --quando")


_SERVICO_TEMPLATE = """[Unit]
Description=JARVIS agendado: {nome}

[Service]
Type=oneshot
ExecStart={execstart}
"""

_TIMER_TEMPLATE = """[Unit]
Description=JARVIS agendado: {nome}

[Timer]
OnCalendar={quando}
Persistent=true

[Install]
WantedBy=timers.target
"""


def _systemctl(args: list[str]) -> str:
    try:
        subprocess.run(
            ["systemctl", "--user", *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as erro:
        raise ErroAgendador(
            "systemctl não encontrado — o agendador usa systemd user timers"
        ) from erro
    except subprocess.CalledProcessError as erro:
        mensagem = (erro.stderr or "").strip() or (erro.stdout or "").strip()
        raise ErroAgendador(f"systemctl --user {' '.join(args)} falhou: {mensagem}") from erro
    except OSError as erro:
        raise ErroAgendador(f"não foi possível rodar systemctl --user: {erro}") from erro
    return ""


def _diretorio_units() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def _execstart(objetivo: str) -> str:
    alvo = _valor_unit(objetivo)
    binario = shutil.which("jarvis")
    if binario:
        return f"{binario} run {alvo}"
    return f"{sys.executable} -m jarvis.io.cli run {alvo}"


def criar_tarefa(
    nome: str,
    objetivo: str,
    diarias: str | None = None,
    a_cada: int | None = None,
    quando: str | None = None,
    sobrescrever: bool = False,
    diretorio: Path | None = None,
    systemctl: SistemaSystemctl = _systemctl,
    execstart: str | None = None,
) -> Path:
    slug = slugificar(nome)
    quando_final = _montar_quando(diarias, a_cada, quando)
    diretorio_final = diretorio or _diretorio_units()
    diretorio_final.mkdir(parents=True, exist_ok=True)

    servico = diretorio_final / f"{PREFIJO_UNIDADE}{slug}.service"
    timer = diretorio_final / f"{PREFIJO_UNIDADE}{slug}.timer"
    if (servico.exists() or timer.exists()) and not sobrescrever:
        raise ErroAgendador(f"tarefa '{nome}' já existe — use --sobrescrever para substituir")

    execstart_final = execstart or _execstart(objetivo)
    _escrever_unit(
        diretorio_final,
        servico.name,
        _SERVICO_TEMPLATE.format(nome=nome, execstart=execstart_final),
    )
    _escrever_unit(
        diretorio_final,
        timer.name,
        _TIMER_TEMPLATE.format(nome=nome, quando=quando_final),
    )

    systemctl(["daemon-reload"])
    systemctl(["enable", "--now", timer.name])
    return timer


def listar_tarefas(
    diretorio: Path | None = None, systemctl: SistemaSystemctl | None = None
) -> list[str]:
    if systemctl is None:
        return sorted(
            servico.name.removeprefix(PREFIJO_UNIDADE)[: -len(".service")]
            for servico in (diretorio or _diretorio_units()).glob(f"{PREFIJO_UNIDADE}*.service")
        )
    saida = systemctl(["list-timers", "--all", "--no-legend"])
    slugs = set()
    for linha in saida.splitlines():
        for coluna in linha.split():
            if coluna.startswith(PREFIJO_UNIDADE) and coluna.endswith(".timer"):
                slugs.add(coluna[len(PREFIJO_UNIDADE) : -len(".timer")])
    return sorted(slugs)


def remover_tarefa(
    nome: str,
    diretorio: Path | None = None,
    systemctl: SistemaSystemctl = _systemctl,
) -> None:
    slug = slugificar(nome)
    diretorio_final = diretorio or _diretorio_units()
    for unidade in (
        f"{PREFIJO_UNIDADE}{slug}.timer",
        f"{PREFIJO_UNIDADE}{slug}.service",
    ):
        caminho = diretorio_final / unidade
        if caminho.exists():
            systemctl(["disable", "--now", unidade])
            caminho.unlink()
    systemctl(["daemon-reload"])


def testar_tarefa(nome: str, systemctl: SistemaSystemctl = _systemctl) -> None:
    slug = slugificar(nome)
    systemctl(["start", f"{PREFIJO_UNIDADE}{slug}.service"])
