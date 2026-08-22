"""Ferramentas de sistema: informação de máquina, processos e execução de terminal.

`terminal.exec` nunca usa `shell=True` (argumentos vão como lista, sem interpolação de shell) e
roda com ambiente sanitizado — só o necessário para o binário encontrar coisas básicas, nada do
ambiente do processo do JARVIS é repassado por padrão (evita vazar segredos em variáveis de
ambiente para um comando de terceiros).
"""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from typing import Any

from jarvis.tools.base import Ferramenta, NivelRisco

TAMANHO_MAXIMO_SAIDA = 4000
SINAIS_PERMITIDOS = {"SIGTERM", "SIGKILL", "SIGINT"}

SCHEMA_VAZIO = {"type": "object", "properties": {}, "additionalProperties": False}

SCHEMA_PROC_KILL = {
    "type": "object",
    "properties": {
        "pid": {"type": "integer"},
        "sinal": {"type": "string"},
    },
    "required": ["pid"],
    "additionalProperties": False,
}

SCHEMA_TERMINAL_EXEC = {
    "type": "object",
    "properties": {
        "comando": {"type": "string"},
        "argumentos": {"type": "array"},
    },
    "required": ["comando"],
    "additionalProperties": False,
}


def _ler_meminfo() -> dict[str, float]:
    valores: dict[str, float] = {}
    try:
        for linha in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            chave, _, resto = linha.partition(":")
            if chave in {"MemTotal", "MemAvailable"}:
                valores[chave] = round(int(resto.strip().split()[0]) / (1024 * 1024), 2)
    except OSError:
        pass
    return valores


def _ler_uptime_segundos() -> float | None:
    try:
        return float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
    except OSError:
        return None


def _sys_info(argumentos: dict[str, Any]) -> dict[str, Any]:
    uso_disco = os.statvfs(Path.home())
    memoria = _ler_meminfo()
    return {
        "cpus": os.cpu_count(),
        "carga_media": os.getloadavg(),
        "memoria_total_gb": memoria.get("MemTotal"),
        "memoria_disponivel_gb": memoria.get("MemAvailable"),
        "disco_home_livre_gb": round(uso_disco.f_bavail * uso_disco.f_frsize / 1e9, 2),
        "disco_home_total_gb": round(uso_disco.f_blocks * uso_disco.f_frsize / 1e9, 2),
        "uptime_segundos": _ler_uptime_segundos(),
    }


def _proc_list(argumentos: dict[str, Any]) -> list[dict[str, Any]]:
    processos = []
    for entrada in Path("/proc").iterdir():
        if not entrada.name.isdigit():
            continue
        try:
            nome = (entrada / "comm").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        processos.append({"pid": int(entrada.name), "nome": nome})
    return sorted(processos, key=lambda item: item["pid"])


def _proc_kill(argumentos: dict[str, Any]) -> str:
    pid = int(argumentos["pid"])
    nome_sinal = argumentos.get("sinal", "SIGTERM")
    if nome_sinal not in SINAIS_PERMITIDOS:
        raise ValueError(f"sinal '{nome_sinal}' não permitido, use um de {SINAIS_PERMITIDOS}")

    try:
        os.kill(pid, 0)
    except ProcessLookupError as erro:
        raise ValueError(f"processo {pid} não existe") from erro
    except PermissionError as erro:
        raise ValueError(f"sem permissão para sinalizar o processo {pid}") from erro

    os.kill(pid, signal.Signals[nome_sinal].value)
    return f"sinal {nome_sinal} enviado ao processo {pid}"


def _criar_terminal_exec(timeout_segundos: int) -> Any:
    def _terminal_exec(argumentos: dict[str, Any]) -> dict[str, Any]:
        comando = argumentos["comando"]
        lista_argumentos = [str(item) for item in argumentos.get("argumentos", [])]
        ambiente_sanitizado = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(Path.home()),
            "LANG": "C.UTF-8",
        }

        processo = subprocess.run(
            [comando, *lista_argumentos],
            capture_output=True,
            text=True,
            timeout=timeout_segundos,
            env=ambiente_sanitizado,
        )

        return {
            "codigo_saida": processo.returncode,
            "saida": processo.stdout[:TAMANHO_MAXIMO_SAIDA],
            "erro": processo.stderr[:TAMANHO_MAXIMO_SAIDA],
        }

    return _terminal_exec


def criar_ferramentas_sistema(timeout_segundos: int = 30) -> list[Ferramenta]:
    return [
        Ferramenta(
            nome="sys.info",
            descricao="Informações do sistema: CPU, memória, disco e uptime.",
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_VAZIO,
            executar=_sys_info,
        ),
        Ferramenta(
            nome="proc.list",
            descricao="Lista os processos em execução (pid e nome).",
            risco=NivelRisco.READ_ONLY,
            schema_argumentos=SCHEMA_VAZIO,
            executar=_proc_list,
        ),
        Ferramenta(
            nome="proc.kill",
            descricao="Envia um sinal (SIGTERM/SIGKILL/SIGINT) para encerrar um processo por PID.",
            risco=NivelRisco.HIGH,
            schema_argumentos=SCHEMA_PROC_KILL,
            executar=_proc_kill,
        ),
        Ferramenta(
            nome="terminal.exec",
            descricao="Roda um binário da allowlist com argumentos, sem shell, com timeout.",
            risco=NivelRisco.MEDIUM,
            schema_argumentos=SCHEMA_TERMINAL_EXEC,
            executar=_criar_terminal_exec(timeout_segundos),
            campo_binario="comando",
        ),
    ]
