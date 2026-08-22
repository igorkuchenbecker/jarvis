"""Interfaces comuns a providers do JARVIS — trocáveis via config.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ErroProvider(Exception):
    """Levantada quando um provider falha ao responder, de forma amigável para o usuário."""


class LLMProvider(Protocol):
    def enviar(self, mensagem: str) -> str:
        """Envia uma mensagem do usuário na sessão corrente e retorna a resposta completa."""
        ...

    def reiniciar(self) -> None:
        """Descarta o histórico da sessão corrente e começa uma nova do zero."""
        ...


class VisionProvider(Protocol):
    def analisar(self, caminho_imagem: Path, pergunta: str) -> str:
        """Analisa uma imagem local e responde à pergunta sobre ela, sem manter sessão."""
        ...
