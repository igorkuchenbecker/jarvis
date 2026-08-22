"""Carregamento de config.yaml do JARVIS, com padrões embutidos que funcionam sem o arquivo."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CAMINHO_CONFIG_PADRAO = Path.home() / "jarvis" / "config.yaml"


@dataclass(frozen=True)
class ConfiguracaoClaudeCli:
    binario: str = "claude"
    timeout_segundos: int = 120


@dataclass(frozen=True)
class Configuracao:
    llm_padrao: str = "claude_cli"
    claude_cli: ConfiguracaoClaudeCli = field(default_factory=ConfiguracaoClaudeCli)


def carregar_configuracao(caminho: Path = CAMINHO_CONFIG_PADRAO) -> Configuracao:
    if not caminho.exists():
        return Configuracao()

    bruto: dict[str, Any] = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    provedor = bruto.get("provedor") or {}
    claude_cli_bruto = provedor.get("claude_cli") or {}

    return Configuracao(
        llm_padrao=provedor.get("llm_padrao", "claude_cli"),
        claude_cli=ConfiguracaoClaudeCli(
            binario=claude_cli_bruto.get("binario", "claude"),
            timeout_segundos=claude_cli_bruto.get("timeout_segundos", 120),
        ),
    )
