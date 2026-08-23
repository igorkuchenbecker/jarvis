"""Providers de LLM/visão/voz do JARVIS — trocáveis via config.yaml."""

from __future__ import annotations

import os

from jarvis.core.configuracao import Configuracao
from jarvis.providers.base import (
    ErroProvider,
    LLMProvider,
    STTProvider,
    TTSProvider,
    VisionProvider,
)
from jarvis.providers.claude_cli import ClaudeCliProvider, ClaudeCliVisionProvider
from jarvis.providers.openai_compat import OpenAICompatProvider
from jarvis.providers.stt import WhisperSTTProvider
from jarvis.providers.tts import PiperTTSProvider

__all__ = [
    "ClaudeCliProvider",
    "ClaudeCliVisionProvider",
    "ErroProvider",
    "LLMProvider",
    "OpenAICompatProvider",
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
    if configuracao.llm_padrao == "openai_compat":
        ajustes = configuracao.openai_compat
        api_key: str | None = None
        if ajustes.api_key_env:
            api_key = os.environ.get(ajustes.api_key_env)
            if not api_key:
                raise ErroProvider(
                    f"variável de ambiente '{ajustes.api_key_env}' não definida — exporte a "
                    "chave da API ou remova 'api_key_env' de provedor.openai_compat no config.yaml"
                )
        if prompt_sistema is None:
            return OpenAICompatProvider(
                base_url=ajustes.base_url,
                modelo=ajustes.modelo,
                timeout_segundos=ajustes.timeout_segundos,
                api_key=api_key,
            )
        return OpenAICompatProvider(
            base_url=ajustes.base_url,
            modelo=ajustes.modelo,
            timeout_segundos=ajustes.timeout_segundos,
            api_key=api_key,
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
