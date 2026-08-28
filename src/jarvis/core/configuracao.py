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
    # Teto de tokens de saída por chamada. Modelos com raciocínio (ex.: openai/gpt-oss-120b
    # no Groq) emitem um campo `reasoning` que consome desse teto antes do `content` — com o
    # default do servidor (baixo) a resposta pode vir com `content` vazio. 0 = não enviar o
    # campo (usa o default do servidor).
    max_tokens: int = 8192
    # Modelos com raciocínio (qwen3, gpt-oss, deepseek-r1...) emitem um campo `reasoning` que
    # consome do teto ANTES do `content`; se o ceiling ficar baixo demais, `content` vem vazio
    # ou cortado no meio de uma ação. Este piso garante um mínimo para esses modelos (0 = sem
    # piso). O valor de `max_tokens` acima, quando explicitamente maior, continua valendo.
    piso_max_tokens_raciocinio: int = 16384
    # Alguns modelos (ex.: gpt-oss no Groq) emitem tool calling nativa mesmo quando a API não
    # declara ferramentas — o servidor então rejeita (HTTP 400 "tool choice is none"). Enviar
    # `tools: []` + `tool_choice: "none"` força texto puro (protocolo de ações do JARVIS).
    desabilitar_ferramentas_nativas: bool = True


@dataclass(frozen=True)
class ConfiguracaoAutonomia:
    nivel: int = 2


@dataclass(frozen=True)
class ConfiguracaoLimites:
    timeout_por_passo_segundos: int = 60
    max_iteracoes_por_turno: int = 12
    max_reparos_por_turno: int = 2
    max_replanejamentos: int = 3


@dataclass(frozen=True)
class ConfiguracaoSeguranca:
    jail_paths: tuple[Path, ...] = field(
        default_factory=lambda: (RAIZ_JARVIS_PADRAO / "workspace",)
    )
    # Raízes extras visíveis SÓ para ferramentas READ_ONLY (fs.read/fs.list).
    # fs.write nunca enxerga isto -- continua confinado a jail_paths. Vazio
    # por padrão (comportamento antigo preservado até o usuário configurar).
    jail_paths_leitura: tuple[Path, ...] = ()
    allowlist_binarios: tuple[str, ...] = ALLOWLIST_BINARIOS_PADRAO


@dataclass(frozen=True)
class ConfiguracaoConhecimento:
    diretorios: tuple[Path, ...] = ()


@dataclass(frozen=True)
class ConfiguracaoComputador:
    habilitada: bool = False


@dataclass(frozen=True)
class ConfiguracaoWeb:
    habilitada: bool = True
    timeout_segundos: int = 15
    limite_padrao: int = 4


@dataclass(frozen=True)
class ConfiguracaoGdap:
    """GDAP (Global Data Automation Platform) é um projeto irmão em ~/gdap, rodando como
    servidor HTTP separado (`gdap system serve`). O JARVIS fala com ele só pela API HTTP dele
    -- nunca importa o pacote gdap nem toca no banco dele diretamente --, do mesmo jeito que
    qualquer outro cliente da API (a própria CLI/web UI do GDAP). Ver `io/gdap.py`.
    """

    habilitada: bool = False
    base_url: str = "http://127.0.0.1:8000"
    # Nome da variável de ambiente com a API key do GDAP (`gdap system key create jarvis
    # --role analyst`). Igual a openai_compat.api_key_env: o config.yaml nunca guarda o segredo
    # em si, só o nome da variável.
    api_key_env: str = ""
    timeout_segundos: int = 30
    # Só pipelines nesta lista podem ser rodados por gdap.executar_pipeline (MEDIUM) -- mesma
    # filosofia de seguranca.allowlist_binarios para terminal.exec, adaptada porque o Executor
    # não tem um mecanismo genérico de allowlist além de binário de terminal (ver DECISOES.md).
    pipelines_permitidos: tuple[str, ...] = ()


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
    modelos_voz: Path = field(default_factory=lambda: RAIZ_JARVIS_PADRAO / "dados" / "modelos_voz")


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
    web: ConfiguracaoWeb = field(default_factory=ConfiguracaoWeb)
    gdap: ConfiguracaoGdap = field(default_factory=ConfiguracaoGdap)


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
    web_bruta = bruto.get("web") or {}
    gdap_bruto = bruto.get("gdap") or {}

    padroes_caminhos = ConfiguracaoCaminhos()
    padroes_seguranca = ConfiguracaoSeguranca()
    padroes_limites = ConfiguracaoLimites()
    padroes_autonomia = ConfiguracaoAutonomia()
    padroes_voz = ConfiguracaoVoz()
    padroes_computador = ConfiguracaoComputador()
    padroes_web = ConfiguracaoWeb()
    padroes_gdap = ConfiguracaoGdap()

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
            max_tokens=int(
                openai_compat_bruto.get("max_tokens", ConfiguracaoOpenAiCompat().max_tokens)
            ),
            piso_max_tokens_raciocinio=int(
                openai_compat_bruto.get(
                    "piso_max_tokens_raciocinio",
                    ConfiguracaoOpenAiCompat().piso_max_tokens_raciocinio,
                )
            ),
            desabilitar_ferramentas_nativas=bool(
                openai_compat_bruto.get(
                    "desabilitar_ferramentas_nativas",
                    ConfiguracaoOpenAiCompat().desabilitar_ferramentas_nativas,
                )
            ),
        ),
        autonomia=ConfiguracaoAutonomia(
            nivel=autonomia_bruta.get("nivel", padroes_autonomia.nivel),
        ),
        limites=ConfiguracaoLimites(
            timeout_por_passo_segundos=limites_brutos.get(
                "timeout_por_passo_segundos", padroes_limites.timeout_por_passo_segundos
            ),
            max_iteracoes_por_turno=limites_brutos.get(
                "max_iteracoes_por_turno", padroes_limites.max_iteracoes_por_turno
            ),
            max_reparos_por_turno=limites_brutos.get(
                "max_reparos_por_turno", padroes_limites.max_reparos_por_turno
            ),
            max_replanejamentos=limites_brutos.get(
                "max_replanejamentos", padroes_limites.max_replanejamentos
            ),
        ),
        seguranca=ConfiguracaoSeguranca(
            jail_paths=tuple(
                Path(item).expanduser()
                for item in seguranca_bruta.get(
                    "jail_paths", [str(p) for p in padroes_seguranca.jail_paths]
                )
            ),
            jail_paths_leitura=tuple(
                Path(item).expanduser()
                for item in seguranca_bruta.get(
                    "jail_paths_leitura", [str(p) for p in padroes_seguranca.jail_paths_leitura]
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
        web=ConfiguracaoWeb(
            habilitada=web_bruta.get("habilitada", padroes_web.habilitada),
            timeout_segundos=int(web_bruta.get("timeout_segundos", padroes_web.timeout_segundos)),
            limite_padrao=int(web_bruta.get("limite_padrao", padroes_web.limite_padrao)),
        ),
        gdap=ConfiguracaoGdap(
            habilitada=gdap_bruto.get("habilitada", padroes_gdap.habilitada),
            base_url=str(gdap_bruto.get("base_url", padroes_gdap.base_url)),
            api_key_env=str(gdap_bruto.get("api_key_env", padroes_gdap.api_key_env)),
            timeout_segundos=int(gdap_bruto.get("timeout_segundos", padroes_gdap.timeout_segundos)),
            pipelines_permitidos=tuple(
                gdap_bruto.get("pipelines_permitidos", list(padroes_gdap.pipelines_permitidos))
            ),
        ),
    )
