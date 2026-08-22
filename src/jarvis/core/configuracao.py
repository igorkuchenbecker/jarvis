"""Carregamento de config.yaml do JARVIS, com padrões embutidos que funcionam sem o arquivo."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CAMINHO_CONFIG_PADRAO = Path.home() / "jarvis" / "config.yaml"
RAIZ_JARVIS_PADRAO = Path.home() / "jarvis"


@dataclass(frozen=True)
class ConfiguracaoClaudeCli:
    binario: str = "claude"
    timeout_segundos: int = 120


@dataclass(frozen=True)
class ConfiguracaoSeguranca:
    jail_paths: tuple[Path, ...] = field(
        default_factory=lambda: (RAIZ_JARVIS_PADRAO / "workspace",)
    )


@dataclass(frozen=True)
class ConfiguracaoCaminhos:
    workspace: Path = field(default_factory=lambda: RAIZ_JARVIS_PADRAO / "workspace")
    banco_dados: Path = field(default_factory=lambda: RAIZ_JARVIS_PADRAO / "dados" / "jarvis.db")
    auditoria_jsonl: Path = field(
        default_factory=lambda: RAIZ_JARVIS_PADRAO / "dados" / "auditoria.jsonl"
    )


@dataclass(frozen=True)
class Configuracao:
    llm_padrao: str = "claude_cli"
    claude_cli: ConfiguracaoClaudeCli = field(default_factory=ConfiguracaoClaudeCli)
    seguranca: ConfiguracaoSeguranca = field(default_factory=ConfiguracaoSeguranca)
    caminhos: ConfiguracaoCaminhos = field(default_factory=ConfiguracaoCaminhos)


def carregar_configuracao(caminho: Path = CAMINHO_CONFIG_PADRAO) -> Configuracao:
    if not caminho.exists():
        return Configuracao()

    bruto: dict[str, Any] = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    provedor = bruto.get("provedor") or {}
    claude_cli_bruto = provedor.get("claude_cli") or {}
    seguranca_bruta = bruto.get("seguranca") or {}
    caminhos_brutos = bruto.get("caminhos") or {}

    padroes_caminhos = ConfiguracaoCaminhos()
    padroes_seguranca = ConfiguracaoSeguranca()

    return Configuracao(
        llm_padrao=provedor.get("llm_padrao", "claude_cli"),
        claude_cli=ConfiguracaoClaudeCli(
            binario=claude_cli_bruto.get("binario", "claude"),
            timeout_segundos=claude_cli_bruto.get("timeout_segundos", 120),
        ),
        seguranca=ConfiguracaoSeguranca(
            jail_paths=tuple(
                Path(item).expanduser()
                for item in seguranca_bruta.get(
                    "jail_paths", [str(p) for p in padroes_seguranca.jail_paths]
                )
            ),
        ),
        caminhos=ConfiguracaoCaminhos(
            workspace=Path(
                caminhos_brutos.get("workspace", str(padroes_caminhos.workspace))
            ).expanduser(),
            banco_dados=Path(
                caminhos_brutos.get("banco_dados", str(padroes_caminhos.banco_dados))
            ).expanduser(),
            auditoria_jsonl=Path(
                caminhos_brutos.get("auditoria_jsonl", str(padroes_caminhos.auditoria_jsonl))
            ).expanduser(),
        ),
    )
