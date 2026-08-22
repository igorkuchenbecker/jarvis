"""Interface comum a todo provider de LLM do JARVIS — trocável via config.yaml."""

from __future__ import annotations

from typing import Protocol


class ErroProvider(Exception):
    """Levantada quando um provider de LLM falha ao responder, de forma amigável para o usuário."""


class LLMProvider(Protocol):
    def enviar(self, mensagem: str) -> str:
        """Envia uma mensagem do usuário na sessão corrente e retorna a resposta completa."""
        ...

    def reiniciar(self) -> None:
        """Descarta o histórico da sessão corrente e começa uma nova do zero."""
        ...
