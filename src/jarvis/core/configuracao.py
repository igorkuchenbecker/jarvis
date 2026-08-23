"""Carregamento de config.yaml do JARVIS, com padrões embutidos que funcionam sem o arquivo."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CAMINHO_CONFIG_PADRAO = Path.home() / "jarvis" / "config.yaml"
RAIZ_JARVIS_PADRAO = Path.home() / "jarvis"
ALLOWLIST_BINARIOS_PADRAO = ("ls", "cat", "rg", "git", "fd")


@dataclass(frozen=True)
class ConfiguracaoClaudeCli:
    binario: str = "claude"
    timeout_segundos: int = 120


@dataclass(frozen=True)
class ConfiguracaoOpenAiCompat:
    base_url: str = "http://localhost:11434/v1"
    modelo: str = "llama3"
    api_key_env: str = ""
    timeout_segundos: int = 120


@dataclass(frozen=True)
class ConfiguracaoAutonomia:
    nivel: int = 2


@dataclass(frozen=True)
class ConfiguracaoLimites:
    timeout_por_passo_segundos: int = 60


@dataclass(frozen=True)
class ConfiguracaoSeguranca:
    jail_paths: tuple[Path, ...] = field(
        default_factory=lambda: (RAIZ_JARVIS_PADRAO / "workspace",)
    )
    allowlist_binarios: tuple[str, ...] = ALLOWLIST_BINARIOS_PADRAO


@dataclass(frozen=True)
class ConfiguracaoConhecimento:
    diretorios: tuple[Path, ...] = ()


@dataclass(frozen=True)
class ConfiguracaoComputador:
    habilitada: bool = False


@dataclass(frozen=True)
class ConfiguracaoVoz:
    habilitada: bool = False
    stt_modelo: str = "small"
    dispositivo: str = "auto"
    taxa_amostragem: int = 16000
    idioma: str = "pt"
    tts_voz: str = "pt_BR-faber-medium"
    duracao_captura_segundos: float = 6.0


@dataclass(frozen=True)
class ConfiguracaoCaminhos:
    workspace: Path = field(default_factory=lambda: RAIZ_JARVIS_PADRAO / "workspace")
    banco_dados: Path = field(default_factory=lambda: RAIZ_JARVIS_PADRAO / "dados" / "jarvis.db")
    auditoria_jsonl: Path = field(
        default_factory=lambda: RAIZ_JARVIS_PADRAO / "dados" / "auditoria.jsonl"
    )
    modelos_voz: Path = field(
        default_factory=lambda: RAIZ_JARVIS_PADRAO / "dados" / "modelos_voz"
    )


@dataclass(frozen=True)
class Configuracao:
    llm_padrao: str = "claude_cli"
    claude_cli: ConfiguracaoClaudeCli = field(default_factory=ConfiguracaoClaudeCli)
    openai_compat: ConfiguracaoOpenAiCompat = field(default_factory=ConfiguracaoOpenAiCompat)
    autonomia: ConfiguracaoAutonomia = field(default_factory=ConfiguracaoAutonomia)
    limites: ConfiguracaoLimites = field(default_factory=ConfiguracaoLimites)
    seguranca: ConfiguracaoSeguranca = field(default_factory=ConfiguracaoSeguranca)
    caminhos: ConfiguracaoCaminhos = field(default_factory=ConfiguracaoCaminhos)
    conhecimento: ConfiguracaoConhecimento = field(default_factory=ConfiguracaoConhecimento)
    voz: ConfiguracaoVoz = field(default_factory=ConfiguracaoVoz)
    computador: ConfiguracaoComputador = field(default_factory=ConfiguracaoComputador)


def carregar_configuracao(caminho: Path = CAMINHO_CONFIG_PADRAO) -> Configuracao:
    if not caminho.exists():
        return Configuracao()

    bruto: dict[str, Any] = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    provedor = bruto.get("provedor") or {}
    claude_cli_bruto = provedor.get("claude_cli") or {}
    openai_compat_bruto = provedor.get("openai_compat") or {}
    autonomia_bruta = bruto.get("autonomia") or {}
    limites_brutos = bruto.get("limites") or {}
    seguranca_bruta = bruto.get("seguranca") or {}
    caminhos_brutos = bruto.get("caminhos") or {}
    conhecimento_bruto = bruto.get("conhecimento") or {}
    voz_bruta = bruto.get("voz") or {}
    computador_bruto = bruto.get("computador") or {}

    padroes_caminhos = ConfiguracaoCaminhos()
    padroes_seguranca = ConfiguracaoSeguranca()
    padroes_limites = ConfiguracaoLimites()
    padroes_autonomia = ConfiguracaoAutonomia()
    padroes_voz = ConfiguracaoVoz()
    padroes_computador = ConfiguracaoComputador()

    return Configuracao(
        llm_padrao=provedor.get("llm_padrao", "claude_cli"),
        claude_cli=ConfiguracaoClaudeCli(
            binario=claude_cli_bruto.get("binario", "claude"),
            timeout_segundos=claude_cli_bruto.get("timeout_segundos", 120),
        ),
        openai_compat=ConfiguracaoOpenAiCompat(
            base_url=str(openai_compat_bruto.get("base_url", "http://localhost:11434/v1")),
            modelo=str(openai_compat_bruto.get("modelo", "llama3")),
            api_key_env=str(openai_compat_bruto.get("api_key_env", "")),
            timeout_segundos=int(openai_compat_bruto.get("timeout_segundos", 120)),
        ),
        autonomia=ConfiguracaoAutonomia(
            nivel=autonomia_bruta.get("nivel", padroes_autonomia.nivel),
        ),
        limites=ConfiguracaoLimites(
            timeout_por_passo_segundos=limites_brutos.get(
                "timeout_por_passo_segundos", padroes_limites.timeout_por_passo_segundos
            ),
        ),
        seguranca=ConfiguracaoSeguranca(
            jail_paths=tuple(
                Path(item).expanduser()
                for item in seguranca_bruta.get(
                    "jail_paths", [str(p) for p in padroes_seguranca.jail_paths]
                )
            ),
            allowlist_binarios=tuple(
                seguranca_bruta.get("allowlist_binarios", list(ALLOWLIST_BINARIOS_PADRAO))
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
            modelos_voz=Path(
                caminhos_brutos.get("modelos_voz", str(padroes_caminhos.modelos_voz))
            ).expanduser(),
        ),
        conhecimento=ConfiguracaoConhecimento(
            diretorios=tuple(
                Path(item).expanduser() for item in conhecimento_bruto.get("diretorios", [])
            ),
        ),
        voz=ConfiguracaoVoz(
            habilitada=voz_bruta.get("habilitada", padroes_voz.habilitada),
            stt_modelo=voz_bruta.get("stt_modelo", padroes_voz.stt_modelo),
            dispositivo=voz_bruta.get("dispositivo", padroes_voz.dispositivo),
            taxa_amostragem=voz_bruta.get("taxa_amostragem", padroes_voz.taxa_amostragem),
            idioma=voz_bruta.get("idioma", padroes_voz.idioma),
            tts_voz=voz_bruta.get("tts_voz", padroes_voz.tts_voz),
            duracao_captura_segundos=voz_bruta.get(
                "duracao_captura_segundos", padroes_voz.duracao_captura_segundos
            ),
        ),
        computador=ConfiguracaoComputador(
            habilitada=computador_bruto.get("habilitada", padroes_computador.habilitada),
        ),
    )
