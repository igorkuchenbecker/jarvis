"""Provider determinístico usado exclusivamente nos testes: nunca toca rede, disco ou CLI real."""

from __future__ import annotations

from jarvis.providers.base import ErroProvider


class FakeProvider:
    def __init__(self, respostas: list[str]) -> None:
        self._respostas = list(respostas)
        self.historico: list[str] = []

    def enviar(self, mensagem: str) -> str:
        self.historico.append(mensagem)
        if not self._respostas:
            raise ErroProvider("FakeProvider ficou sem respostas roteirizadas")
        return self._respostas.pop(0)

    def reiniciar(self) -> None:
        self.historico.clear()
