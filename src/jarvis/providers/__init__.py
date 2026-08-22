"""Providers de LLM (e, no futuro, STT/TTS/visão) do JARVIS — trocáveis via config.yaml."""

from __future__ import annotations

from jarvis.core.configuracao import Configuracao
from jarvis.providers.base import ErroProvider, LLMProvider
from jarvis.providers.claude_cli import ClaudeCliProvider

__all__ = ["ClaudeCliProvider", "ErroProvider", "LLMProvider", "criar_provider_llm"]


def criar_provider_llm(configuracao: Configuracao) -> LLMProvider:
    if configuracao.llm_padrao == "claude_cli":
        return ClaudeCliProvider(
            binario=configuracao.claude_cli.binario,
            timeout_segundos=configuracao.claude_cli.timeout_segundos,
        )
    raise ErroProvider(f"provedor de LLM '{configuracao.llm_padrao}' ainda não é suportado")
