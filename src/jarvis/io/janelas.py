"""Listagem de janelas via `hyprctl` (Hyprland — compositor-alvo do projeto).

Só leitura. Foco/movimentação de janela por seletor não é exposto aqui: esta máquina roda uma
build do Hyprland com uma camada de dispatch em Lua (`hl.dsp.*`) não documentada e cujo
comportamento de foco por seletor (classe/endereço) se mostrou não confiável em teste manual —
só o foco por direção (`hl.dsp.focus({direction=...})`) foi confirmado funcionando de verdade.
Decisão registrada em docs/DECISOES.md: não expor foco de janela como ferramenta até esse
comportamento ser mais bem entendido; listar janelas (útil para o agente ter contexto do que
está aberto) já cobre a maior parte do valor de "computer use" ler o estado da tela.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


class ErroJanelas(Exception):
    """Levantada quando não é possível consultar as janelas abertas."""


@dataclass(frozen=True)
class Janela:
    endereco: str
    classe: str
    titulo: str
    workspace: str
    ativa_no_momento: bool = False


def listar_janelas(binario: str = "hyprctl", timeout_segundos: int = 10) -> list[Janela]:
    try:
        processo = subprocess.run(
            [binario, "clients", "-j"],
            capture_output=True,
            text=True,
            timeout=timeout_segundos,
        )
    except FileNotFoundError as erro:
        raise ErroJanelas(f"binário '{binario}' não encontrado no PATH") from erro
    except subprocess.TimeoutExpired as erro:
        raise ErroJanelas("hyprctl não respondeu a tempo") from erro

    if processo.returncode != 0:
        raise ErroJanelas(f"{binario} falhou: {processo.stderr.strip()}")

    try:
        brutas = json.loads(processo.stdout)
    except json.JSONDecodeError as erro:
        raise ErroJanelas(f"saída inesperada de '{binario} clients -j': {erro}") from erro

    try:
        endereco_ativa = _endereco_janela_ativa(binario, timeout_segundos)
    except ErroJanelas:
        endereco_ativa = None

    return [
        Janela(
            endereco=bruta["address"],
            classe=bruta.get("class", ""),
            titulo=bruta.get("title", ""),
            workspace=str(bruta.get("workspace", {}).get("name", "")),
            ativa_no_momento=bruta["address"] == endereco_ativa,
        )
        for bruta in brutas
    ]


def _endereco_janela_ativa(binario: str, timeout_segundos: int) -> str | None:
    processo = subprocess.run(
        [binario, "activewindow", "-j"],
        capture_output=True,
        text=True,
        timeout=timeout_segundos,
    )
    if processo.returncode != 0 or not processo.stdout.strip():
        return None
    try:
        bruta = json.loads(processo.stdout)
    except json.JSONDecodeError:
        return None
    endereco = bruta.get("address")
    return str(endereco) if endereco else None
