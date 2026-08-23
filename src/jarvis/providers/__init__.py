"""Providers de LLM/visão/voz do JARVIS — trocáveis via config.yaml."""

from __future__ import annotations

from jarvis.core.configuracao import Configuracao
from jarvis.providers.base import (
    ErroProvider,
    LLMProvider,
    STTProvider,
    TTSProvider,
    VisionProvider,
)
from jarvis.providers.claude_cli import ClaudeCliProvider, ClaudeCliVisionProvider
from jarvis.providers.stt import WhisperSTTProvider
from jarvis.providers.tts import PiperTTSProvider

__all__ = [
    "ClaudeCliProvider",
    "ClaudeCliVisionProvider",
    "ErroProvider",
    "LLMProvider",
    "PiperTTSProvider",
    "STTProvider",
    "TTSProvider",
    "VisionProvider",
    "WhisperSTTProvider",
    "criar_provider_llm",
    "criar_provider_stt",
    "criar_provider_tts",
    "criar_provider_visao",
]


def criar_provider_llm(
    configuracao: Configuracao, prompt_sistema: str | None = None
) -> LLMProvider:
    if configuracao.llm_padrao == "claude_cli":
        if prompt_sistema is None:
            return ClaudeCliProvider(
                binario=configuracao.claude_cli.binario,
                timeout_segundos=configuracao.claude_cli.timeout_segundos,
            )
        return ClaudeCliProvider(
            binario=configuracao.claude_cli.binario,
            timeout_segundos=configuracao.claude_cli.timeout_segundos,
            prompt_sistema=prompt_sistema,
        )
    raise ErroProvider(f"provedor de LLM '{configuracao.llm_padrao}' ainda não é suportado")


def criar_provider_visao(configuracao: Configuracao) -> VisionProvider:
    if configuracao.llm_padrao == "claude_cli":
        return ClaudeCliVisionProvider(
            binario=configuracao.claude_cli.binario,
            timeout_segundos=configuracao.claude_cli.timeout_segundos,
        )
    raise ErroProvider(f"provedor de visão para '{configuracao.llm_padrao}' ainda não é suportado")


def criar_provider_stt(configuracao: Configuracao) -> STTProvider:
    return WhisperSTTProvider(
        modelo=configuracao.voz.stt_modelo,
        idioma=configuracao.voz.idioma,
        diretorio_download=str(configuracao.caminhos.modelos_voz),
    )


def criar_provider_tts(configuracao: Configuracao) -> TTSProvider:
    return PiperTTSProvider(
        voz=configuracao.voz.tts_voz,
        diretorio_modelos=configuracao.caminhos.modelos_voz,
    )
